use crate::domain::{dispatcher::DispatcherError, events::Event};

pub trait Dispatcher {
    async fn send(&mut self, event: Event) -> Result<(), DispatcherError>;

    async fn finish(&mut self) -> Result<(), DispatcherError> {
        Ok(())
    }
}
