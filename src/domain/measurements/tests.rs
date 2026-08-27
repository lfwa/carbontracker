use super::*;
use crate::domain::{
    providers::ProviderId,
    source::{GridLocation, IntensitySources, PowerDomain, PowerMeasurementScope, PowerSource},
};
use chrono::TimeZone;

const SERIES_CAPACITY: usize = 2;

fn timestamp(seconds: i64) -> Timestamp {
    Utc.with_ymd_and_hms(2026, 8, 20, 10, 0, 0).unwrap() + chrono::Duration::seconds(seconds)
}

fn intensity_source(name: &str) -> Source {
    Source::Intensity {
        source: IntensitySources::Static,
        location: GridLocation::Zone {
            zone_id: name.to_owned(),
        },
    }
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

fn store(sources: Vec<Source>) -> MeasurementStore {
    MeasurementStore::new(sources, SERIES_CAPACITY).unwrap()
}

fn source_key(store: &MeasurementStore, source: &Source) -> SourceKey {
    *store.sources.get(source).unwrap()
}

fn sample(source_key: SourceKey, seconds: i64, value: f64) -> MeasurementSample {
    MeasurementSample {
        source_key,
        measurement: Measurement::new(timestamp(seconds), value),
    }
}

fn insert_samples(store: &mut MeasurementStore, source_key: SourceKey, samples: &[(i64, f64)]) {
    for &(seconds, value) in samples {
        store.insert(sample(source_key, seconds, value)).unwrap();
    }
}

fn collected_values<'a>(measurements: impl Iterator<Item = &'a Measurement>) -> Vec<f64> {
    measurements.map(Measurement::value).collect()
}

fn interval(start_seconds: i64, end_seconds: i64) -> TimeInterval {
    TimeInterval::new(timestamp(start_seconds), timestamp(end_seconds)).unwrap()
}

#[test]
fn time_interval_accepts_very_small_valid_interval() {
    let start = timestamp(0);
    let end = start + chrono::Duration::nanoseconds(1);

    let interval = TimeInterval::new(start, end).unwrap();

    assert_eq!(interval.start(), &start);
    assert_eq!(interval.end(), &end);
    assert_eq!(interval.duration(), Duration::from_nanos(1));
}

#[test]
fn time_interval_rejects_equal_start_and_end() {
    let time = timestamp(0);

    assert_eq!(
        TimeInterval::new(time, time),
        Err(TimeIntervalError::EndNotAfterStart {
            start: time,
            end: time,
        })
    );
}

#[test]
fn time_interval_rejects_end_before_start_and_reports_both_timestamps() {
    let start = timestamp(2);
    let end = timestamp(1);

    let error = TimeInterval::new(start, end).unwrap_err();
    let message = error.to_string();

    assert_eq!(error, TimeIntervalError::EndNotAfterStart { start, end });
    assert!(message.contains(&start.to_string()));
    assert!(message.contains(&end.to_string()));
}

#[test]
fn create_store_registers_source_with_empty_series() {
    let source = intensity_source("DK-DK1");
    let store = store(vec![source.clone()]);
    let key = source_key(&store, &source);

    assert_eq!(key, SourceKey(0));
    assert_eq!(store.sources.len(), 1);
    assert_eq!(store.series.len(), 1);
    assert!(store.series[key.index()].is_empty());
}

#[test]
fn create_store_registers_mixed_sources_with_distinct_series() {
    let power = power_source(3, "cpu-0");
    let intensity = intensity_source("DK-DK2");
    let store = store(vec![power.clone(), intensity.clone()]);
    let power_key = source_key(&store, &power);
    let intensity_key = source_key(&store, &intensity);

    assert_ne!(power_key, intensity_key);
    assert_eq!(store.series.len(), 2);
    assert!(store.series[power_key.index()].is_empty());
    assert!(store.series[intensity_key.index()].is_empty());
}

#[test]
fn create_store_rejects_empty_sources() {
    assert!(matches!(
        MeasurementStore::new(Vec::new(), SERIES_CAPACITY),
        Err(MeasurementStoreError::NoSourcesFoundUponCreation)
    ));
}

#[test]
fn create_store_rejects_duplicate_sources() {
    let source = intensity_source("DK-DK1");

    assert!(matches!(
        MeasurementStore::new(vec![source.clone(), source], SERIES_CAPACITY),
        Err(MeasurementStoreError::DuplicateSource)
    ));
}

