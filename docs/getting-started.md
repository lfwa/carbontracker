# Getting started
## Installation
[**carbontracker** is available on PyPI](https://pypi.org/project/carbontracker/) and can be installed using pip:
~~~bash
pip install carbontracker
~~~

To get accurate measurements for applications using GPUs, please make sure [NVML](https://developer.nvidia.com/nvidia-management-library-nvml) is installed.

## Example usage (CLI)
[See documentation for list of CLI options](documentation/CLI.md).

~~~bash
$ carbontracker python script.py
~~~

Example output:
```
CarbonTracker: The following components were found: CPU with device(s) cpu:0.
CarbonTracker: Average carbon intensity during training was 151.50 gCO2/kWh at detected location: Copenhagen, Capital Region, DK.
CarbonTracker: 
Actual consumption:
	Time:	0:00:24
	Energy:	0.000286936393 kWh
	CO2eq:	0.043470863590 g
	This is equivalent to:
	0.000404380126 km travelled by car
CarbonTracker: Finished monitoring.
```

## Example usage (Python)
[See documentation for CarbonTracker class](documentation/CarbonTracker.md).

~~~python
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
~~~

Example output:
~~~
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
~~~
