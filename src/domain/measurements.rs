use crate::domain::source::Source;
use chrono::{DateTime, Utc};
use std::{
    collections::{HashMap, VecDeque},
    time::Duration,
};

pub type Timestamp = DateTime<Utc>;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Measurement {
    observed_at: Timestamp,
    value: f64,
}

impl Measurement {
    pub fn new(observed_at: Timestamp, value: f64) -> Self {
        Self { observed_at, value }
    }
    pub fn observed_at(&self) -> &Timestamp {
        &self.observed_at
    }
    pub fn value(&self) -> f64 {
        self.value
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct SourceKey(usize);

impl SourceKey {
    pub fn index(self) -> usize {
        self.0
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MeasurementSample {
    source_key: SourceKey,
    measurement: Measurement,
}

#[derive(Debug)]
pub struct MeasurementStore {
    sources: HashMap<Source, SourceKey>,
    series: Vec<VecDeque<Measurement>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum MeasurementStoreError {
    #[error("measurements were inserted out of order")]
    MeasurementsOutOfOrder,

    #[error("unknown measurement source key")]
    UnknownSourceKey,

    #[error("Sources was empty on creation")]
    NoSourcesFoundUponCreation,
}

impl MeasurementStore {
    pub fn new(
        sources: Vec<Source>,
        series_capicity: usize,
    ) -> Result<MeasurementStore, MeasurementStoreError> {
        if sources.is_empty() {
            return Err(MeasurementStoreError::NoSourcesFoundUponCreation);
        }

        let mut store = MeasurementStore {
            sources: HashMap::with_capacity(sources.len()),
            series: Vec::with_capacity(sources.len()),
        };
        for (key, source) in sources.into_iter().enumerate() {
            store.sources.insert(source, SourceKey(key));
            store
                .series
                .insert(key, VecDeque::with_capacity(series_capicity));
        }
        Ok(store)
    }

    pub fn insert(&mut self, sample: MeasurementSample) -> Result<(), MeasurementStoreError> {
        let series = self
            .series
            .get_mut(sample.source_key.index())
            .ok_or(MeasurementStoreError::UnknownSourceKey)?;

        // Gaurentees sort order
        if series
            .back()
            .is_some_and(|last| last.observed_at() > sample.measurement.observed_at())
        {
            return Err(MeasurementStoreError::MeasurementsOutOfOrder);
        }

        series.push_back(sample.measurement);
        Ok(())
    }

    pub fn view(
        &self,
        key: SourceKey,
    ) -> Result<impl Iterator<Item = &Measurement>, MeasurementStoreError> {
        self.series
            .get(key.index())
            .map(|series| series.iter())
            .ok_or(MeasurementStoreError::UnknownSourceKey)
    }

    ///
    ///
    ///
    ///
    ///
    ///
    ///
    ///
    ///
    ///
    pub fn view_interval(
        &self,
        key: SourceKey,
        interval: &TimeInterval,
        include_boundaries: bool,
    ) -> Result<impl Iterator<Item = &Measurement>, MeasurementStoreError> {
        let series = self
            .series
            .get(key.index())
            .ok_or(MeasurementStoreError::UnknownSourceKey)?;

        let start =
            series.partition_point(|measurement| measurement.observed_at() < interval.start());
        let end = series.partition_point(|measurement| measurement.observed_at() <= interval.end());
        if include_boundaries {
            Ok(series.range(start - 1..end))
        } else {
            Ok(series.range(start..end))
        }
    }

    pub fn delete_before(&mut self, cutoff: Option<&Timestamp>) {
        for series in &mut self.series {
            if series.is_empty() {
                continue;
            }

            let retain_from = match cutoff {
                Some(cutoff) => {
                    let first_at_or_after =
                        series.partition_point(|measurement| measurement.observed_at() < cutoff);
                    first_at_or_after.saturating_sub(1)
                }
                None => series.len().saturating_sub(1),
            };

            series.drain(..retain_from);
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct TimeInterval {
    start: Timestamp,
    end: Timestamp,
}

impl TimeInterval {
    pub fn new(start: Timestamp, end: Timestamp) -> Result<Self, TimeIntervalError> {
        if end <= start {
            return Err(TimeIntervalError::EndNotAfterStart { start, end });
        }

        Ok(Self { start, end })
    }

    pub fn start(&self) -> &Timestamp {
        &self.start
    }

    pub fn end(&self) -> &Timestamp {
        &self.end
    }

    pub fn duration(&self) -> Duration {
        self.end
            .signed_duration_since(self.start)
            .to_std()
            .expect("validated interval must have a nonnegative duration")
    }
}

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum TimeIntervalError {
    #[error("interval must have end after start: {start}..{end}")]
    EndNotAfterStart { start: Timestamp, end: Timestamp },
}

#[cfg(test)]
#[allow(dead_code)]
mod tests {
    use super::*;
    use crate::domain::source::{GridLocation, IntensitySources};
    use chrono::TimeZone;

    // time interval
    #[test]
    fn time_interval_accepts_very_small_valid_interval() {
        let start = Utc.with_ymd_and_hms(2026, 8, 20, 10, 0, 0).unwrap();
        let end = start + chrono::Duration::nanoseconds(1);

        let interval = TimeInterval::new(start, end).unwrap();

        assert_eq!(interval.start(), &start);
        assert_eq!(interval.end(), &end);
        assert_eq!(interval.duration(), Duration::from_nanos(1));
    }

    // Store creation
    #[test]
    fn create_store_w_sources() {}

    #[test]
    fn create_store_w_many_and_different_sources() {}

    #[test]
    fn create_store_rejects_empty_sources() {
        let result = MeasurementStore::new(Vec::new(), 10);

        assert!(matches!(
            result,
            Err(MeasurementStoreError::NoSourcesFoundUponCreation)
        ));
    }

    // Insert
    #[test]
    fn insert_adds_measurement() {}

    #[test]
    fn insert_rejects_out_of_order_measurements() {}

    #[test]
    fn insert_rejects_unknown_source() {}

    // View
    #[test]
    fn view_interval_w_boundaries() {}
    #[test]
    fn view_interval() {}
    #[test]
    fn view_interval_w_zero_measurements() {}

    // View
    #[test]
    fn view_interval_w_boundaries_w_zero_measurements() {}

    #[test]
    fn view_rejects_unknown_source() {}

    // Delete

    #[test]
    fn delete_before_w_measurements() {}
    fn delete_before_w_no_measurements() {}
    fn delete_before_w_no_source() {}
}
