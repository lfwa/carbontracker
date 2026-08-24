use std::fmt;
use std::time::Duration;

use crate::domain::measurements::Timestamp;

const JOULES_PER_KILOWATT_HOUR: f64 = 3_600_000.0;
const MILLIWATTS_PER_WATT: f64 = 1_000.0;
const MICROJOULES_PER_JOULE: f64 = 1_000_000.0;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TimeInterval {
    pub start: Timestamp,
    pub end: Timestamp,
}

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum UnitError {
    #[error("{unit} must be finite, got {value}")]
    NonFinite { unit: &'static str, value: f64 },

    #[error("{unit} must be nonnegative, got {value}")]
    Negative { unit: &'static str, value: f64 },

    #[error("{unit} arithmetic produced an invalid value: {value}")]
    ArithmeticOverflow { unit: &'static str, value: f64 },

    #[error("PUE must be at least 1.0, got {value}")]
    InvalidPue { value: f64 },
}

fn validate_nonnegative_finite(unit: &'static str, value: f64) -> Result<f64, UnitError> {
    if !value.is_finite() {
        return Err(UnitError::NonFinite { unit, value });
    }

    if value < 0.0 {
        return Err(UnitError::Negative { unit, value });
    }

    Ok(value)
}

macro_rules! nonnegative_unit {
    (
        $(#[$meta:meta])*
        $name:ident,
        unit = $unit:literal,
        symbol = $symbol:literal
    ) => {
        $(#[$meta])*
        #[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
        pub struct $name(f64);

        impl $name {
            pub const ZERO: Self = Self(0.0);

            pub fn new(value: f64) -> Result<Self, UnitError> {
                Ok(Self(validate_nonnegative_finite($unit, value)?))
            }

            pub const fn zero() -> Self {
                Self::ZERO
            }

            pub const fn get(self) -> f64 {
                self.0
            }

            pub fn is_zero(self) -> bool {
                self.0 == 0.0
            }

            pub fn checked_add(self, other: Self) -> Result<Self, UnitError> {
                let value = self.0 + other.0;

                if !value.is_finite() {
                    return Err(UnitError::ArithmeticOverflow {
                        unit: $unit,
                        value,
                    });
                }

                Ok(Self(value))
            }

            pub fn checked_sub(self, other: Self) -> Result<Self, UnitError> {
                Self::new(self.0 - other.0)
            }

            pub fn saturating_sub(self, other: Self) -> Self {
                Self((self.0 - other.0).max(0.0))
            }

            pub fn checked_mul(self, factor: f64) -> Result<Self, UnitError> {
                Self::new(self.0 * factor)
            }

            pub fn checked_div(self, divisor: f64) -> Result<Self, UnitError> {
                Self::new(self.0 / divisor)
            }
        }

        impl Default for $name {
            fn default() -> Self {
                Self::ZERO
            }
        }

        impl fmt::Display for $name {
            fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                write!(formatter, "{} {}", self.0, $symbol)
            }
        }

        impl TryFrom<f64> for $name {
            type Error = UnitError;

            fn try_from(value: f64) -> Result<Self, Self::Error> {
                Self::new(value)
            }
        }

        impl From<$name> for f64 {
            fn from(value: $name) -> Self {
                value.get()
            }
        }
    };
}

nonnegative_unit!(
    /// Instantaneous power in watts.
    Watts,
    unit = "watts",
    symbol = "W"
);

nonnegative_unit!(
    /// Energy in joules.
    Joules,
    unit = "joules",
    symbol = "J"
);

nonnegative_unit!(
    /// Energy in kilowatt-hours.
    KilowattHours,
    unit = "kilowatt-hours",
    symbol = "kWh"
);

nonnegative_unit!(
    /// Carbon emissions in grams of CO2 equivalent.
    GramsCo2e,
    unit = "grams CO2e",
    symbol = "gCO2e"
);

nonnegative_unit!(
    /// Carbon intensity in grams of CO2 equivalent per kilowatt-hour.
    GramsCo2ePerKwh,
    unit = "grams CO2e per kilowatt-hour",
    symbol = "gCO2e/kWh"
);

impl Watts {
    pub fn from_milliwatts(milliwatts: f64) -> Result<Self, UnitError> {
        Self::new(milliwatts / MILLIWATTS_PER_WATT)
    }

    pub fn as_milliwatts(self) -> f64 {
        self.0 * MILLIWATTS_PER_WATT
    }

    pub fn energy_over(self, duration: Duration) -> Result<Joules, UnitError> {
        Joules::new(self.0 * duration.as_secs_f64())
    }
}

impl Joules {
    pub fn from_microjoules(microjoules: f64) -> Result<Self, UnitError> {
        Self::new(microjoules / MICROJOULES_PER_JOULE)
    }

    pub fn as_microjoules(self) -> f64 {
        self.0 * MICROJOULES_PER_JOULE
    }

    pub fn to_kilowatt_hours(self) -> KilowattHours {
        KilowattHours(self.0 / JOULES_PER_KILOWATT_HOUR)
    }
}

impl KilowattHours {
    pub fn to_joules(self) -> Result<Joules, UnitError> {
        Joules::new(self.0 * JOULES_PER_KILOWATT_HOUR)
    }

    pub fn emissions_at(self, intensity: GramsCo2ePerKwh) -> Result<GramsCo2e, UnitError> {
        GramsCo2e::new(self.0 * intensity.get())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
pub struct PowerUsageEffectiveness(f64);

impl PowerUsageEffectiveness {
    pub const IDEAL: Self = Self(1.0);

    pub fn new(value: f64) -> Result<Self, UnitError> {
        if !value.is_finite() {
            return Err(UnitError::NonFinite { unit: "PUE", value });
        }

        if value < 1.0 {
            return Err(UnitError::InvalidPue { value });
        }

        Ok(Self(value))
    }

    pub const fn ideal() -> Self {
        Self::IDEAL
    }

    pub const fn get(self) -> f64 {
        self.0
    }

    pub fn apply_to_energy(self, energy: KilowattHours) -> Result<KilowattHours, UnitError> {
        energy.checked_mul(self.0)
    }
}

impl Default for PowerUsageEffectiveness {
    fn default() -> Self {
        Self::IDEAL
    }
}

impl fmt::Display for PowerUsageEffectiveness {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{} PUE", self.0)
    }
}
