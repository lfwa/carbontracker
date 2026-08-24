use std::collections::HashMap;

use chrono::{Duration, Utc};
use tokio::time::Instant;

use crate::domain::{
    config::FailurePolicy,
    events::{ObserverEvent, ProfilerEvent},
    guard::{Guard, GuardInput},
    measurements::{MeasurementStore, MeasurementStoreError, SourceKey, Timestamp},
    predictor::{PredictionError, Predictor},
    providers::{ProviderError, ProviderId, ProviderOutput, ProviderRequestState},
    request::{RequestId, RequestsState},
    source::Source,
    span::{ActiveSpan, PendingSpan, SpanBoundary, SpanId},
    units::{GramsCo2e, GramsCo2ePerKwh, KilowattHours, UnitError, Watts},
};

pub struct Profiler {
    active_spans: HashMap<SpanId, ActiveSpan>,
    pending_spans: HashMap<RequestId, PendingSpan>,
    request_state: RequestsState,
    measurements: MeasurementStore,
    session_stats: SessionStats,
    failure_policy: FailurePolicy,
    predictor: Option<Predictor>,
    guard: Option<Guard>,
}

impl Profiler {
    pub fn new(
        predictor: Option<Predictor>,
        guard: Option<Guard>,
        failure_policy: FailurePolicy,
        sources: Vec<Source>,
        series_capacity: usize,
        request_capacity: usize,
    ) -> Self {
        Self {
            active_spans: HashMap::new(),
            pending_spans: HashMap::new(),
            request_state: RequestsState::new(request_capacity),
            measurements: MeasurementStore::new(sources, series_capacity),
            session_stats: SessionStats::default(),
            failure_policy,
            predictor,
            guard,
        }
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

        if matches!(self.failure_policy, FailurePolicy::Strict) {
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
        
        todo!("define the span attribution and integration policy")
        /*
         * Naive approach:
         * get slices for across sources
         * 
         * 
         * 
         */

        
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
pub struct SpanProfile {
    pub span_id: SpanId,
    pub parent_span_id: Option<SpanId>,
    pub name: String,
    pub started_at: Timestamp,
    pub ended_at: Timestamp,
    pub usage: UsageStats,
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
    #[error("received an invalid span")]
    BadSpan,

    #[error("unknown request {0:?}")]
    UnknownRequest(RequestId),

    #[error("provider {provider_id:?} does not belong to request {request_id:?}")]
    UnknownRequestProvider {
        request_id: RequestId,
        provider_id: ProviderId,
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
