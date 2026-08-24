#[derive(Debug, thiserror::Error)]
pub enum DispatcherError {
    #[error("dispatcher output closed")]
    OutputClosed,
}
