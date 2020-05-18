# carbontracker
[![pypi](https://img.shields.io/pypi/v/carbontracker?label=pypi)](https://pypi.org/project/carbontracker/)
[![Python 3.6](https://img.shields.io/pypi/pyversions/django?color=blue&logo=python)](https://www.python.org/downloads/)
[![build](https://github.com/lfwa/carbontracker/workflows/build/badge.svg)](https://github.com/lfwa/carbontracker/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/lfwa/carbontracker/blob/master/LICENSE)

## About
**carbontracker** is a tool for tracking and predicting the carbon footprint of training deep learning models.


## Installation
### PyPi
```
pip install carbontracker
```

## Basic usage

#### Required arguments
- `epochs`:
  Total epochs of your training loop.
#### Optional arguments
- `epochs_before_pred` (default=1):
  Epochs to monitor before outputting predicted consumption. Set to -1 for all epochs. Set to 0 for no prediction.
- `monitor_epochs` (default=1):
  Total number of epochs to monitor. Outputs actual consumption when reached. Set to -1 for all epochs. Cannot be less than `epochs_before_pred` or equal to 0.
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
- `devices_by_pid` (default=False):
  If True, only devices (under the chosen components) running processes associated with the main process are measured. If False, all available devices are measured (see Section 'Notes' for jobs running on SLURM or in containers). Note that this requires your devices to have active processes before instantiating the `CarbonTracker` class.
- `log_dir` (default=None):
  Path to the desired directory to write log files. If None, then no logging will be done.
- `verbose` (default=0):
  Sets the level of verbosity.

#### Example usage

```python
from carbontracker.tracker import CarbonTracker

tracker = CarbonTracker(epochs=max_epochs)

# Training loop.
for epoch in range(max_epochs):
    tracker.epoch_start()
    
    # Your model training.

    tracker.epoch_end()

# Optional: Add a stop in case of early termination before all monitor_epochs has
# been monitored to ensure that actual consumption is reported.
tracker.stop()
```

#### Example output
##### Default settings
```
CarbonTracker: 
Actual consumption for 1 epoch(s):
        Time:   0:00:10
        Energy: 0.000038 kWh
        CO2eq:  0.003130 g
        This is equivalent to:
        0.000026 km travelled by car
CarbonTracker: 
Predicted consumption for 1000 epoch(s):
        Time:   2:52:22
        Energy: 0.038168 kWh
        CO2eq:  4.096665 g
        This is equivalent to:
        0.034025 km travelled by car
CarbonTracker: Finished monitoring.
```
##### verbose=2
```
CarbonTracker: The following components were found: CPU with device(s) cpu:0.
CarbonTracker: Average carbon intensity during training was 82.00 gCO2/kWh at detected location: Copenhagen, Capital Region, DK.
CarbonTracker: 
Actual consumption for 1 epoch(s):
        Time:   0:00:10
        Energy: 0.000041 kWh
        CO2eq:  0.003357 g
        This is equivalent to:
        0.000028 km travelled by car
CarbonTracker: Carbon intensity for the next 2:59:06 is predicted to be 107.49 gCO2/kWh at detected location: Copenhagen, Capital Region, DK.
CarbonTracker: 
Predicted consumption for 1000 epoch(s):
        Time:   2:59:06
        Energy: 0.040940 kWh
        CO2eq:  4.400445 g
        This is equivalent to:
        0.036549 km travelled by car
CarbonTracker: Finished monitoring.
```

### Aggregating log files
**carbontracker** supports aggregating all log files in a specified directory to a single estimate of the carbon footprint.
#### Usage
```python
from carbontracker import parser

parser.print_aggregate(log_dir="./my_log_directory/")
```
#### Example output
```
The training of models in this work is estimated to use 4.494 kWh of electricity contributing to 0.423 kg of CO2eq. This is equivalent to 3.515 km travelled by car. Measured by carbontracker (https://github.com/lfwa/carbontracker).
```

## Compatability
CarbonTracker is compatible with:
- NVIDIA GPUs that support [NVIDIA Management Library (NVML)](https://developer.nvidia.com/nvidia-management-library-nvml)
- Intel CPUs that support [Intel RAPL](http://web.eece.maine.edu/~vweaver/projects/rapl/rapl_support.html)
- Slurm
- Google Colab / Jupyter Notebook


## Notes
### Availability of GPUs and Slurm
- Available GPU devices are determined by first checking the environment variable `CUDA_VISIBLE_DEVICES` (only if `devices_by_pid`=False otherwise we find devices by PID). This ensures that for Slurm we only fetch GPU devices associated with the current job and not the entire cluster. If this fails we measure all available GPUs.
- NVML cannot find processes for containers spawned without `--pid=host`. This affects the `device_by_pids` parameter and means that it will never find any active processes for GPUs in affected containers. 