#[test]
fn insert_preserves_ordered_measurements() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);

    insert_samples(&mut store, key, &[(1, 10.0), (2, 20.0), (3, 30.0)]);

    assert_eq!(
        collected_values(store.view(key).unwrap()),
        vec![10.0, 20.0, 30.0]
    );
}

#[test]
fn insert_accepts_equal_timestamps_in_insertion_order() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);

    insert_samples(&mut store, key, &[(1, 10.0), (1, 11.0), (1, 12.0)]);

    assert_eq!(
        collected_values(store.view(key).unwrap()),
        vec![10.0, 11.0, 12.0]
    );
}

#[test]
fn insert_rejects_older_measurement_without_mutating_series() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(2, 20.0)]);

    let result = store.insert(sample(key, 1, 10.0));

    assert_eq!(result, Err(MeasurementStoreError::MeasurementsOutOfOrder));
    assert_eq!(collected_values(store.view(key).unwrap()), vec![20.0]);
}

#[test]
fn insert_enforces_order_independently_per_source() {
    let first = intensity_source("DK-DK1");
    let second = intensity_source("DK-DK2");
    let mut store = store(vec![first.clone(), second.clone()]);
    let first_key = source_key(&store, &first);
    let second_key = source_key(&store, &second);
    insert_samples(&mut store, first_key, &[(10, 10.0)]);

    assert_eq!(store.insert(sample(second_key, 1, 1.0)), Ok(()));
    assert_eq!(collected_values(store.view(second_key).unwrap()), vec![1.0]);
}

#[test]
fn insert_rejects_unknown_source_key() {
    let mut store = store(vec![intensity_source("DK-DK1")]);

    assert_eq!(
        store.insert(sample(SourceKey(usize::MAX), 1, 10.0)),
        Err(MeasurementStoreError::UnknownSourceKey)
    );
}

#[test]
fn insert_grows_beyond_initial_series_capacity() {
    let source = intensity_source("DK-DK1");
    let mut store = MeasurementStore::new(vec![source.clone()], 1).unwrap();
    let key = source_key(&store, &source);

    insert_samples(&mut store, key, &[(1, 10.0), (2, 20.0), (3, 30.0)]);

    assert_eq!(store.series[key.index()].len(), 3);
}

#[test]
fn view_returns_every_measurement() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(1, 10.0), (2, 20.0), (3, 30.0)]);

    assert_eq!(
        collected_values(store.view(key).unwrap()),
        vec![10.0, 20.0, 30.0]
    );
}

#[test]
fn view_returns_empty_for_unused_registered_source() {
    let source = intensity_source("DK-DK1");
    let store = store(vec![source.clone()]);
    let key = source_key(&store, &source);

    assert_eq!(store.view(key).unwrap().count(), 0);
}

#[test]
fn view_rejects_unknown_source_key() {
    let store = store(vec![intensity_source("DK-DK1")]);

    assert!(matches!(
        store.view(SourceKey(usize::MAX)),
        Err(MeasurementStoreError::UnknownSourceKey)
    ));
}

#[test]
fn view_interval_includes_exact_endpoints_without_exterior_samples() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(
        &mut store,
        key,
        &[(0, 0.0), (1, 10.0), (2, 20.0), (3, 30.0)],
    );

    let values = collected_values(store.view_interval(key, &interval(1, 2), false).unwrap());

    assert_eq!(values, vec![10.0, 20.0]);
}

#[test]
fn view_interval_adds_both_neighbors_when_boundaries_are_enabled() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(
        &mut store,
        key,
        &[(0, 0.0), (1, 10.0), (2, 20.0), (3, 30.0)],
    );

    let values = collected_values(store.view_interval(key, &interval(1, 2), true).unwrap());

    assert_eq!(values, vec![0.0, 10.0, 20.0, 30.0]);
}

#[test]
fn view_interval_returns_empty_for_gap_without_boundaries() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(0, 0.0), (3, 30.0)]);

    assert_eq!(
        store
            .view_interval(key, &interval(1, 2), false)
            .unwrap()
            .count(),
        0
    );
}

