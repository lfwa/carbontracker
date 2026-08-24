use chrono::Utc;

use crate::domain::{
    measurements::{
        self, ProviderMeasurement, MeasurementQuality, PowerDomain, PowerMeasurement, PowerMeasurementScope,
    },
    providers::{ProviderError, ProviderState},
    units::Watts,
};

use crate::application::ports::providers::Provider;

pub struct StaticPowerProvider {
    watts: Watts,
    device_id: String,
    domain: PowerDomain,
    scope: PowerMeasurementScope,
    quality: MeasurementQuality,
    state: ProviderState,
}

impl Provider for StaticPowerProvider {
    async fn fetch(&mut self) -> Result<ProviderMeasurement, ProviderError> {
        let fetched_at = Utc::now();
        let measurement = ProviderMeasurement::Power(PowerMeasurement {
            observed_at: fetched_at,
            provider: crate::domain::providers::PowerProviderType::Static,
            device_id: self.device_id.clone(),
            domain: self.domain,
            scope: self.scope.clone(),
            value: measurements::PowerValue::Instantaneous { watts: self.watts },
            quality: self.quality,
        });

        self.state.record_fetch(fetched_at, measurement.clone());
        Ok(measurement)
    }

    fn name(&self) -> &str {
        "static-power"
    }

    fn state(&self) -> &ProviderState {
        &self.state
    }
}
