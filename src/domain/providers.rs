use std::collections::HashMap;
use std::time::Duration;

use std::sync::{
    Arc,
    atomic::{AtomicU8, Ordering},
};

use tokio::sync::mpsc;
use tokio::task::JoinHandle;
use tokio::time::{Instant, MissedTickBehavior};

use crate::application::ports::providers::{Provider, ProviderFactory};
use crate::domain::config::SourceRequest;
use crate::domain::measurements::{MeasurementSample, SourceKey, Timestamp};
use crate::domain::request::RequestId;
use crate::domain::source::{Source, SourceKind};

pub type ProviderReceiver = mpsc::Receiver<ProviderOutput>;
pub type ProviderReciever = ProviderReceiver;
pub type ProviderOutputSender = mpsc::Sender<ProviderOutput>;
pub type ProviderCommandReceiver = mpsc::Receiver<ProviderCommand>;
pub type ProviderSender = mpsc::Sender<ProviderCommand>;

#[derive(Debug, Clone)]
pub struct ProviderMetaData {
    pub sampling_interval: Duration,
    pub minimal_interval: Duration,
    pub fetch_on_start: bool,
    pub provider_id: ProviderId,
    pub sources: HashMap<SourceKey, Source>,
}

#[derive(Debug)]
pub struct ProviderOutput {
    pub provider_id: ProviderId,
    pub request_id: Option<RequestId>,
    pub result: Result<Vec<MeasurementSample>, ProviderError>,
}

#[derive(Debug, Default)]
pub struct ProviderState {
    last_fetch_at: Option<Timestamp>,
    last_output: Option<ProviderOutput>,
    enabled: bool,
}

impl ProviderState {
    pub fn record_fetch(&mut self, fetched_at: Timestamp, output: ProviderOutput) {
        self.last_output = Some(output);
        self.last_fetch_at = Some(fetched_at);
    }

    pub fn last_fetch_at(&self) -> Option<&Timestamp> {
        self.last_fetch_at.as_ref()
    }

    pub fn last_output(&self) -> Option<&ProviderOutput> {
        self.last_output.as_ref()
    }
}

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum ProviderError {
    #[error("fetch failed")]
    Fetch,
    #[error("provider {provider_id:?} command stream closed: {error}")]
    CommandStreamClosed {
        provider_id: ProviderId,
        error: String,
    },
    #[error("provider {provider_id:?} command queue is full")]
    CommandQueueFull { provider_id: ProviderId },
    #[error("provider {provider_id:?} timed out for request {request_id:?}")]
    RequestTimedOut {
        provider_id: ProviderId,
        request_id: RequestId,
    },
    #[error("Invalid permissions")]
    InvalidPermissions,
    #[error("Shutdown Failed")]
    Shutdown,
}

pub struct ProviderRegistration {
    pub metadata: ProviderMetaData,
    pub provider: Box<dyn Provider>,
}

