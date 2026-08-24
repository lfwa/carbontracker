#[derive(Debug, thiserror::Error)]
pub enum ObserverError {
    #[error("observer does not have the required permissions")]
    PermissionsError,

    #[error("Duplicate start for span")]
    DuplicateStart,
    #[error("Duplicate end for span")]
    DuplicateEnd,
    #[error("Output channel is closed")]
    ChannelClosed,
    #[error("Observer start failed")]
    ObserverStartFailed,
}

use async_trait::async_trait;

