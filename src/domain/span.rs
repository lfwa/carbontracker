use crate::domain::{measurements::Timestamp, profiler::UsageStats, request::RequestId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct SpanId(usize);

impl SpanId {
    pub const fn new(value: usize) -> Self {
        Self(value)
    }

    pub const fn index(self) -> usize {
        self.0
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpanBoundary {
    Start,
    Stop,
}

#[derive(Debug, Clone)]
pub struct ActiveSpan {
    pub span_id: SpanId,
    pub name: String,
    pub started_at: Timestamp,
    pub parent_span_id: Option<SpanId>,
    pub start_boundary_request_id: RequestId,
}

#[derive(Debug, Clone)]
pub struct PendingSpan {
    pub span_id: SpanId,
    pub name: String,
    pub started_at: Timestamp,
    pub ended_at: Timestamp,
    pub parent_span_id: Option<SpanId>,
    pub start_boundary_request_id: RequestId,
}

#[derive(Debug, Clone)]
pub struct SpanProfile {
    pub span_id: SpanId,
    pub parent_span_id: Option<SpanId>,
    pub name: String,
    pub started_at: Timestamp,
    pub ended_at: Timestamp,
    pub usage: UsageStats,
}
