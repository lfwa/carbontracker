
use std::num::NonZeroUsize;

use crate::domain::{predictor::Prediction, profiler::SessionStats, units::{GramsCo2e, GramsCo2ePerKwh, KilowattHours}};

#[derive(Debug)]
pub struct Guard {
    config: GuardConfig,
    consecutive_breaches: usize,
    action_emitted: bool,
}

#[derive(Debug, Clone)]
pub struct GuardConfig {
    budget: Budget,
    evaluation: GuardEvaluation,
    patience: NonZeroUsize,
    action: GuardBreachAction,
}

#[derive(Debug, Clone, Copy)]
pub enum Budget {
    Energy {
        maximum: KilowattHours,
    },

    Emissions {
        maximum: GramsCo2e,
    },
    Intensity {
        maximum: GramsCo2ePerKwh,
    },
    EnergyAndEmissions {
        maximum_energy: KilowattHours,
        maximum_emissions: GramsCo2e,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardEvaluation {
    Observed,
    Predicted,
}

#[derive(Debug, Clone, Copy, PartialEq)]
 pub enum GuardBreach {
     Energy {
         observed: KilowattHours,
         maximum: KilowattHours,
     },

     Emissions {
         observed: GramsCo2e,
         maximum: GramsCo2e,
     },

     Intensity {
         observed: GramsCo2ePerKwh,
         maximum: GramsCo2ePerKwh,
     },
 }

 #[derive(Debug, Clone, PartialEq)]
 pub enum GuardVerdict {
     NotReady,

     WithinBudget,

     Breached {
         breaches: Vec<GuardBreach>,
         consecutive_breaches: usize,

         // Some only when patience has been reached and the
         // action has not previously been emitted.
         action: Option<GuardBreachAction>,
     },
 }
 
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardBreachAction {
    Log,
    RequestStop,
    NotifyHost,
}

pub struct GuardInput<'a> {
      pub observed: &'a SessionStats,
      pub prediction: Option<&'a Prediction>,
  }



  #[derive(Debug, Clone, Copy)]
  struct GuardUsage {
      energy: KilowattHours,
      emissions: GramsCo2e,
      intensity: Option<GramsCo2ePerKwh>,
  }

  impl Guard {
      pub fn new(config: GuardConfig) -> Self {
          Self {
              config,
              consecutive_breaches: 0,
              action_emitted: false,
          }
      }

      pub fn evaluate(
          &mut self,
          input: GuardInput<'_>,
      ) -> GuardVerdict {
          let usage = match self.config.evaluation {
              GuardEvaluation::Observed => GuardUsage {
                  energy: input.observed.energy,
                  emissions: input.observed.emissions,
                  intensity: input.observed.average_intensity,
              },

              GuardEvaluation::Predicted => {
                  let Some(prediction) = input.prediction else {
                      return GuardVerdict::NotReady;
                  };

                  GuardUsage {
                      energy: prediction.projected_energy,
                      emissions: prediction.projected_emissions,
                      intensity: prediction.projected_average_intensity,
                  }
              }
          };

          let breaches =
              evaluate_budget(self.config.budget, usage);

          if breaches.is_empty() {
              self.consecutive_breaches = 0;
              self.action_emitted = false;

              return GuardVerdict::WithinBudget;
          }

          self.consecutive_breaches += 1;

          let patience_reached =
              self.consecutive_breaches >= self.config.patience.get();

          let action = if patience_reached && !self.action_emitted {
              self.action_emitted = true;
              Some(self.config.action)
          } else {
              None
          };

          GuardVerdict::Breached {
              breaches,
              consecutive_breaches: self.consecutive_breaches,
              action,
          }
      }
      
      
  }


  fn evaluate_budget(
      budget: Budget,
      usage: GuardUsage,
  ) -> Vec<GuardBreach> {
      let mut breaches = Vec::new();

      match budget {
          Budget::Energy { maximum } => {
              if usage.energy > maximum {
                  breaches.push(GuardBreach::Energy {
                      observed: usage.energy,
                      maximum,
                  });
              }
          }

          Budget::Emissions { maximum } => {
              if usage.emissions > maximum {
                  breaches.push(GuardBreach::Emissions {
                      observed: usage.emissions,
                      maximum,
                  });
              }
          }

          Budget::Intensity { maximum } => {
              if let Some(intensity) = usage.intensity {
                  if intensity > maximum {
                      breaches.push(GuardBreach::Intensity {
                          observed: intensity,
                          maximum,
                      });
                  }
              }
          }

          Budget::EnergyAndEmissions {
              maximum_energy,
              maximum_emissions,
          } => {
              if usage.energy > maximum_energy {
                  breaches.push(GuardBreach::Energy {
                      observed: usage.energy,
                      maximum: maximum_energy,
                  });
              }

              if usage.emissions > maximum_emissions {
                  breaches.push(GuardBreach::Emissions {
                      observed: usage.emissions,
                      maximum: maximum_emissions,
                  });
              }
          }
      }

      breaches
  }