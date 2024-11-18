import os
import re

import numpy as np

from carbontracker import exceptions
from typing import Dict, Union, List


def parse_all_logs(log_dir):
    """
    Parse all logs in directory.

    Args:
        log_dir (str): Directory of logs

    Returns:
        (dict[]): List of log entries of shape

                {
                    "output_filename": str,
                    "standard_filename": str,
                    "components": dict, # See parse_logs
                    "early_stop": bool,
                    "actual": dict | None, # See get_consumption
                    "pred": dict | None, # See get_consumption
                }
    """
    logs = []
    output_logs, std_logs = get_all_logs(log_dir)

    for out, std in zip(output_logs, std_logs):
        with open(std, "r") as f:
            std_log_data = f.read()

        with open(out, "r") as f:
            output_log_data = f.read()

        actual, pred = get_consumption(output_log_data)
        early_stop = get_early_stop(std_log_data)
        entry = {
            "output_filename": out,
            "standard_filename": std,
            "components": parse_logs(log_dir, std, out),
            "early_stop": early_stop,
            "actual": actual,
            "pred": pred,
        }
        logs.append(entry)

    return logs


def parse_logs(log_dir, std_log_file=None, output_log_file=None):
    """
    Parse logs in log_dir (defaults to most recent logs).

    Args:
        log_dir (str): Directory of logs
        std_log_file (str, optional): Log file to read. Defaults to most recent logs.
        output_log_file (str, optional): Deprecated

    Returns:
        (dict): Dictionary of shape

                {
                        [component name]: {
                            "avg_power_usages (W)": NDArray | None,
                            "avg_energy_usages (J)": NDArray | None,
                            "epoch_durations (s)": NDArray | None,
                            "devices": str[],
                        }
                }

            where `[component name]` is either `"gpu"` or `"cpu"`.
            Return value can contain both `"gpu"` and `"cpu"` field.
    """
    if std_log_file is None or output_log_file is None:
        std_log_file, output_log_file = get_most_recent_logs(log_dir)

    with open(std_log_file, "r") as f:
        std_log_data = f.read()

    epoch_durations = get_epoch_durations(std_log_data)
    avg_power_usages = get_avg_power_usages(std_log_data)
    devices = get_devices(std_log_data)

    components = {}
    for comp, devices in devices.items():
        power_usages = (
            np.array(avg_power_usages[comp]) if len(avg_power_usages) != 0 else None
        )
        durations = np.array(epoch_durations) if len(epoch_durations) != 0 else None
        if power_usages is None or durations is None:
            energy_usages = None
        else:
            if power_usages.size != durations.size:
                raise exceptions.MismatchedEpochsError(
                    f"Found {power_usages.size} power measurements and {durations.size} duration measurements. "
                    "Expected equal number of measurements."
                )
            energy_usages = (power_usages.T * durations).T
        measurements = {
            "avg_power_usages (W)": power_usages,
            "avg_energy_usages (J)": energy_usages,
            "epoch_durations (s)": durations,
            "devices": devices,
        }
        components[comp] = measurements

    return components


def get_consumption(output_log_data: str):
    """
    Gets actual and predicted energy consumption, CO2eq and equivalence statements from output_log_data using regular expressions.

    Args:
        output_log_data (str): Log data to search through.

    Returns:
        actual (dict | None): Actual consumption

        pred (dict | None): Predicted consumption

            Both `actual` and `pred` has the shape:

                {
                    "epochs": int,
                    "duration (s)": int,
                    "energy (kWh)": float | None,
                    "co2eq (g)": float | None,
                    "equivalents": equivalents,
                }
    """
    actual_re = re.compile(
        r"(?i)Actual consumption"
        r"(?:\s*for\s+\d+\s+epochs)?"
        r"[\s\S]*?Time:\s*(.*)\n\s*Energy:\s*(.*)\s+kWh"
        r"[\s\S]*?CO2eq:\s*(.*)\s+g"
        r"(?:\s*This is equivalent to:\s*([\s\S]*?))?(?=\d{4}-\d{2}-\d{2}|\Z)"
    )
    pred_re = re.compile(
        r"(?i)Predicted consumption for (\d*) epoch\(s\):"
        r"[\s\S]*?Time:\s*(.*)\n\s*Energy:\s*(.*)\s+kWh"
        r"[\s\S]*?CO2eq:\s*(.*)\s+g"
        r"(?:\s*This is equivalent to:\s*([\s\S]*?))?(?=\d{4}-\d{2}-\d{2}|\Z)"
    )
    actual_match = re.search(actual_re, output_log_data)
    pred_match = re.search(pred_re, output_log_data)
    actual = extract_measurements(actual_match)
    pred = extract_measurements(pred_match)
    return actual, pred


