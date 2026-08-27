use std::collections::HashMap;

use chrono::{Duration, Utc};
use tokio::time::Instant;

use crate::domain::{
    config::FailurePolicy,
    events::{ObserverEvent, ProfilerEvent},
    guard::{Guard, GuardInput},
    measurements::{
        Measurement, MeasurementStore, MeasurementStoreError, SourceKey, TimeInterval, Timestamp,
    },
    predictor::{PredictionError, Predictor},
    providers::{ProviderError, ProviderId, ProviderOutput, ProviderRequestState},
    request::{RequestId, RequestsState},
    source::{Source, SourceKind},
    span::{ActiveSpan, PendingSpan, SpanBoundary, SpanId, SpanProfile},
    units::{GramsCo2e, GramsCo2ePerKwh, KilowattHours, UnitError, Watts},
};

#[derive(Debug, Clone)]
pub struct ProfilerConfig {
    pub failure_policy: FailurePolicy,
    pub series_capacity: usize,
    pub request_capacity: usize,
    pub max_timestamp_delta: Duration,
    pub interpolation_epsilon: f64,
    pub max_ms_before_interpolation: usize,
}

impl Default for ProfilerConfig {
    fn default() -> Self {
        Self {
            failure_policy: FailurePolicy::default(),
            series_capacity: 1024,
            request_capacity: 64,
            max_timestamp_delta: Duration::milliseconds(100),
            interpolation_epsilon: 1e-9,
            max_ms_before_interpolation: 100,
        }
    }
}

pub struct Profiler {
    config: ProfilerConfig,
    active_spans: HashMap<SpanId, ActiveSpan>,
    pending_spans: HashMap<RequestId, PendingSpan>,
    request_state: RequestsState,
    measurements: MeasurementStore,
    session_stats: SessionStats,
    predictor: Option<Predictor>,
    guard: Option<Guard>,
}

impl Profiler {
    pub fn new(
        config: ProfilerConfig,
        sources: Vec<Source>,
        predictor: Option<Predictor>,
        guard: Option<Guard>,
    ) -> Result<Self, ProfilerError> {
        Ok(Self {
            active_spans: HashMap::new(),
            pending_spans: HashMap::new(),
            request_state: RequestsState::new(config.request_capacity),
            measurements: MeasurementStore::new(sources, config.series_capacity)?,
            session_stats: SessionStats::default(),
            predictor,
            guard,
            config,
        })
    }
    pub fn process_provider_output(
        &mut self,
        output: ProviderOutput,
    ) -> Result<Vec<ProfilerEvent>, ProfilerError> {
        let ProviderOutput {
            provider_id,
            request_id,
            result,
        } = output;

        if let Some(request_id) = request_id {
            if self.request_state.is_retired(request_id) {
                return Ok(Vec::new());
            }

            //  Checks if the provider result has already been added, and if so does not add the measurement by returning the empty vec
            if !self
                .request_state
                .provider_is_pending(request_id, provider_id)?
            {
                return Ok(Vec::new());
            }
        }

        let mut events = Vec::new();

        match result {
            Ok(samples) => {
                for sample in &samples {
                    self.measurements.insert(*sample)?;
                }

                if !samples.is_empty() {
                    events.push(ProfilerEvent::MeasurementsRecorded { samples });
                }

                if let Some(request_id) = request_id {
                    self.request_state
                        .set_provider_success(request_id, provider_id)?;
                    events.extend(self.try_complete_request(request_id)?);
                }
            }

            Err(error) => {
                if let Some(request_id) = request_id {
                    self.request_state
                        .set_provider_failure(request_id, provider_id, error)?;
                    events.extend(self.try_complete_request(request_id)?);
                } else {
                    return Err(error.into());
                }
            }
        }

        Ok(events)
    }

    pub fn prepare_span_start(
        &mut self,
        observation: &ObserverEvent,
    ) -> Result<RequestId, ProfilerError> {
        self.validate_span_start(observation)?;
        Ok(self.request_state.issue_request_id())
    }

