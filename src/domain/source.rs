use std::hash::{Hash, Hasher};

use crate::domain::providers::{DeviceId, ProviderId};

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum IntensitySources {
    ElectricityMaps{api_key: Option<String>},
    Static,
    LocalizedAverage,
    GlobalAverage,
    Constant,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum PowerSource {
    Nvml,
    Rapl,
    Powermetrics,
    GenericCpuEstimate,
    Static,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Source {
    Power {
        source: PowerSource,
        provider_id: ProviderId,
        device_name: String,
        domain: PowerDomain,
        scope: PowerMeasurementScope,
    },
    Intensity {
        source: IntensitySources,
        location: GridLocation,
    },
}

impl Source {
    pub const fn kind(&self) -> SourceKind {
        match self {
            Self::Power { .. } => SourceKind::Power,
            Self::Intensity { .. } => SourceKind::Intensity,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SourceKind {
    Power,
    Intensity,
}

#[derive(Debug, Clone)]
pub enum GridLocation {
    Zone {
        zone_id: String,
    },

    Country {
        country_code: String,
    },

    DataCenter {
        cloud_provider: String,
        region: String,
    },

    Coordinates {
        latitude: f64,
        longitude: f64,
    },

    Global,
}

impl PartialEq for GridLocation {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Self::Zone { zone_id: left }, Self::Zone { zone_id: right }) => left == right,
            (
                Self::Country { country_code: left },
                Self::Country {
                    country_code: right,
                },
            ) => left == right,
            (
                Self::DataCenter {
                    cloud_provider: left_provider,
                    region: left_region,
                },
                Self::DataCenter {
                    cloud_provider: right_provider,
                    region: right_region,
                },
            ) => left_provider == right_provider && left_region == right_region,
            (
                Self::Coordinates {
                    latitude: left_latitude,
                    longitude: left_longitude,
                },
                Self::Coordinates {
                    latitude: right_latitude,
                    longitude: right_longitude,
                },
            ) => {
                left_latitude.to_bits() == right_latitude.to_bits()
                    && left_longitude.to_bits() == right_longitude.to_bits()
            }
            (Self::Global, Self::Global) => true,
            _ => false,
        }
    }
}

impl Eq for GridLocation {}

impl Hash for GridLocation {
    fn hash<H: Hasher>(&self, state: &mut H) {
        match self {
            Self::Zone { zone_id } => {
                0_u8.hash(state);
                zone_id.hash(state);
            }
            Self::Country { country_code } => {
                1_u8.hash(state);
                country_code.hash(state);
            }
            Self::DataCenter {
                cloud_provider,
                region,
            } => {
                2_u8.hash(state);
                cloud_provider.hash(state);
                region.hash(state);
            }
            Self::Coordinates {
                latitude,
                longitude,
            } => {
                3_u8.hash(state);
                latitude.to_bits().hash(state);
                longitude.to_bits().hash(state);
            }
            Self::Global => 4_u8.hash(state),
        }
    }
}

impl GridLocation {
    pub fn validate(&self) -> Result<(), GridLocationError> {
        match self {
            Self::Zone { zone_id } => {
                if zone_id.trim().is_empty() {
                    return Err(GridLocationError::EmptyZoneId);
                }
            }

            Self::Country { country_code } => {
                let country_code = country_code.trim();

                if country_code.len() != 2
                    || !country_code.bytes().all(|byte| byte.is_ascii_alphabetic())
                {
                    return Err(GridLocationError::InvalidCountryCode {
                        value: country_code.to_owned(),
                    });
                }
            }

            Self::DataCenter {
                cloud_provider,
                region,
            } => {
                if cloud_provider.trim().is_empty() {
                    return Err(GridLocationError::EmptyDataCenterProvider);
                }

                if region.trim().is_empty() {
                    return Err(GridLocationError::EmptyDataCenterRegion);
                }
            }

            Self::Coordinates {
                latitude,
                longitude,
            } => {
                if !latitude.is_finite() || !(-90.0..=90.0).contains(latitude) {
                    return Err(GridLocationError::InvalidLatitude { value: *latitude });
                }

                if !longitude.is_finite() || !(-180.0..=180.0).contains(longitude) {
                    return Err(GridLocationError::InvalidLongitude { value: *longitude });
                }
            }

            Self::Global => {}
        }

        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum GridLocationError {
    #[error("grid zone identifier cannot be empty")]
    EmptyZoneId,

    #[error("country code must contain exactly two ASCII letters, got {value}")]
    InvalidCountryCode { value: String },

    #[error("data-center provider cannot be empty")]
    EmptyDataCenterProvider,

    #[error("data-center region cannot be empty")]
    EmptyDataCenterRegion,

    #[error("latitude must be finite and between -90 and 90, got {value}")]
    InvalidLatitude { value: f64 },

    #[error("longitude must be finite and between -180 and 180, got {value}")]
    InvalidLongitude { value: f64 },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum PowerDomain {
    Cpu,
    Gpu,
    Ram,
    Ane,
    System,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum PowerMeasurementScope {
    DeviceTotal,

    Process { pid: u32 },

    Job { job_id: String },

    Container { container_id: String },
}