def get_early_stop(std_log_data: str) -> bool:
    early_stop_re = re.compile(r"(?i)Training was interrupted")
    early_stop = re.findall(early_stop_re, std_log_data)
    return bool(early_stop)

def extract_measurements(match):
    if not match:
        return None
    match = match.groups()
    if len(match) == 4:
        match = [1] + list(match)
    epochs = int(match[0])
    duration = get_time(match[1])
    energy, co2eq, equivalents = get_stats(match)
    measurements = {
        "epochs": epochs,
        "duration (s)": duration,
        "energy (kWh)": energy,
        "co2eq (g)": co2eq,
        "equivalents": equivalents,
    }
    return measurements


def get_time(time_str: str) -> Union[float, None]:
    duration_re = re.compile(r"(\d+):(\d{2}):(\d\d?(?:.\d{2})?)")
    match = re.search(duration_re, time_str)
    if not match:
        return None
    match = match.groups()
    duration = float(match[0]) * 60 * 60 + float(match[1]) * 60 + float(match[2])
    return duration


def print_aggregate(log_dir):
    """
    Prints the aggregate consumption in all log files in log_dir to stdout. See `get_aggregate`.

    Args:
        log_dir (str): Directory of logs
    """
    energy, co2eq, equivalents = aggregate_consumption(log_dir)

    equivalents_p = " or ".join([f"{v:.16f} {k}" for k, v in equivalents.items()])

    printable = f"The training of models in this work is estimated to use {energy:.16f} kWh of electricity contributing to {co2eq / 1000:.16f} kg of CO2eq. "
    if equivalents_p:
        printable += f"This is equivalent to {equivalents_p}. "

    printable += "Measured by carbontracker (https://github.com/lfwa/carbontracker)."

    print(printable)


def aggregate_consumption(log_dir):
    """
    Aggregate consumption in all log files in specified log_dir.

    Args:
        log_dir (str): Directory of logs

    Returns:
        total_energy (float): Total energy (kWh) of all logs
        total_co2 (float): Total CO2eq (gCO2eq) of all logs
        total_equivalents (float): Total energy of all logs
    """
    output_logs, std_logs = get_all_logs(log_dir=log_dir)

    total_energy = 0
    total_co2eq = 0
    total_equivalents = {}

    for output_log, std_log in zip(output_logs, std_logs):
        with open(output_log, "r") as f:
            output_data = f.read()
        with open(std_log, "r") as f:
            std_data = f.read()

        actual, pred = get_consumption(output_data)
        early_stop = get_early_stop(std_data)

        if actual is None and pred is None:
            continue
        elif actual is None and pred is not None:
            energy = pred["energy (kWh)"]
            co2eq = pred["co2eq (g)"]
            equivalents = pred["equivalents"]
        elif pred is None and actual is not None:
            energy = actual["energy (kWh)"]
            co2eq = actual["co2eq (g)"]
            equivalents = actual["equivalents"]
        # Both actual and pred is available
        elif pred is not None and actual is not None:
            actual_epochs = actual["epochs"]
            pred_epochs = pred["epochs"]
            if early_stop or actual_epochs == pred_epochs:
                energy = actual["energy (kWh)"]
                co2eq = actual["co2eq (g)"]
                equivalents = actual["equivalents"]
            else:
                energy = pred["energy (kWh)"]
                co2eq = pred["co2eq (g)"]
                equivalents = pred["equivalents"]
        else:
            continue  # unreachable case

        total_energy += energy
        if not np.isnan(co2eq):
            total_co2eq += co2eq
        if equivalents is not None:
            for key, value in equivalents.items():
                total_equivalents[key] = total_equivalents.get(key, 0) + value

    return total_energy, total_co2eq, total_equivalents


def get_stats(groups):
    energy = float(groups[2])
    co2eq = float(groups[3])
    if len(groups) >= 5 and groups[4] is not None:
        equivalents = parse_equivalents(groups[4])
    else:
        equivalents = None
    return energy, co2eq, equivalents


def parse_equivalents(lines):
    equivalents = {}
    lines = lines.split("\n")
    for line in lines:
        tup = line.split(" ", 1)
        if tup[0] and tup[1]:
            try:
                equivalents[tup[1].strip()] = float(tup[0].strip())
            except ValueError as e:
                print(
                    f"Warning: Unable to convert '{tup[0]}' to float. Skipping this equivalent."
                )
                continue
    return equivalents