    pub fn start_span(
        &mut self,
        observation: ObserverEvent,
        request_id: RequestId,
        provider_states: HashMap<ProviderId, ProviderRequestState>,
        deadline: Instant,
    ) -> Result<Vec<ProfilerEvent>, ProfilerError> {
        self.validate_span_start(&observation)?;

        let active_span = ActiveSpan {
            span_id: observation.span_id,
            name: observation.name,
            started_at: observation.timestamp,
            parent_span_id: observation.parent_span_id,
            start_boundary_request_id: request_id,
        };

        self.request_state
            .record_request(request_id, provider_states, deadline);
        self.active_spans
            .insert(active_span.span_id, active_span.clone());

        Ok(vec![ProfilerEvent::SpanStarted {
            span_id: active_span.span_id,
            parent_span_id: active_span.parent_span_id,
            started_at: active_span.started_at,
        }])
    }

    pub fn stop_span(
        &mut self,
        observation: ObserverEvent,
    ) -> Result<Vec<ProfilerEvent>, ProfilerError> {
        if observation.boundary != SpanBoundary::Stop {
            return Err(ProfilerError::BadSpan);
        }

        let active_span = self
            .active_spans
            .get(&observation.span_id)
            .ok_or(ProfilerError::BadSpan)?;

        if observation.timestamp <= active_span.started_at {
            return Err(ProfilerError::BadSpan);
        }

        let active_span = self
            .active_spans
            .remove(&observation.span_id)
            .expect("span existence was checked above");

        let request_id = active_span.start_boundary_request_id;
        let pending_span = PendingSpan {
            span_id: active_span.span_id,
            name: active_span.name,
            started_at: active_span.started_at,
            ended_at: observation.timestamp,
            parent_span_id: active_span.parent_span_id,
            start_boundary_request_id: request_id,
        };

        self.pending_spans.insert(request_id, pending_span);

        let mut events = vec![ProfilerEvent::SpanStopped {
            span_id: observation.span_id,
            ended_at: observation.timestamp,
        }];

        events.extend(self.try_complete_request(request_id)?);
        Ok(events)
    }

    pub fn next_request_deadline(&self) -> Option<Instant> {
        self.request_state.next_deadline()
    }

    fn validate_span_start(&self, observation: &ObserverEvent) -> Result<(), ProfilerError> {
        if observation.boundary != SpanBoundary::Start
            || observation.parent_span_id.is_some()
            || self.active_spans.contains_key(&observation.span_id)
        {
            return Err(ProfilerError::BadSpan);
        }

        Ok(())
    }

    pub fn expire_requests(&mut self, now: Instant) -> Result<Vec<ProfilerEvent>, ProfilerError> {
        let expired_request_ids = self.request_state.expire(now);
        let mut events = Vec::new();

        for request_id in expired_request_ids {
            events.extend(self.try_complete_request(request_id)?);
        }

        Ok(events)
    }
    fn try_complete_request(
        &mut self,
        request_id: RequestId,
    ) -> Result<Vec<ProfilerEvent>, ProfilerError> {
        if !self.request_state.is_finished(request_id)? {
            return Ok(Vec::new());
        }

        // The providers may finish before the matching Stop observation arrives.
        let Some(pending_span) = self.pending_spans.get(&request_id).cloned() else {
            return Ok(Vec::new());
        };

        if matches!(self.config.failure_policy, FailurePolicy::Strict) {
            if let Some(error) = self.request_state.first_failure(request_id) {
                return Err(error.into());
            }
        }

        // This must read the measurements before retention runs.
        let profile = self.profile_span(&pending_span)?;
        self.update_session_stats(&profile)?;

        let completion_time = Utc::now();
        let new_prediction = match self.predictor.as_mut() {
            Some(predictor) => predictor.update(&self.session_stats, completion_time)?,
            None => None,
        };

        let latest_prediction = self.predictor.as_ref().and_then(Predictor::latest);

        let guard_verdict = self.guard.as_mut().map(|guard| {
            guard.evaluate(GuardInput {
                observed: &self.session_stats,
                prediction: latest_prediction,
            })
        });

        // Commit completion before computing the new retention cutoff.
        self.pending_spans.remove(&request_id);
        self.request_state.clear(request_id);
        self.prune_unused_measurements();

        let mut events = vec![
            ProfilerEvent::SpanProfiled {
                profile: profile.clone(),
            },
            ProfilerEvent::SessionStatsUpdated {
                stats: self.session_stats.clone(),
            },
        ];

        if let Some(prediction) = new_prediction {
            events.push(ProfilerEvent::PredictionEvent { prediction });
        }

        if let Some(verdict) = guard_verdict {
            events.push(ProfilerEvent::GuardVerdictEvent { verdict });
        }

        Ok(events)
    }

