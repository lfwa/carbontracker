# About

**carbontracker** is a tool for tracking and predicting the energy consumption and carbon footprint of training deep learning models as described in [Anthony et al. (2020)](https://arxiv.org/abs/2007.03051).
It is available both as a CLI and as a Python module for easy implementation into existing code.

See [Getting started](/getting-started) for how to get started.

See [CLI](documentation/CLI.md) for CLI options.

## Compatible components
**carbontracker** supports the following components:

- Intel CPUs that support [Intel RAPL](http://web.eece.maine.edu/~vweaver/projects/rapl/rapl_support.html) on Linux. [Note on how to enable permissions](/#permissions)
- NVIDIA GPUs that support [NVIDIA Management Library (NVML)](Intel CPUs that support Intel RAPL) on Linux
- Apple Silicon on MacOS

## Permissions
To be able to read the power consumption from Intel CPUs, **carbontracker** needs read access to the `/sys/class/powercap/intel-rapl:0/energy_uj` file. This can be done like so using `chmod`:
~~~bash
sudo chmod +r /sys/class/powercap/intel-rapl:0/energy_uj
~~~
Note that these changes are not persistent. To make persistent changes, one can add a `udev` rule like so:
~~~bash
# /etc/udev/rules.d/powercap.rules
ACTION=="add|change", SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", RUN+="/bin/chmod og+r %S%p/energy_uj"
~~~
Then one can immediately apply the permission changes:
~~~bash
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=powercap
~~~
### Disabling CPU monitoring
If you do not have such access and only wish to monitor GPU power consumption, one can disable CPU access using the `components` parameter:
~~~python
tracker = CarbonTracker(
        epochs=args.num_epochs,
        components="gpu", # Exclude CPU from components to monitor
        log_dir='carbontracker/',
        monitor_epochs=-1
    )
~~~

## Running **carbontracker** on HPC clusters and in containers

- Available GPU devices are determined by first checking the environment variable `CUDA_VISIBLE_DEVICES` (only if `devices_by_pid=False`, otherwise devices are found by PID). 
This ensures that for Slurm we only fetch GPU devices associated with the current job and not the entire cluster. 
If this fails we measure all available GPUs.

- NVML cannot find processes for containers spawned without `--pid=host`. This affects the `device_by_pid` parameter and means that it will never find any active processes for GPUs in affected containers.

## Running **carbontracker** on Apple Silicon

- **carbontracker** is compatible with Apple Silicon on MacOS using `powermetrics` to get power consumption data.
- `powermetrics` requires root access to run. This can be done by adding `your_username ALL=(ALL) NOPASSWD: /usr/bin/powermetrics` to `/etc/sudoers` (replace `your_username` with your actual username):
```
echo "your_username ALL=(ALL) NOPASSWD: /usr/bin/powermetrics" | sudo tee -a /etc/sudoers
```
- Alternatively, one can run **carbontracker** with root privileges.

## Running **carbontracker** in Virtual Machines

In virtual machines or containerized environments where direct power measurements are unavailable, **carbontracker** estimates power consumption using [CPU TDP values](https://github.com/mlco2/codecarbon/blob/master/codecarbon/data/hardware/cpu_power.csv):

- Identifies the CPU model when possible
- Uses 50% of the CPU's TDP value to estimate power consumption at 50% utilization
- Falls back to 50% of average TDP across known CPUs if the specific model isn't found

While less precise than direct measurements, this provides reasonable power consumption estimates in virtualized environments.