def get_all_logs(log_dir):
    """
    Get all output and standard logs in log_dir.

    Args:
        log_dir (str): Directory of logs

    Returns:
        std_logs (list[str]): List of file names of standard logs
        output_logs (list[str]): List of file names of output logs

    Raises:
        MismatchedLogFilesError: Thrown if there exists standard log files that cannot be matched with an output log file or vice versa.
    """
    files = [
        os.path.join(log_dir, f)
        for f in os.listdir(log_dir)
        if os.path.isfile(os.path.join(log_dir, f))
        and os.path.getsize(os.path.join(log_dir, f)) > 0
    ]
    output_re = re.compile(r".*carbontracker_output.log")
    std_re = re.compile(r".*carbontracker.log")
    output_logs = sorted(list(filter(output_re.match, files)))
    std_logs = sorted(list(filter(std_re.match, files)))
    if len(output_logs) != len(std_logs):
        # Try to remove the files with no matching output/std logs
        op_fn = [f.split("_carbontracker")[0] for f in output_logs]
        std_fn = [f.split("_carbontracker")[0] for f in std_logs]
        if len(std_logs) > len(output_logs):
            missing_logs = list(set(std_fn) - set(op_fn))
            [std_logs.remove(f + "_carbontracker.log") for f in missing_logs]
        else:
            missing_logs = list(set(op_fn) - set(std_fn))
            [output_logs.remove(f + "_carbontracker_output.log") for f in missing_logs]
        ### Even after removal if then there is a mismatch, then throw the error
        if len(output_logs) != len(std_logs):
            raise exceptions.MismatchedLogFilesError(
                f"Found {len(output_logs)} output logs and {len(std_logs)} "
                "standard logs. Expected equal number of logs."
            )
    return output_logs, std_logs


def get_devices(std_log_data: str) -> Dict[str, List[str]]:
    """
    Retrieve dictionary of components with their device(s).

    Args:
        std_log_data (str): Log data to parse

    Returns:
        (dict): Dictionary with devices per component of shape

                {
                        [component]: ["device1", "device2"]
                }

            Where `[component]` is the component name and `"device1"`, `"device2"` are device names.
    """
    comp_re = re.compile(r"The following components were found:(.*)\n")
    device_re = re.compile(r" (.*?) with device\(s\) (.*?)\.")
    # Take first match as we only expect one.
    match = re.findall(comp_re, std_log_data)
    if not match:
        return {}
    device_matches = re.findall(device_re, match[0])
    devices = {}

    for comp, device_str in device_matches:
        dev = device_str.split(",")
        devices[comp.lower()] = dev

    return devices


def get_epoch_durations(std_log_data):
    """
    Retrieve epoch durations (s).

    Args:
        std_log_data (str): Log to parse

    Returns:
        (list[float]): List of epoch durations (s)
    """
    duration_re = re.compile(r"Duration: (\d+):(\d{2}):(\d\d?(?:.\d{2})?)")
    matches = re.findall(duration_re, std_log_data)
    epoch_durations = [
        float(h) * 60 * 60 + float(m) * 60 + float(s) for h, m, s in matches
    ]
    return epoch_durations


def get_avg_power_usages(std_log_data):
    """
    Retrieve average power usages for each epoch (W).

    Args:
        std_log_data (str): Log to parse

    Returns:
        (dict): Dictionary containing list of average power usages for each epoch per component. Has shape:
                {
                        [component name]: list[list[float]]
                }
    """
    power_re = re.compile(r"Average power usage \(W\) for (.+): (\[?[0-9\.]+\]?|None)")
    matches = re.findall(power_re, std_log_data)
    components = list(set([comp for comp, _ in matches]))
    avg_power_usages = {}

    for component in components:
        powers: list[list[float]] = []
        for comp, power in matches:
            if comp == component:
                if power == "None":
                    powers.append([0.0])
                    continue
                else:
                    p_list = power.strip("[").strip("]").split(" ")
                    p_power = [float(num) for num in p_list if num != ""]
                    powers.append(p_power)
        avg_power_usages[component] = powers

    return avg_power_usages


def get_most_recent_logs(log_dir):
    """
    Retrieve the file names of the most recent standard and output logs.

    Args:
        log_dir (str): Directory of logs

    Returns:
        std_log (str): File name of latest standard log
        output_log (str): File name of latest output log
    """
    # Get all files in log_dir.
    files = [
        os.path.join(log_dir, f)
        for f in os.listdir(log_dir)
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