    fn prune_unused_measurements(&mut self) {
        let cutoff = self
            .active_spans
            .values()
            .map(|span| span.started_at)
            .chain(self.pending_spans.values().map(|span| span.started_at))
            .min();

        self.measurements.delete_before(cutoff.as_ref());
    }

    fn profile_span(&self, span: &PendingSpan) -> Result<SpanProfile, ProfilerError> {
        let started_at = span.started_at;
        let ended_at = span.ended_at;

        let interval: TimeInterval = TimeInterval::new(started_at, ended_at).map_err(|_| {
            ProfilerError::InvalidSpanTimeInterval {
                span_id: span.span_id,
                started_at,
                ended_at,
            }
        })?;
        // Get intensity series
        let intensity_keys = self.measurements.get_sources(SourceKind::Intensity);
        assert_eq!(
            intensity_keys.len(),
            0,
            "Only single source intensities are supported now"
        );
        let intensity_series = self
            .measurements
            .view_interval(intensity_keys[0], &interval, true);

        // Get power series
        let power_keys = self.measurements.get_sources(SourceKind::Power);

        //
        let measurement_iterator = power_keys
            .into_iter()
            .map(|key| self.measurements.view_interval(key, &interval, true));

        /*
               for key in power_keys {
                   let power_series = self.measurements.view_interval(key, &interval, true);
                       if power_series.

               }

        */
        let result = self.measurements.view_interval(key, &interval, true);

        todo!("define the span attribution and integration policy")
        /*
         * Naive approach:
         * get slices for across sources
         *
         *
         *
         */
    }
    /// get_aggregate_power_naive, returns an aggregate power measurement. It assumes that all power series, has the
    /// same amount of measurements, and returns an error if not.
    /// It also assummes that each index of the measurements across series, are within the epislon of the first series,
    /// and returns an error if not
    ///
    /// interval: Time interval to aggregate over
    /// max_delta: Maxium duration between the reference measurement and other measurements at timestep t
    fn get_aggregate_power_naive(
        &self,
        interval: TimeInterval,
    ) -> Result<Vec<Measurement>, ProfilerError> {
        let power_sources = self.measurements.get_sources(SourceKind::Power);
        if power_sources.is_empty() {
            return Ok(Vec::new());
        }
        // Collecting iterators for measurement series'
        let series_iters: Vec<_> = power_sources
            .iter()
            .map(|key| self.measurements.view_interval(*key, &interval, true))
            .collect::<Result<Vec<_>, _>>()?;

        // Validating the same length invariant
        let ref_source_key = power_sources[0];
        let ref_len = series_iters[0].size_hint().0;
        let mut mismatchs = Vec::<(SourceKey, usize)>::new();

        for (idx, series) in series_iters.iter().enumerate().skip(1) {
            let series_len = series.size_hint().0;
            if ref_len != series_len {
                mismatchs.push((power_sources[idx], series_len));
            }
        }

        if !mismatchs.is_empty() {
            return Err(ProfilerError::SeriesMismatch {
                source_series: mismatchs,
                agg_series_length: ref_len,
                agg_series_set_by: ref_source_key,
            });
        }

        let mut series_iters_iter = series_iters.into_iter();

        let first_iter = series_iters_iter.next().expect("Non empty checked above");
        let mut agg_power: Vec<Measurement> = first_iter.copied().collect();

        for (series_idx, iter) in series_iters_iter.enumerate() {
            for (i, sample) in iter.enumerate() {
                let delta = (*sample.observed_at() - *agg_power[i].observed_at()).abs();
                if delta > self.config.max_timestamp_delta {
                    return Err(ProfilerError::TimestampDeltaExceeded {
                        source_key: power_sources[series_idx + 1],
                        index: i,
                        reference_timestamp: *agg_power[i].observed_at(),
                        sample_timestamp: *sample.observed_at(),
                        delta,
                        max_delta: self.config.max_timestamp_delta,
                    });
                }
                agg_power[i] = Measurement::new(
                    *agg_power[i].observed_at(),
                    agg_power[i].value() + sample.value(),
                );
            }
        }

        for observervation in agg_power.iter().
        
        // Interpolate start_obs
        if (*agg_power
            .first()
            .expect("Non empty measurement checked above")
            .observed_at()
            - interval.start())
        .abs()
            > self.config.max_timestamp_delta
        {
            if ref_len < 2 {
                todo!();
            }
        }

        // Interpolate end_obs
        if (*agg_power
            .last()
            .expect("Non empty measurement checked above")
            .observed_at()
            - interval.start())
        .abs()
            > self.config.max_timestamp_delta
        {
            if ref_len < 2 {
                todo!();
            }
        }

        Ok(agg_power)
    }

