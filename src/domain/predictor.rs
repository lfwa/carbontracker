use chrono::Duration;

use crate::domain::{config::PredictionConfig, measurements::Timestamp, profiler::SessionStats, units::{GramsCo2e, GramsCo2ePerKwh, KilowattHours, UnitError}};

#[derive(Debug, Clone)]
pub enum PredictionTarget {
    Units { total: usize, unit_name: String },

    Duration(Duration),
}

#[derive(Debug, Clone)]
pub enum PredictionStart {
    AfterUnits(usize),
    AfterDuration(Duration),
}

pub struct Predictor {
    pub config: PredictionConfig,
    pub latest: Option<Prediction>,
    pub last_updated_at: Option<Timestamp>,
}


impl Predictor {
      pub fn new(config: PredictionConfig) -> Self {
          Self {
              config,
              latest: None,
              last_updated_at: None,
          }
      }

      pub fn latest(&self) -> Option<&Prediction> {
          self.latest.as_ref()
      }

      pub fn update(
          &mut self,
          stats: &SessionStats,
          now: Timestamp,
      ) -> Result<Option<Prediction>, PredictionError> {
          if !self.has_enough_data(stats) {
              return Ok(None);
          }

          if !self.update_is_due(&now) {
              return Ok(None);
          }

          let factor = self.projection_factor(stats)?;

          let prediction = Prediction {
              calculated_at: now,
              projected_energy: stats.energy.checked_mul(factor)?,
              projected_emissions: stats.emissions.checked_mul(factor)?,
              projected_average_intensity: stats.average_intensity,
              based_on_completed_units: stats.completed_units,
              projection_factor: factor,
          };

          self.last_updated_at =
              Some(prediction.calculated_at);

          self.latest = Some(prediction.clone());

          Ok(Some(prediction))
      }

      fn has_enough_data(&self, stats: &SessionStats) -> bool {
          match self.config.start_after {
              PredictionStart::AfterUnits(required) => {
                  stats.completed_units >= required
              }

              PredictionStart::AfterDuration(required) => {
                  stats.elapsed >= required
              }
          }
      }

      fn update_is_due(&self, now: &Timestamp) -> bool {
          let Some(interval) = self.config.update_interval else {
              return true;
          };

          let Some(last_updated_at) = &self.last_updated_at else {
              return true;
          };

          now.signed_duration_since(*last_updated_at) >= interval
      }

      fn projection_factor(
          &self,
          stats: &SessionStats,
      ) -> Result<f64, PredictionError> {
          let factor = match &self.config.target {
              PredictionTarget::Units { total, .. } => {
                  if stats.completed_units == 0 {
                      return Err(PredictionError::NoCompletedUnits);
                  }

                  *total as f64 / stats.completed_units as f64
              }

              PredictionTarget::Duration(target) => {
                  let elapsed = stats.elapsed.num_milliseconds();

                  if elapsed <= 0 {
                      return Err(PredictionError::NoElapsedTime);
                  }

                  target.num_milliseconds() as f64 / elapsed as f64
              }
          };

          // A prediction should never become lower than what was
          // already observed.
          Ok(factor.max(1.0))
      }
  }
#[derive(Debug, Clone)]
 pub struct Prediction {
     pub calculated_at: Timestamp,
     pub projected_energy: KilowattHours,
     pub projected_emissions: GramsCo2e,
     pub projected_average_intensity: Option<GramsCo2ePerKwh>,
     pub based_on_completed_units: usize,
     pub projection_factor: f64,
 }
 #[derive(Debug, thiserror::Error)]
 pub enum PredictionError {
     #[error("cannot predict before a unit has completed")]
     NoCompletedUnits,

     #[error("cannot predict without positive elapsed time")]
     NoElapsedTime,

     #[error(transparent)]
     InvalidUnit(#[from] UnitError),
 }