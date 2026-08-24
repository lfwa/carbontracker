use std::{future::pending, time::Duration};

use tokio::{sync::mpsc, time::Instant};

use crate::domain::{
    errors::Error,
    events::{Event, ObserverEvent},
    observer::ObserverError,
    profiler::Profiler,
    providers::ProviderRuntime,
    span::SpanBoundary,
};

pub enum ControllerCommand {
    Observe(Result<ObserverEvent, ObserverError>),
    Finish,
}

pub struct Controller {
    command_rx: mpsc::Receiver<ControllerCommand>,
    out_tx: mpsc::Sender<Event>,
    provider_runtime: ProviderRuntime,
    profiler: Profiler,
    request_timeout: Duration,
}

impl Controller {
    pub fn new(
        command_rx: mpsc::Receiver<ControllerCommand>,
        out_tx: mpsc::Sender<Event>,
        provider_runtime: ProviderRuntime,
        profiler: Profiler,
        request_timeout: Duration,
    ) -> Self {
        Self {
            command_rx,
            out_tx,
            provider_runtime,
            profiler,
            request_timeout,
        }
    }

    async fn send_output(&self, output: Event) -> Result<(), ControllerError> {
        self.out_tx
            .send(output)
            .await
            .map_err(|_| ControllerError::OutputClosed)
    }

    async fn send_profiler_outputs(
        &self,
        outputs: impl IntoIterator<Item = crate::domain::events::ProfilerEvent>,
    ) -> Result<(), ControllerError> {
        for output in outputs {
            self.send_output(Event::Profiler(output)).await?;
        }

        Ok(())
    }

    pub async fn run_tracker(mut self) -> Result<(), Error> {
        loop {
            let deadline = self.profiler.next_request_deadline();

            tokio::select! {
                command = self.command_rx.recv() => {
                    match command {
                        Some(ControllerCommand::Observe(observer_event)) => {
                            let observation = observer_event?;

                            let events = match observation.boundary {
                                SpanBoundary::Start => {
                                    let request_id = self
                                        .profiler
                                        .prepare_span_start(&observation)?;
                                    let provider_states = self
                                        .provider_runtime
                                        .sample_all(request_id);
                                    let deadline = Instant::now() + self.request_timeout;

                                    self.profiler.start_span(
                                        observation,
                                        request_id,
                                        provider_states,
                                        deadline,
                                    )?
                                }

                                SpanBoundary::Stop => {
                                    self.profiler.stop_span(observation)?
                                }
                            };

                            self.send_profiler_outputs(events).await?;
                        }

                        Some(ControllerCommand::Finish) => {
                            let events = self.profiler.finish().await?;
                            self.send_profiler_outputs(events).await?;
                            break;
                        }

                        None => {
                            return Err(
                                ControllerError::CommandStreamClosed.into()
                            );
                        }
                    }
                }

                provider_output = self.provider_runtime.output_rx.recv() => {
                    match provider_output {
                        Some(output) => {
                            let events = self
                                .profiler
                                .process_provider_output(output)?;

                            self.send_profiler_outputs(events).await?;
                        }

                        None => {
                            return Err(
                                ControllerError::ProviderOutputStreamClosed.into()
                            );
                        }
                    }
                }

                _ = wait_for_deadline(deadline) => {
                    let events = self
                        .profiler
                        .expire_requests(Instant::now())?;

                    self.send_profiler_outputs(events).await?;
                }
            }
        }

        Ok(())
    }
}

async fn wait_for_deadline(deadline: Option<Instant>) {
    match deadline {
        Some(deadline) => tokio::time::sleep_until(deadline).await,
        None => pending::<()>().await,
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ControllerError {
    #[error("output channel closed")]
    OutputClosed,

    #[error("controller command stream closed unexpectedly")]
    CommandStreamClosed,

    #[error("provider output stream closed unexpectedly")]
    ProviderOutputStreamClosed,
}
