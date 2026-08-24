use crate::domain::{
    guard::GuardVerdict, measurements::{Measurement, MeasurementSample, Timestamp}, predictor::Prediction, profiler::{SessionFinalStats, SessionStats, SpanProfile}, providers::{ProviderId, ProviderMetaData, ResolvedProviders, SourceResolutions}, span::{ SpanBoundary, SpanId},
};

#[derive(Debug, Clone)]
pub struct ObserverEvent {
    pub span_id: SpanId,
    pub parent_span_id: Option<SpanId>,
    pub name: String,
    pub boundary: SpanBoundary,
    pub timestamp: Timestamp,
}

#[derive(Debug, Clone)]
pub enum ProfilerEvent {
    SpanStarted {
        span_id: SpanId,
        parent_span_id: Option<SpanId>,
        started_at: Timestamp,
    },

    SpanStopped {
        span_id: SpanId,
        ended_at: Timestamp,
    },

    MeasurementsRecorded {
        samples: Vec<MeasurementSample>,
    },

    SpanProfiled {
        profile: SpanProfile,
    },

    SessionStatsUpdated {
        stats: SessionStats,
    },

    PredictionEvent {
        prediction: Prediction
    },

    GuardVerdictEvent {
        verdict: GuardVerdict
    },

    FinalStatsComputed {
        stats: SessionFinalStats,
    },
}

#[derive(Debug, Clone)]
pub enum Event {
    Profiler(ProfilerEvent),

    ProviderInitialized { resolutions: SourceResolutions },

    TrackingStarted,
    TrackingStopped,

    ObserverFailed { message: String },

    ProfilerFailed { message: String },
}
