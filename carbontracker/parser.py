import os
import re
import json

import numpy as np


def parse_logs(log_dir, std_log_file=None, output_log_file=None):
    """Parse logs in log_dir (defaults to most recent logs)."""
    # TODO: Output log is not parsed since this can easily be
    # retrieved manually.
    if std_log_file is None or output_log_file is None:
        std_log_file, output_log_file = get_most_recent_logs(log_dir)

    with open(std_log_file, "r") as f:
        std_log_data = f.read()

    epoch_durations = get_epoch_durations(std_log_data)
    avg_power_usages = get_avg_power_usages(std_log_data)
    devices = get_devices(std_log_data)

    components = {}

    for comp, devices in devices.items():
        power_usages = np.array(avg_power_usages[comp])
        durations = np.array(epoch_durations)
        energy_usages = (power_usages.T * durations).T.tolist()
        measurements = {
            "avg_power_usages (W)": avg_power_usages[comp],
            "avg_energy_usages (J)": energy_usages,
            "epoch_durations (s)": epoch_durations,
            "devices": devices
        }
        components[comp] = measurements

    return components


def get_devices(std_log_data):
    """Retrieve dictionary of components with their device(s)."""
    comp_re = re.compile(r"The following components were found:(.*)\n")
    device_re = re.compile(r" (.*?) with device\(s\) (.*?)\.")
    # Take first match as we only expect one.
    match = re.findall(comp_re, std_log_data)[0]
    device_matches = re.findall(device_re, match)
    devices = {}

    for comp, device_str in device_matches:
        dev = device_str.split(',')
        devices[comp.lower()] = dev

    return devices


def get_epoch_durations(std_log_data):
    """Retrieve epoch durations (s)."""
    duration_re = re.compile(r"Duration: (\d+):(\d{2}):(\d{2})")
    matches = re.findall(duration_re, std_log_data)
    epoch_durations = [
        int(h) * 60 * 60 + int(m) * 60 + int(s) for h, m, s in matches
    ]
    return epoch_durations


def get_avg_power_usages(std_log_data):
    """Retrieve average power usages for each epoch (W)."""
    power_re = re.compile(r"Average power usage \(W\) for (.+): (\[.+\])")
    matches = re.findall(power_re, std_log_data)
    components = list(set([comp for comp, _ in matches]))
    avg_power_usages = {}

    for component in components:
        powers = [
            json.loads(power) for comp, power in matches if comp == component
        ]
        avg_power_usages[component] = powers

    return avg_power_usages


def get_most_recent_logs(log_dir):
    """Retrieve the file names of the most recent standard and output logs."""
    # Get all files in log_dir.
    files = [
        os.path.join(log_dir, f) for f in os.listdir(log_dir)
        if os.path.isfile(os.path.join(log_dir, f))
    ]
    # Find output and standard logs and sort by modified date.
    output_re = re.compile(r".*carbontracker_output.log")
    std_re = re.compile(r".*carbontracker.log")
    output_logs = list(filter(output_re.match, files))
    std_logs = list(filter(std_re.match, files))
    output_logs.sort(key=os.path.getmtime)
    std_logs.sort(key=os.path.getmtime)

    return std_logs[-1], output_logs[-1]
