# **carbontracker**
[![Build](https://github.com/lfwa/carbontracker/actions/workflows/publish.yml/badge.svg)](https://github.com/lfwa/carbontracker/actions)
[![PyPI](https://img.shields.io/pypi/v/carbontracker?label=PyPI)](https://pypi.org/project/carbontracker/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.7-blue)](https://www.python.org/downloads/)
[![Unit Tests](https://github.com/lfwa/carbontracker/actions/workflows/test.yml/badge.svg)](https://github.com/lfwa/carbontracker/actions)
[![License](https://img.shields.io/github/license/lfwa/carbontracker)](https://github.com/lfwa/carbontracker/blob/master/LICENSE)
[![Downloads](https://static.pepy.tech/badge/carbontracker)](https://pepy.tech/project/carbontracker)

[Website](https://carbontracker.info)

## About
**carbontracker** is a tool for tracking and predicting the energy consumption and carbon footprint of training deep learning models as described in [Anthony et al. (2020)](https://arxiv.org/abs/2007.03051).

## Citation
Kindly cite our work if you use **carbontracker** in a scientific publication:
```
@misc{anthony2020carbontracker,
  title={Carbontracker: Tracking and Predicting the Carbon Footprint of Training Deep Learning Models},
  author={Lasse F. Wolff Anthony and Benjamin Kanding and Raghavendra Selvan},
  howpublished={ICML Workshop on Challenges in Deploying and monitoring Machine Learning Systems},
  month={July},
  note={arXiv:2007.03051},
  year={2020}}
```

## Installation
### PyPi
```
pip install carbontracker
```

## Basic usage

### Command Line Mode
Wrap any of your scripts (python, bash, etc.):

`carbontracker python script.py
`
### Embed into Python Scripts

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
- `log_file_prefix` (default=""):
  Prefix to add to the log file name.
- `verbose` (default=1):
  Sets the level of verbosity.
- `decimal_precision` (default=6):
  Desired decimal precision of reported values.

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

## Parsing log files

### Aggregating log files
**carbontracker** supports aggregating all log files in a specified directory to a single estimate of the carbon footprint.
#### Example usage
```python
from carbontracker import parser

parser.print_aggregate(log_dir="./my_log_directory/")
```
#### Example output
```
The training of models in this work is estimated to use 4.494 kWh of electricity contributing to 0.423 kg of CO2eq. This is equivalent to 3.515 km travelled by car. Measured by carbontracker (https://github.com/lfwa/carbontracker).
```

### Convert logs to dictionary objects
Log files can be parsed into dictionaries using `parser.parse_all_logs()` or `parser.parse_logs()`.
#### Example usage
```python
from carbontracker import parser

logs = parser.parse_all_logs(log_dir="./logs/")
first_log = logs[0]

print(f"Output file name: {first_log['output_filename']}")
print(f"Standard file name: {first_log['standard_filename']}")
print(f"Stopped early: {first_log['early_stop']}")
print(f"Measured consumption: {first_log['actual']}")
print(f"Predicted consumption: {first_log['pred']}")
print(f"Measured GPU devices: {first_log['components']['gpu']['devices']}")
```
#### Example output
```
Output file name: ./logs/2020-05-17T19:02Z_carbontracker_output.log
Standard file name: ./logs/2020-05-17T19:02Z_carbontracker.log
Stopped early: False
Measured consumption: {'epochs': 1, 'duration (s)': 8.0, 'energy (kWh)': 6.5e-05, 'co2eq (g)': 0.019201, 'equivalents': {'km travelled by car': 0.000159}}
Predicted consumption: {'epochs': 3, 'duration (s)': 25.0, 'energy (kWh)': 1000.000196, 'co2eq (g)': 10000.057604, 'equivalents': {'km travelled by car': 10000.000478}}
Measured GPU devices: ['Tesla T4']
```



## Compatibility
**carbontracker** is compatible with:
- NVIDIA GPUs that support [NVIDIA Management Library (NVML)](https://developer.nvidia.com/nvidia-management-library-nvml)
- Intel CPUs that support [Intel RAPL](http://web.eece.maine.edu/~vweaver/projects/rapl/rapl_support.html)
- Slurm
- Google Colab / Jupyter Notebook


## Notes
### Availability of GPUs and Slurm
- Available GPU devices are determined by first checking the environment variable `CUDA_VISIBLE_DEVICES` (only if `devices_by_pid`=False otherwise we find devices by PID). This ensures that for Slurm we only fetch GPU devices associated with the current job and not the entire cluster. If this fails we measure all available GPUs.
- NVML cannot find processes for containers spawned without `--pid=host`. This affects the `device_by_pids` parameter and means that it will never find any active processes for GPUs in affected containers. 

## Extending **carbontracker**
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Star History
[![Star History Chart](https://api.star-history.com/svg?repos=lfwa/carbontracker&type=Date)](https://star-history.com/#lfwa/carbontracker&Date)

## carbontracker in media
* Official press release from University of Copenhagen can be obtained here: [en](https://news.ku.dk/all_news/2020/11/students-develop-tool-to-predict-the-carbon-footprint-of-algorithms/) [da](https://nyheder.ku.dk/alle_nyheder/2020/11/studerende-opfinder-vaerktoej-der-forudsiger-algoritmers-co2-aftryk/)

* Carbontracker has recieved some attention in popular science forums within, and outside of, Denmark [[1](https://videnskab.dk/teknologi-innovation/kunstig-intelligens-er-en-kaempe-klimasynder-men-unge-danskeres-nye-vaerktoej)][[2](https://www.anthropocenemagazine.org/2020/11/time-to-talk-about-carbon-footprint-artificial-intelligence/)][[3](https://www.theregister.com/2020/11/04/gpt3_carbon_footprint_estimate/)][[4](https://jyllands-posten.dk/nyviden/ECE12533278/kunstig-intelligens-er-en-kaempe-klimasynder-men-nyt-dansk-vaerktoej-skal-hjaelpe/)][[5](https://www.sciencenewsforstudents.org/article/training-ai-energy-emissions-climate-risk)][[6](https://www.digitaltrends.com/news/carbontracker-deep-learning-sustainability/)][[7](https://www.prosa.dk/artikel/detail/news/effektivt-vaaben-mod-klimaforandringer/)][[8](https://medium.com/techtalkers/artificial-intelligence-contributes-to-climate-change-heres-how-405ff919186e)]



