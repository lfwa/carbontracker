use chrono::Utc;

use crate::{
    application::ports::providers::Provider,
    domain::{
        measurements::{GridLocation, IntensityMeasurement, ProviderMeasurement, MeasurementQuality},
        providers::{IntensityProviderType, ProviderError, ProviderState},
        units::GramsCo2ePerKwh,
    },
};

pub struct StaticIntensityProvider {
    carbon_intensity: GramsCo2ePerKwh,
    location: GridLocation,
    state: ProviderState,
}

impl StaticIntensityProvider {
    pub fn new(carbon_intensity: GramsCo2ePerKwh, location: GridLocation) -> Self {
        Self {
            carbon_intensity,
            location,
            state: ProviderState::default(),
        }
    }
}

impl Provider for StaticIntensityProvider {
    async fn fetch(&mut self) -> Result<ProviderMeasurement, ProviderError> {
        let fetched_at = Utc::now();
        let measurement = ProviderMeasurement::Intensity(IntensityMeasurement {
            observed_at: fetched_at,
            provider: IntensityProviderType::Static,
            location: self.location.clone(),
            carbon_intensity: self.carbon_intensity,
            quality: MeasurementQuality::DefaultValue,
        });

        self.state.record_fetch(fetched_at, measurement.clone());
        Ok(measurement)
    }

    fn name(&self) -> &str {
        "static-intensity"
    }

    fn state(&self) -> &ProviderState {
        &self.state
    }
}
