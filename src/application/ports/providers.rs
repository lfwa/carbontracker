use crate::domain::{
    config::SourceRequest,
    measurements::MeasurementSample,
    providers::{ProviderError, ProviderRegistration, ProviderState, ProviderUnsupportedReason},
};

#[async_trait::async_trait]
pub trait Provider: Send {
    async fn fetch(&mut self) -> Result<Vec<MeasurementSample>, ProviderError>;
    fn name(&self) -> &str;
    fn state(&self) -> &ProviderState;
}

#[async_trait::async_trait]
pub trait ProviderFactory: Send + Sync {
    fn name(&self) -> &'static str;
    async fn supports(&self, request: &SourceRequest) -> Result<(), ProviderUnsupportedReason>;
    async fn create(
        &self,
        requests: &[SourceRequest],
    ) -> Result<ProviderRegistration, ProviderError>;
}