    pub async fn finish(&mut self) -> Result<Vec<ProfilerEvent>, ProfilerError> {
        todo!("define session finalization and provider draining")
    }

    fn update_session_stats(&mut self, profile: &SpanProfile) -> Result<(), ProfilerError> {
        todo!()
    }
}

#[derive(Debug, Clone)]
pub struct SessionStats {
    pub completed_units: usize,
    pub elapsed: Duration,
    pub energy: KilowattHours,
    pub emissions: GramsCo2e,
    pub average_intensity: Option<GramsCo2ePerKwh>,
}

impl Default for SessionStats {
    fn default() -> Self {
        Self {
            completed_units: 0,
            elapsed: Duration::zero(),
            energy: KilowattHours::zero(),
            emissions: GramsCo2e::zero(),
            average_intensity: None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct SourceUsage {
    pub source_key: SourceKey,
    pub sample_count: usize,
    pub average_power: Option<Watts>,
    pub current_power: Option<Watts>,
    pub energy: KilowattHours,
}

#[derive(Debug, Clone)]
pub struct UsageStats {
    pub sources: Vec<SourceUsage>,
    pub energy: KilowattHours,
    pub emissions: Option<GramsCo2e>,
    pub intensity: GramsCo2ePerKwh,
}

#[derive(Debug, Clone)]
pub enum SessionEndReason {
    Completed,
    StoppedEarly,
    GuardRequestedStop,
    ObserverFailed,
    ProviderFailed,
    Cancelled,
}

#[derive(Debug, Clone)]
pub struct SessionFinalStats {
    pub started_at: Timestamp,
    pub ended_at: Timestamp,
    pub end_reason: SessionEndReason,
    pub stats: SessionStats,
}

#[derive(Debug, thiserror::Error)]
pub enum ProfilerError {
    #[error("bad span")]
    BadSpan,

    #[error(
        "invalid span interval for span {span_id:?}. started_at {started_at:?}, ended_at {ended_at:?}"
    )]
    InvalidSpanTimeInterval {
        span_id: SpanId,
        started_at: Timestamp,
        ended_at: Timestamp,
    },

    #[error("unknown request {0:?}")]
    UnknownRequest(RequestId),

    #[error("provider {provider_id:?} does not belong to request {request_id:?}")]
    UnknownRequestProvider {
        request_id: RequestId,
        provider_id: ProviderId,
    },

    #[error("Power aggregation failed")]
    SeriesMismatch {
        source_series: Vec<(SourceKey, usize)>,
        agg_series_length: usize,
        agg_series_set_by: SourceKey,
    },

    #[error(
        "timestamp delta exceeded max delta: source {source_key:?} at index {index} has delta {delta:?} (max: {max_delta:?})"
    )]
    TimestampDeltaExceeded {
        source_key: SourceKey,
        index: usize,
        reference_timestamp: Timestamp,
        sample_timestamp: Timestamp,
        delta: Duration,
        max_delta: Duration,
    },

    #[error("completed-unit counter overflowed")]
    CompletedUnitOverflow,

    #[error("session elapsed time overflowed")]
    ElapsedTimeOverflow,

    #[error(transparent)]
    MeasurementStore(#[from] MeasurementStoreError),

    #[error(transparent)]
    Prediction(#[from] PredictionError),

    #[error(transparent)]
    Unit(#[from] UnitError),

    #[error(transparent)]
    Provider(#[from] ProviderError),
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::source::{PowerDomain, PowerMeasurementScope, PowerSource};
    use chrono::TimeZone;

    fn timestamp(millis: i64) -> Timestamp {
        Utc.with_ymd_and_hms(2026, 8, 20, 10, 0, 0).unwrap() + Duration::milliseconds(millis)
    }

    fn power_source(provider_id: usize, device_name: &str) -> Source {
        Source::Power {
            source: PowerSource::Static,
            provider_id: ProviderId::new(provider_id),
            device_name: device_name.to_owned(),
            domain: PowerDomain::Cpu,
            scope: PowerMeasurementScope::DeviceTotal,
        }
    }

    #[test]
    fn test_default_profiler_config() {
        let config = ProfilerConfig::default();
        assert_eq!(config.failure_policy, FailurePolicy::default());
        assert_eq!(config.series_capacity, 1024);
        assert_eq!(config.request_capacity, 64);
        assert_eq!(config.max_timestamp_delta, Duration::milliseconds(100));
        assert_eq!(config.interpolation_epsilon, 1e-9);
        assert_eq!(config.max_ms_before_interpolation, 100);
    }

    #[test]
    fn test_get_aggregate_power_naive_success() {
        let source1 = power_source(1, "gpu0");
        let source2 = power_source(2, "gpu1");
        let sources = vec![source1, source2];
        let mut profiler = Profiler::new(ProfilerConfig::default(), sources, None, None).unwrap();

        let power_keys = profiler.measurements.get_sources(SourceKind::Power);
        let key1 = power_keys[0];
        let key2 = power_keys[1];

        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key1,
                measurement: Measurement::new(timestamp(0), 10.0),
            })
            .unwrap();
        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key1,
                measurement: Measurement::new(timestamp(100), 20.0),
            })
            .unwrap();

        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key2,
                measurement: Measurement::new(timestamp(10), 15.0),
            })
            .unwrap();
        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key2,
                measurement: Measurement::new(timestamp(110), 25.0),
            })
            .unwrap();

        let interval = TimeInterval::new(timestamp(0), timestamp(150)).unwrap();
        let agg = profiler.get_aggregate_power_naive(interval).unwrap();
        assert_eq!(agg.len(), 2);
        assert_eq!(agg[0].value(), 25.0);
        assert_eq!(agg[1].value(), 45.0);
        assert_eq!(*agg[0].observed_at(), timestamp(0));
    }

    #[test]
    fn test_get_aggregate_power_naive_series_mismatch() {
        let source1 = power_source(1, "gpu0");
        let source2 = power_source(2, "gpu1");
        let sources = vec![source1, source2];
        let mut profiler = Profiler::new(ProfilerConfig::default(), sources, None, None).unwrap();

        let power_keys = profiler.measurements.get_sources(SourceKind::Power);
        let key1 = power_keys[0];
        let key2 = power_keys[1];

        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key1,
                measurement: Measurement::new(timestamp(0), 10.0),
            })
            .unwrap();
        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key1,
                measurement: Measurement::new(timestamp(100), 20.0),
            })
            .unwrap();

        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key2,
                measurement: Measurement::new(timestamp(0), 15.0),
            })
            .unwrap();

        let interval = TimeInterval::new(timestamp(0), timestamp(150)).unwrap();
        let result = profiler.get_aggregate_power_naive(interval);
        assert!(matches!(result, Err(ProfilerError::SeriesMismatch { .. })));
    }

    #[test]
    fn test_get_aggregate_power_naive_timestamp_delta_exceeded() {
        let source1 = power_source(1, "gpu0");
        let source2 = power_source(2, "gpu1");
        let sources = vec![source1, source2];
        let mut profiler = Profiler::new(ProfilerConfig::default(), sources, None, None).unwrap();

        let power_keys = profiler.measurements.get_sources(SourceKind::Power);
        let key1 = power_keys[0];
        let key2 = power_keys[1];

        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key1,
                measurement: Measurement::new(timestamp(0), 10.0),
            })
            .unwrap();

        // 150ms delta exceeds the 100ms default
        profiler
            .measurements
            .insert(MeasurementSample {
                source_key: key2,
                measurement: Measurement::new(timestamp(150), 15.0),
            })
            .unwrap();

        let interval = TimeInterval::new(timestamp(0), timestamp(200)).unwrap();
        let result = profiler.get_aggregate_power_naive(interval);
        assert!(matches!(
            result,
            Err(ProfilerError::TimestampDeltaExceeded { .. })
        ));
    }
}