// Used to gaurantee measurements for spans. A Ticket is simply the object, that allows us to track certain measurements, such that the profiler, cant await ticket completions, before doing span profiling
#[derive(Debug, Clone, PartialEq)]
pub enum ProviderRequestState {
    Pending,
    Succeeded,
    Failed(ProviderError),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct SourceRequestId(usize);

impl SourceRequestId {
    pub fn index(self) -> usize {
        self.0
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct FactoryId(usize);

impl FactoryId {
    pub fn index(self) -> usize {
        self.0
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ProviderId(usize);

impl ProviderId {
    pub const fn new(value: usize) -> Self {
        Self(value)
    }

    pub const fn index(self) -> usize {
        self.0
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct DeviceId(usize);

pub enum ProviderCommand {
    SampleNow { request_id: RequestId },
    Shutdown,
}

// Generic provider commander, used to group the providers into a common type
pub struct ProviderCommander {
    pub provider_id: ProviderId,
    pub command_tx: ProviderSender,
}

pub struct ProviderRuntime {
    pub providers: Vec<ProviderCommander>,
    pub(crate) output_rx: ProviderReceiver,
    pub(crate) tasks: Vec<JoinHandle<()>>,
}

#[derive(Debug, thiserror::Error)]
pub enum ProviderRuntimeError {
    #[error("provider task failed to join: {0}")]
    TaskJoin(#[from] tokio::task::JoinError),
}

impl ProviderRuntime {
    pub fn sample_all(&self, request_id: RequestId) -> HashMap<ProviderId, ProviderRequestState> {
        let mut request_states = HashMap::with_capacity(self.providers.len());

        for provider in &self.providers {
            let command = ProviderCommand::SampleNow { request_id };

            let state = match provider.command_tx.try_send(command) {
                Ok(()) => ProviderRequestState::Pending,
                Err(mpsc::error::TrySendError::Full(_)) => {
                    ProviderRequestState::Failed(ProviderError::CommandQueueFull {
                        provider_id: provider.provider_id,
                    })
                }
                Err(error @ mpsc::error::TrySendError::Closed(_)) => {
                    ProviderRequestState::Failed(ProviderError::CommandStreamClosed {
                        provider_id: provider.provider_id,
                        error: error.to_string(),
                    })
                }
            };

            request_states.insert(provider.provider_id, state);
        }

        request_states
    }
}

pub fn spawn_providers(
    registrations: Vec<ProviderRegistration>,
    provider_command_capacity: usize,
    provider_output_capacity: usize,
) -> ProviderRuntime {
    let (provider_output_tx, provider_output_rx) = mpsc::channel(provider_output_capacity);

    let mut provider_commanders = Vec::with_capacity(registrations.len());
    let mut provider_tasks = Vec::with_capacity(registrations.len());

    for registration in registrations {
        let provider_id = registration.metadata.provider_id;

        let (provider_command_tx, provider_command_rx) = mpsc::channel(provider_command_capacity);

        provider_commanders.push(ProviderCommander {
            provider_id,
            command_tx: provider_command_tx,
        });

        provider_tasks.push(tokio::spawn(run_provider(
            registration,
            provider_command_rx,
            provider_output_tx.clone(),
        )));
    }

    drop(provider_output_tx);

    ProviderRuntime {
        providers: provider_commanders,
        output_rx: provider_output_rx,
        tasks: provider_tasks,
    }
}
pub async fn run_provider(
    mut registration: ProviderRegistration,
    mut command_receiver: ProviderCommandReceiver,
    output_sender: ProviderOutputSender,
) {
    let provider_id = registration.metadata.provider_id;
    let sampling_interval = registration.metadata.sampling_interval;

    let first_sample = if registration.metadata.fetch_on_start {
        Instant::now()
    } else {
        Instant::now() + sampling_interval
    };

    let mut ticker = tokio::time::interval_at(first_sample, sampling_interval);
    ticker.set_missed_tick_behavior(MissedTickBehavior::Skip);

    loop {
        tokio::select! {
            _ = ticker.tick() => {
                let output = ProviderOutput {
                    provider_id,
                    request_id: None,
                    result: registration.provider.fetch().await,
                };

                // If there is no reciever, break the loop
                if output_sender.send(output).await.is_err() {
                    break;
                }

            }
            command = command_receiver.recv() => {
                match command {
                    Some(ProviderCommand::SampleNow { request_id }) => {
                        let output = ProviderOutput {
                            provider_id,
                            request_id: Some(request_id),
                            result: registration.provider.fetch().await,
                        };

                        if output_sender.send(output).await.is_err() {
                            break;
                        }
                    }
                    Some(ProviderCommand::Shutdown) | None => {
                        break;
                    }
                }
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ProviderUnsupportedReason {
    #[error("permissions denied")]
    PermissionsDenied,
    #[error("source type is not supported")]
    SourceType,
    #[error("API key is missing or invalid")]
    ApiKey,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnsupportedFactory {
    pub factory_id: FactoryId,
    pub factory_name: String,
    pub reason: ProviderUnsupportedReason,
}

#[derive(Debug, Clone)]
pub struct SourceResolution {
    source_request_id: SourceRequestId,
    source_request: SourceRequest,
    chosen_factory: Option<FactoryId>,
    compatible_factories: Vec<FactoryId>,
    unsupported_factories: Vec<UnsupportedFactory>,
}

impl SourceResolution {
    pub fn new(source_request_id: SourceRequestId, source_request: SourceRequest) -> Self {
        Self {
            source_request_id,
            source_request,
            chosen_factory: None,
            compatible_factories: Vec::new(),
            unsupported_factories: Vec::new(),
        }
    }

    pub fn add_compatible(&mut self, factory_id: FactoryId) {
        self.compatible_factories.push(factory_id);
        self.chosen_factory = Some(factory_id);
    }

    pub fn add_unsupported(
        &mut self,
        factory_id: FactoryId,
        factory_name: impl Into<String>,
        reason: ProviderUnsupportedReason,
    ) {
        self.unsupported_factories.push(UnsupportedFactory {
            factory_id,
            factory_name: factory_name.into(),
            reason,
        });
    }

    pub fn source_request_id(&self) -> SourceRequestId {
        self.source_request_id
    }

    pub fn source_request(&self) -> &SourceRequest {
        &self.source_request
    }

    pub fn chosen_factory(&self) -> Option<FactoryId> {
        self.chosen_factory
    }

    pub fn compatible_factories(&self) -> &[FactoryId] {
        &self.compatible_factories
    }

    pub fn unsupported_factories(&self) -> &[UnsupportedFactory] {
        &self.unsupported_factories
    }

    pub fn is_resolved(&self) -> bool {
        self.chosen_factory.is_some()
    }
}

#[derive(Debug, Clone, Default)]
pub struct SourceResolutions {
    resolutions: Vec<SourceResolution>,
}

impl SourceResolutions {
    pub(crate) fn new() -> Self {
        Self::default()
    }

    pub(crate) fn with_capacity(capacity: usize) -> Self {
        Self {
            resolutions: Vec::with_capacity(capacity),
        }
    }

    pub(crate) fn push(&mut self, resolution: SourceResolution) {
        self.resolutions.push(resolution);
    }

    pub(crate) fn iter(&self) -> impl Iterator<Item = &SourceResolution> {
        self.resolutions.iter()
    }

    pub fn resolved_sources(
        &self,
        source_type: Option<SourceKind>,
    ) -> impl Iterator<Item = &SourceResolution> {
        self.iter().filter(move |resolution| {
            resolution.is_resolved() && source_type_matches(resolution, source_type)
        })
    }

    pub fn unresolved_sources(
        &self,
        source_type: Option<SourceKind>,
    ) -> impl Iterator<Item = &SourceResolution> {
        self.iter().filter(move |resolution| {
            !resolution.is_resolved() && source_type_matches(resolution, source_type)
        })
    }

    pub fn valid(&self) -> Result<(), UnresolvedSourcesError> {
        let unresolved_sources = self.unresolved_sources(None).cloned().collect::<Vec<_>>();

        if unresolved_sources.is_empty() {
            Ok(())
        } else {
            Err(UnresolvedSourcesError { unresolved_sources })
        }
    }
}

#[derive(Debug, Clone)]
pub struct UnresolvedSourcesError {
    unresolved_sources: Vec<SourceResolution>,
}

impl UnresolvedSourcesError {
    pub fn unresolved_sources(&self) -> &[SourceResolution] {
        &self.unresolved_sources
    }
}

impl std::fmt::Display for UnresolvedSourcesError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            formatter,
            "{} source request(s) could not be resolved",
            self.unresolved_sources.len()
        )?;

        for resolution in &self.unresolved_sources {
            write!(
                formatter,
                "\n- request {}: {}",
                resolution.source_request_id().index(),
                describe_source_request(resolution.source_request())
            )?;

            if resolution.unsupported_factories().is_empty() {
                write!(formatter, "\n  no provider factories were available")?;
            } else {
                for unsupported in resolution.unsupported_factories() {
                    write!(
                        formatter,
                        "\n  - {} (factory {}): {}",
                        unsupported.factory_name,
                        unsupported.factory_id.index(),
                        unsupported.reason
                    )?;
                }
            }
        }

        Ok(())
    }
}

impl std::error::Error for UnresolvedSourcesError {}

fn describe_source_request(source_request: &SourceRequest) -> String {
    match source_request {
        SourceRequest::Power(request) => format!(
            "power (domain: {:?}, scope: {:?})",
            request.domain(),
            request.scope()
        ),
        SourceRequest::Intensity(request) => {
            let method = match request.method() {
                crate::domain::source::IntensitySources::ElectricityMaps { .. } => {
                    "electricity-maps"
                }
                crate::domain::source::IntensitySources::Static => "static",
                crate::domain::source::IntensitySources::LocalizedAverage => "localized-average",
                crate::domain::source::IntensitySources::GlobalAverage => "global-average",
                crate::domain::source::IntensitySources::Constant => "constant",
            };

            format!(
                "intensity (method: {method}, location: {:?})",
                request.location()
            )
        }
    }
}

fn source_type_matches(resolution: &SourceResolution, source_type: Option<SourceKind>) -> bool {
    match source_type {
        None => true,
        Some(SourceKind::Power) => matches!(resolution.source_request(), SourceRequest::Power(_)),
        Some(SourceKind::Intensity) => {
            matches!(resolution.source_request(), SourceRequest::Intensity(_))
        }
    }
}

impl IntoIterator for SourceResolutions {
    type Item = SourceResolution;
    type IntoIter = std::vec::IntoIter<SourceResolution>;

    fn into_iter(self) -> Self::IntoIter {
        self.resolutions.into_iter()
    }
}

impl<'a> IntoIterator for &'a SourceResolutions {
    type Item = &'a SourceResolution;
    type IntoIter = std::slice::Iter<'a, SourceResolution>;

    fn into_iter(self) -> Self::IntoIter {
        self.resolutions.iter()
    }
}

pub struct ResolvedProviders {
    pub resolutions: SourceResolutions,
    pub registrations: Vec<ProviderRegistration>,
}

impl ResolvedProviders {
    pub fn new() -> Self {
        Self {
            resolutions: SourceResolutions::new(),
            registrations: Vec::new(),
        }
    }

    pub fn add_resolve(&mut self, resolution: SourceResolution) {
        self.resolutions.push(resolution);
    }

    pub fn add_registration(&mut self, registration: ProviderRegistration) {
        self.registrations.push(registration);
    }

    pub(crate) fn into_parts(self) -> (SourceResolutions, Vec<ProviderRegistration>) {
        (self.resolutions, self.registrations)
    }
}

impl Default for ResolvedProviders {
    fn default() -> Self {
        Self::new()
    }
}

struct RegisteredProviderFactory {
    id: FactoryId,
    factory: Box<dyn ProviderFactory>,
}

pub struct ProviderRegistry {
    factories: Vec<RegisteredProviderFactory>,
}

#[derive(Debug, thiserror::Error)]
pub enum ProviderRegisterError {
    #[error("provider factory {factory_name} failed to create a provider: {source}")]
    ProviderCreation {
        factory_name: &'static str,
        #[source]
        source: ProviderError,
    },
}

impl ProviderRegistry {
    pub fn new() -> Self {
        Self {
            factories: Vec::new(),
        }
    }
    pub async fn resolve(
        &self,
        source_requests: &[SourceRequest],
    ) -> Result<ResolvedProviders, ProviderRegisterError> {
        let mut resolutions = SourceResolutions::with_capacity(source_requests.len());

        for (request_index, source_request) in source_requests.iter().enumerate() {
            let mut resolution =
                SourceResolution::new(SourceRequestId(request_index), source_request.clone());

            // The registry is ordered from highest to lowest priority. Iterating in
            // reverse lets each compatible factory overwrite the current choice, so
            // the highest-priority compatible factory is chosen last.
            for registered_factory in self.factories.iter().rev() {
                match registered_factory.factory.supports(source_request).await {
                    Ok(()) => resolution.add_compatible(registered_factory.id),
                    Err(reason) => resolution.add_unsupported(
                        registered_factory.id,
                        registered_factory.factory.name(),
                        reason,
                    ),
                }
            }

            resolutions.push(resolution);
        }

        // Group source request into factories
        let mut source_requests_per_factory: HashMap<FactoryId, Vec<SourceRequest>> =
            HashMap::new();

        for resolution in resolutions.iter() {
            let Some(factory_id) = resolution.chosen_factory() else {
                continue;
            };

            source_requests_per_factory
                .entry(factory_id)
                .or_default()
                .push(resolution.source_request().clone());
        }

        let mut resolved_providers = ResolvedProviders::new();

        for registered_factory in &self.factories {
            let Some(requests) = source_requests_per_factory.remove(&registered_factory.id) else {
                // Skip the factories, which are not chosen
                continue;
            };

            // Build one provider that supplies every source assigned to this factory.
            let registration =
                registered_factory
                    .factory
                    .create(&requests)
                    .await
                    .map_err(|source| ProviderRegisterError::ProviderCreation {
                        factory_name: registered_factory.factory.name(),
                        source,
                    })?;

            resolved_providers.add_registration(registration);
        }

        for resolution in resolutions {
            resolved_providers.add_resolve(resolution);
        }

        Ok(resolved_providers)
    }

    pub fn register<F>(&mut self, provider_factory: F) -> FactoryId
    where
        F: ProviderFactory + 'static,
    {
        let id = FactoryId(self.factories.len());
        self.factories.push(RegisteredProviderFactory {
            id,
            factory: Box::new(provider_factory),
        });
        id
    }
}

impl Default for ProviderRegistry {
    fn default() -> Self {
        Self::new()
    }
}
