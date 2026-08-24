use std::{collections::HashMap};

use chrono::Utc;
use tokio::sync::mpsc;

use crate::domain::{
    events::{ObserverEvent, SpanBoundary}, observer::{ObservationItem, ObserverError},
};


pub struct ManualObserverHandle {
    tx: mpsc::Sender<ObservationItem>,
    name_count: HashMap<String, u32>,
}

pub struct ManualObservationSource {
    rx: mpsc::Receiver<ObservationItem>,
}

pub fn manual_observer(
    capacity: usize,
) -> (ManualObserverHandle, ManualObservationSource) {
    let (tx, rx) = mpsc::channel(capacity);

    (
        ManualObserverHandle { tx, name_count: HashMap::new() },
        ManualObservationSource { rx },
    )
}

impl ManualObserverHandle {
    fn create_event(
        &mut self,
        name: &str,
        boundary: SpanBoundary,
    ) -> Result<ObserverEvent, ObserverError> {
        let count = self.name_count.entry(name.to_owned()).or_insert(0);

        if !count.is_multiple_of(2) && boundary == SpanBoundary::Start {
            return Err(ObserverError::DuplicateStart);
        }
        if count.is_multiple_of(2) && boundary == SpanBoundary::Stop {
            return Err(ObserverError::DuplicateEnd);
        }

        *count += 1;

        let marker_id = format!("{name}:{count}");

        return Ok(ObserverEvent {
            marker_id: marker_id,
            timestamp: Utc::now(),
            boundary: boundary,
        });
    }

    pub fn mark_start(&mut self, name: &str) -> Result<(), ObserverError> {
        let event = self.create_event(name, SpanBoundary::Start); 
        self.sender
            .send(event);
        Ok(())
    }
    pub fn mark_end(&mut self, name: &str) -> Result<(), ObserverError> {
        let event = self.create_event(name, SpanBoundary::Stop); 
        self.sender
            .send(event);
        Ok(())
    }
}

