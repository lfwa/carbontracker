use crate::domain::{controller::ControllerError, dispatcher::DispatcherError, observer::ObserverError, profiler::ProfilerError, providers::ProviderError};

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("controller failed: {0}")]
    Controller(#[from] ControllerError),

    #[error("observer failed: {0}")]
    Observer(#[from] ObserverError),

    #[error("provider failed: {0}")]
    Provider(#[from] ProviderError),

    #[error("dispatcher failed: {0}")]
    Dispatcher(#[from] DispatcherError),

    #[error("profiler failed: {0}")]
    Profiler(#[from] ProfilerError),

}