#[test]
fn view_interval_returns_surrounding_samples_for_gap_with_boundaries() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(0, 0.0), (3, 30.0)]);

    let values = collected_values(store.view_interval(key, &interval(1, 2), true).unwrap());

    assert_eq!(values, vec![0.0, 30.0]);
}

#[test]
fn view_interval_handles_missing_predecessor_at_series_start() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(1, 10.0), (2, 20.0), (3, 30.0)]);

    let values = collected_values(store.view_interval(key, &interval(0, 2), true).unwrap());

    assert_eq!(values, vec![10.0, 20.0, 30.0]);
}

#[test]
fn view_interval_handles_missing_successor_at_series_end() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(0, 0.0), (1, 10.0), (2, 20.0)]);

    let values = collected_values(store.view_interval(key, &interval(1, 3), true).unwrap());

    assert_eq!(values, vec![0.0, 10.0, 20.0]);
}

#[test]
fn view_interval_returns_empty_for_empty_registered_series() {
    let source = intensity_source("DK-DK1");
    let store = store(vec![source.clone()]);
    let key = source_key(&store, &source);

    assert_eq!(
        store
            .view_interval(key, &interval(1, 2), false)
            .unwrap()
            .count(),
        0
    );
    assert_eq!(
        store
            .view_interval(key, &interval(1, 2), true)
            .unwrap()
            .count(),
        0
    );
}

#[test]
fn view_interval_rejects_unknown_source_key() {
    let store = store(vec![intensity_source("DK-DK1")]);

    assert!(matches!(
        store.view_interval(SourceKey(usize::MAX), &interval(1, 2), false),
        Err(MeasurementStoreError::UnknownSourceKey)
    ));
}

#[test]
fn delete_before_cutoff_between_samples_keeps_predecessor_and_newer_per_source() {
    let first = intensity_source("DK-DK1");
    let second = intensity_source("DK-DK2");
    let mut store = store(vec![first.clone(), second.clone()]);
    let first_key = source_key(&store, &first);
    let second_key = source_key(&store, &second);
    insert_samples(&mut store, first_key, &[(0, 0.0), (2, 2.0), (4, 4.0)]);
    insert_samples(&mut store, second_key, &[(1, 10.0), (3, 30.0), (5, 50.0)]);

    store.delete_before(Some(&timestamp(3)));

    assert_eq!(
        collected_values(store.view(first_key).unwrap()),
        vec![2.0, 4.0]
    );
    assert_eq!(
        collected_values(store.view(second_key).unwrap()),
        vec![10.0, 30.0, 50.0]
    );
}

#[test]
fn delete_before_exact_sample_keeps_predecessor_exact_sample_and_newer() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(0, 0.0), (2, 20.0), (4, 40.0)]);

    store.delete_before(Some(&timestamp(2)));

    assert_eq!(
        collected_values(store.view(key).unwrap()),
        vec![0.0, 20.0, 40.0]
    );
}

#[test]
fn delete_before_cutoff_before_first_sample_is_no_op() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(1, 10.0), (2, 20.0)]);

    store.delete_before(Some(&timestamp(0)));

    assert_eq!(collected_values(store.view(key).unwrap()), vec![10.0, 20.0]);
}

#[test]
fn delete_before_cutoff_after_all_samples_keeps_latest_sample() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(1, 10.0), (2, 20.0), (3, 30.0)]);

    store.delete_before(Some(&timestamp(4)));

    assert_eq!(collected_values(store.view(key).unwrap()), vec![30.0]);
}

#[test]
fn delete_before_without_cutoff_keeps_latest_sample() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);
    insert_samples(&mut store, key, &[(1, 10.0), (2, 20.0), (3, 30.0)]);

    store.delete_before(None);

    assert_eq!(collected_values(store.view(key).unwrap()), vec![30.0]);
}

#[test]
fn delete_before_empty_registered_series_is_no_op() {
    let source = intensity_source("DK-DK1");
    let mut store = store(vec![source.clone()]);
    let key = source_key(&store, &source);

    store.delete_before(Some(&timestamp(1)));

    assert_eq!(store.view(key).unwrap().count(), 0);
}

#[test]
fn delete_before_with_no_sources_is_no_op() {
    let mut store = MeasurementStore {
        sources: HashMap::new(),
        series: Vec::new(),
    };

    store.delete_before(Some(&timestamp(1)));

    assert!(store.sources.is_empty());
    assert!(store.series.is_empty());
}
