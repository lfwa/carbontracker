import os
import re
import json

import numpy as np

from carbontracker import exceptions


def parse_all_logs(log_dir):
    components_per_log = []
    output_logs, std_logs = get_all_logs(log_dir)

    for out, std in zip(output_logs, std_logs):
        components_per_log.append(parse_logs(log_dir, std, out))

    return components_per_log


def parse_logs(log_dir, std_log_file=None, output_log_file=None):
    """Parse logs in log_dir (defaults to most recent logs)."""
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
        energy_usages = (power_usages.T * durations).T
        measurements = {
            "avg_power_usages (W)": power_usages,
            "avg_energy_usages (J)": energy_usages,
            "epoch_durations (s)": durations,
            "devices": devices
        }
        components[comp] = measurements

    return components


def print_aggregate(log_dir):
    """Prints the aggregate consumption in all log files in log_dir."""
    energy, co2eq, equivalents = aggregate_consumption(log_dir)

    equivalents_p = " or ".join(
        [f"{v:.3f} {k}" for k, v in equivalents.items()])

    printable = f"The training of models in this work is estimated to use {energy:.3f} kWh of electricity contributing to {co2eq / 1000:.3f} kg of CO2eq. "
    if equivalents_p:
        printable += f"This is equivalent to {equivalents_p}. "

    printable += "Measured by carbontracker (https://github.com/lfwa/carbontracker)."

    print(printable)


def aggregate_consumption(log_dir):
    """Aggregate consumption in all log files in specified log_dir."""
    early_stop_re = re.compile(r"(?i)Training was interrupted")
    actual_re = re.compile(
        r"(?i)Actual consumption for (\d*) epoch\(s\):\n\s*(?i)Time:\s*(.*)\n\s*(?i)Energy:\s*(.*)\s+kWh\n\s*(?i)CO2eq:\s*(.*)\s+g\n\s*This is equivalent to:\n([\S\s]*?)\n\d{4}-\d{2}-\d{2}"
    )
    pred_re = re.compile(
        r"(?i)Predicted consumption for (\d*) epoch\(s\):\n\s*(?i)Time:\s*(.*)\n\s*(?i)Energy:\s*(.*)\s+kWh\n\s*(?i)CO2eq:\s*(.*)\s+g\n\s*This is equivalent to:\n([\S\s]*?)\n\d{4}-\d{2}-\d{2}"
    )

    output_logs, std_logs = get_all_logs(log_dir=log_dir)

    total_energy = 0
    total_co2eq = 0
    total_equivalents = {}

    for output_log, std_log in zip(output_logs, std_logs):
        with open(output_log, "r") as f:
            output_data = f.read()
        with open(std_log, "r") as f:
            std_data = f.read()

        early_stop = re.findall(early_stop_re, std_data)
        actual = re.search(actual_re, output_data).groups()
        pred = re.search(pred_re, output_data).groups()
        actual_epochs = int(actual[0])
        pred_epochs = int(pred[0])

        if early_stop or actual_epochs == pred_epochs:
            energy, co2eq, equivalents = get_stats(actual)
        else:
            energy, co2eq, equivalents = get_stats(pred)

        total_energy += energy
        total_co2eq += co2eq
        for key, value in equivalents.items():
            total_equivalents[key] = total_equivalents.get(key, 0) + value

    return total_energy, total_co2eq, total_equivalents


def get_stats(groups):
    energy = float(groups[2])
    co2eq = float(groups[3])
    equivalents = parse_equivalents(groups[4])
    return energy, co2eq, equivalents


def parse_equivalents(lines):
    equivalents = {}
    lines = lines.split("\n")
    for line in lines:
        tup = line.split(" ", 1)
        equivalents[tup[1]] = float(tup[0])
    return equivalents


def get_all_logs(log_dir):
    """Get all output and standard logs in log_dir."""
    files = [
        os.path.join(log_dir, f) for f in os.listdir(log_dir)
        if os.path.isfile(os.path.join(log_dir, f))
    ]
    output_re = re.compile(r".*carbontracker_output.log")
    std_re = re.compile(r".*carbontracker.log")
    output_logs = sorted(list(filter(output_re.match, files)))
    std_logs = sorted(list(filter(std_re.match, files)))
    if len(output_logs) != len(std_logs):
        raise exceptions.MismatchedLogFilesError(
            f"Found {len(output_logs)} output logs and {len(std_logs)} "
            "standard logs. Expected equal number of logs.")
    return output_logs, std_logs


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
    duration_re = re.compile(r"Duration: (\d+):(\d{2}):(\d{2}(?:.\d{2})?)")
    matches = re.findall(duration_re, std_log_data)
    epoch_durations = [
        float(h) * 60 * 60 + float(m) * 60 + float(s) for h, m, s in matches
    ]
    return epoch_durations


def get_avg_power_usages(std_log_data):
    """Retrieve average power usages for each epoch (W)."""
    power_re = re.compile(r"Average power usage \(W\) for (.+): (\[.+\])")
    matches = re.findall(power_re, std_log_data)
    components = list(set([comp for comp, _ in matches]))
    avg_power_usages = {}

    for component in components:
        powers = []
        for comp, power in matches:
            if comp == component:
                p_list = power.strip("[").strip("]").split(" ")
                p_power = [float(num) for num in p_list if num != ""]
                powers.append(p_power)
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
