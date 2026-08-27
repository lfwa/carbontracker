use std::{path::PathBuf, thread::scope};

use chrono::Duration;

use crate::domain::{
    self,
    guard::GuardConfig,
    predictor::{PredictionStart, PredictionTarget},
    profiler::ProfilerConfig,
    source::{GridLocation, IntensitySources, PowerDomain, PowerMeasurementScope},
};

#[derive(Debug, Clone)]
pub struct TrackerConfig {
    pub session: SessionConfig,
    pub sampling: SamplingConfig,
    pub prediction: Option<PredictionConfig>,
    pub source_requests: Vec<SourceRequest>,
    pub guard: Option<GuardConfig>,
    pub profiler: ProfilerConfig,
}

impl Default for TrackerConfig {
    fn default() -> Self {
        Self {
            session: SessionConfig::default(),
            source_requests: vec![
                SourceRequest::Power(PowerSourceRequest::new(
                    PowerDomain::System,
                    PowerMeasurementScope::DeviceTotal,
                )),
                SourceRequest::Power(PowerSourceRequest::new(
                    PowerDomain::Gpu,
                    PowerMeasurementScope::DeviceTotal,
                )),
                SourceRequest::Power(PowerSourceRequest::new(
                    PowerDomain::Cpu,
                    PowerMeasurementScope::DeviceTotal,
                )),
                SourceRequest::Power(PowerSourceRequest::new(
                    PowerDomain::Ram,
                    PowerMeasurementScope::DeviceTotal,
                )),
                SourceRequest::Intensity(IntensitySourceRequest::default()),
            ],
            sampling: SamplingConfig::default(),
            prediction: None,
            guard: None,
            profiler: ProfilerConfig::default(),
        }
    }
}

impl TrackerConfig {
    pub fn new(project_name: impl Into<String>) -> Self {
        Self {
            session: SessionConfig {
                project_name: project_name.into(),
                ..SessionConfig::default()
            },
            ..Self::default()
        }
    }
}

#[derive(Debug, Clone)]
pub struct SamplingConfig {
    pub power_interval: Duration,
    pub intensity_interval: Duration,
    pub statistics_interval: Duration,
    pub request_timeout: Duration,
}

impl Default for SamplingConfig {
    fn default() -> Self {
        Self {
            power_interval: Duration::seconds(1),
            intensity_interval: Duration::minutes(15),
            statistics_interval: Duration::seconds(5),
            request_timeout: Duration::seconds(30),
        }
    }
}

#[derive(Debug, Clone)]
pub struct SessionConfig {
    pub project_name: String,
    pub run_name: Option<String>,
    pub log_directory: PathBuf,
    pub pue: f64,
}

impl Default for SessionConfig {
    fn default() -> Self {
        Self {
            project_name: "carbontracker".to_owned(),
            run_name: None,
            log_directory: PathBuf::from("carbontracker_logs"),
            pue: 1.0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FailurePolicy {
    Strict,
    BestEffort,
}

impl Default for FailurePolicy {
    fn default() -> Self {
        Self::BestEffort
    }
}

#[derive(Debug, Clone)]
pub struct PredictionConfig {
    pub target: PredictionTarget,
    pub start_after: PredictionStart,
    pub update_interval: Option<Duration>,
}

impl PredictionConfig {
    pub fn for_units(total: usize, unit_name: impl Into<String>) -> Self {
        Self {
            target: PredictionTarget::Units {
                total,
                unit_name: unit_name.into(),
            },
            start_after: PredictionStart::AfterUnits(1),
            update_interval: Some(Duration::seconds(30)),
        }
    }

    pub fn for_duration(duration: Duration) -> Self {
        Self {
            target: PredictionTarget::Duration(duration),
            start_after: PredictionStart::AfterDuration(Duration::minutes(1)),
            update_interval: Some(Duration::seconds(30)),
        }
    }
}

#[derive(Debug, Clone)]
pub struct PowerSourceRequest {
    domain: PowerDomain,
    scope: PowerMeasurementScope,
}

impl PowerSourceRequest {
    pub fn new(domain: PowerDomain, scope: PowerMeasurementScope) -> Self {
        Self { domain, scope }
    }

    pub fn domain(&self) -> PowerDomain {
        self.domain
    }

    pub fn scope(&self) -> &PowerMeasurementScope {
        &self.scope
    }
}

#[derive(Debug, Clone)]
pub struct IntensitySourceRequest {
    method: IntensitySources,
    location: Option<GridLocation>,
}

impl IntensitySourceRequest {
    pub fn new(method: IntensitySources, location: Option<GridLocation>) -> Self {
        Self { method, location }
    }

    pub fn method(&self) -> &IntensitySources {
        &self.method
    }

    pub fn location(&self) -> Option<&GridLocation> {
        self.location.as_ref()
    }
}

impl Default for IntensitySourceRequest {
    fn default() -> Self {
        Self {
            method: IntensitySources::GlobalAverage,
            location: Some(GridLocation::Global),
        }
    }
}

#[derive(Debug, Clone)]
pub enum SourceRequest {
    Power(PowerSourceRequest),
    Intensity(IntensitySourceRequest),
}
