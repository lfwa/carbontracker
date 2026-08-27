use chrono::Duration;
use tokio::{sync::mpsc, task::JoinHandle};

use crate::domain::{
    config::TrackerConfig,
    controller::{Controller, ControllerCommand},
    errors::Error,
    events::{Event, ObserverEvent},
    guard::Guard,
    predictor::Predictor,
    profiler::{Profiler, ProfilerError},
    providers::{ProviderRegisterError, ProviderRegistry, UnresolvedSourcesError, spawn_providers},
    source::Source,
};

pub struct TrackerBuilder {
    config: TrackerConfig,
    provider_registry: ProviderRegistry,
    startup_timeout: Duration,
    command_capacity: usize,
    provider_command_capacity: usize,
    event_capacity: usize,
    provider_output_capacity: usize,
    series_capacity: usize,
    request_capacity: usize,
}

pub struct TrackerRuntime {
    pub command_tx: mpsc::Sender<ControllerCommand>,
    pub out_rx: mpsc::Receiver<Event>,
    controller_task: JoinHandle<Result<(), Error>>,
}

impl TrackerBuilder {
    pub async fn start(self) -> Result<TrackerRuntime, TrackerBuilderError> {
        let Self {
            config,
            provider_registry,
            startup_timeout,
            command_capacity,
            provider_command_capacity,
            event_capacity,
            provider_output_capacity,
            series_capacity,
            request_capacity,
        } = self;

        let TrackerConfig {
            session,
            sampling,
            prediction: prediction_config,
            source_requests,
            guard: guard_config,
            profiler: mut profiler_config,
        } = config;

        let providers = provider_registry.resolve(&source_requests).await?;

        let (resolutions, registrations) = providers.into_parts();

        resolutions.valid()?;

        let predictor = prediction_config.map(Predictor::new);
        let guard = guard_config.map(Guard::new);
        let sources: Vec<Source> = registrations
            .iter()
            .flat_map(|provider| provider.metadata.sources.values().cloned())
            .collect();

        let request_timeout = sampling
            .request_timeout
            .to_std()
            .map_err(|_| TrackerBuilderError::InvalidRequestTimeout)?;

        if request_timeout.is_zero() {
            return Err(TrackerBuilderError::InvalidRequestTimeout);
        }

        profiler_config.series_capacity = series_capacity;
        profiler_config.request_capacity = request_capacity;

        let profiler = Profiler::new(
            profiler_config,
            sources,
            predictor,
            guard,
        )?;

        let (command_tx, command_rx) = mpsc::channel::<ControllerCommand>(command_capacity);

        let (out_tx, out_rx) = mpsc::channel::<Event>(command_capacity);

        let provider_runtime = spawn_providers(
            registrations,
            provider_command_capacity,
            provider_output_capacity,
        );

        let controller = Controller::new(
            command_rx,
            out_tx,
            provider_runtime,
            profiler,
            request_timeout,
        );

        let controller_task = tokio::spawn(async move {
            // `controller` is now owned by this task.
            controller.run_tracker().await
        });

        Ok(TrackerRuntime {
            command_tx: command_tx,
            out_rx: out_rx,
            controller_task: controller_task,
        })
    }
}

#[derive(Debug, thiserror::Error)]
pub enum TrackerBuilderError {
    #[error(transparent)]
    ProviderRegistration(#[from] ProviderRegisterError),
    #[error(transparent)]
    UnresolvedSources(#[from] UnresolvedSourcesError),
    #[error("provider request timeout must be positive")]
    InvalidRequestTimeout,
    #[error(transparent)]
    Profiler(#[from] ProfilerError),
}
