# CarbonTracker

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## About
CarbonTracker is a tool for tracking and predicting the carbon footprint of training deep learning models.

## Installation
### PyPi install
```
pip install carbontracker
```

## Basic usage

#### Required arguments
- `epochs`:
  Total epochs of your training loop.
#### Optional arguments
- `epochs_before_pred` (default=1):
  Epochs to monitor before outputting prediction. Set to -1 for all epochs.
- `monitor_epochs` (default=1):
  Total number of epochs to monitor. Set to -1 for all epochs. Cannot be less than `epochs_before_pred`.
- `update_interval` (default=10):
  Interval in seconds between power usage measurements are taken.
- `interpretable` (default=True):
  If set to True then the CO2eq are also converted to interpretable numbers such as the equivalent distance travelled in a car, etc. Otherwise, no conversions are done.
- `stop_and_confirm` (default=False):
  If set to True then the main thread (with your training loop) is paused after `epochs_before_pred` epochs to output the prediction and the user will need to confirm to continue training. Otherwise, prediction is output and training is continued instantly.
- `ignore_errors` (default=False):
  If set to True then all errors will cause energy monitoring to be stopped and training will continue. Otherwise, training will be interrupted as with regular errors.
- `components` (default="all"):
  Comma-separated string of which components to monitor. Options are: "all", "gpu", "cpu", or "gpu,cpu".
- `log_dir` (default=None):
  Path to the desired directory to write log files. If None, then no logging will be done.
- `verbose` (default=0):
  Sets the level of verbosity.

#### Example:

```python
from carbontracker.tracker import CarbonTracker

tracker = CarbonTracker(epochs=max_epochs)

# Training loop.
for epoch in range(max_epochs):
    tracker.epoch_start()
    
    # Your model training

    tracker.epoch_end()
```

## Compatability
CarbonTracker is compatible with:
- NVIDIA GPUs that support [NVIDIA Management Library (NVML)](https://developer.nvidia.com/nvidia-management-library-nvml)
- Intel CPUs that support [Intel RAPL](http://web.eece.maine.edu/~vweaver/projects/rapl/rapl_support.html)