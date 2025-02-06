import os
import re
import time

from carbontracker import exceptions
from carbontracker.components.handler import Handler
from typing import List, Union

# RAPL Literature:
# https://www.researchgate.net/publication/322308215_RAPL_in_Action_Experiences_in_Using_RAPL_for_Power_Measurements

RAPL_DIR = "/sys/class/powercap/"
CPU = 0
DRAM = 2
MEASURE_DELAY = 1


class IntelCPU(Handler):
    def __init__(self, pids: List, devices_by_pid: bool):
        super().__init__(pids, devices_by_pid)
        self._handler = None

    def devices(self) -> List[str]:
        """Returns the name of all RAPL Domains"""
        return self._devices

    def available(self) -> bool:
        return os.path.exists(RAPL_DIR) and bool(os.listdir(RAPL_DIR))

    def power_usage(self) -> List[float]:
        before_measures = self._get_measurements()
        time.sleep(MEASURE_DELAY)
        after_measures = self._get_measurements()
        # Ensure all power measurements >= 0 and retry up to 3 times.
        attempts = 3
        while attempts > 0:
            attempts -= 1
            power_usages = [
                self._compute_power(before, after)
                for before, after in zip(before_measures, after_measures)
            ]
            if all(power >= 0 for power in power_usages):
                return power_usages
        default = [0.0 for device in range(len(self._devices))]
        return default

    def _compute_power(self, before: int, after: int) -> float:
        """Compute avg. power usage from two samples in microjoules."""
        joules = (after - before) / 1000000
        watt = joules / MEASURE_DELAY
        return watt

    def _read_energy(self, path: str) -> int:
        with open(os.path.join(path, "energy_uj"), "r") as f:
            return int(f.read())

    def _get_measurements(self):
        measurements = []
        permission_errors = []
        for package in self._rapl_devices:
            try:
                power_usage = self._read_energy(os.path.join(RAPL_DIR, package))
                measurements.append(power_usage)
            # If there is no sudo access, we cannot read the energy_uj file.
            # Permission denied error is raised.
            except PermissionError:
                permission_errors += [os.path.join(RAPL_DIR, package, "energy_uj")]

            except FileNotFoundError:
                # check cpu/gpu/dram
                parts = [
                    f
                    for f in os.listdir(os.path.join(RAPL_DIR, package))
                    if re.match(self.parts_pattern, f)
                ]
                total_power_usage = 0
                for part in parts:
                    total_power_usage += self._read_energy(
                        os.path.join(RAPL_DIR, package, part)
                    )

                measurements.append(total_power_usage)
        if permission_errors:
            raise exceptions.IntelRaplPermissionError(permission_errors)
        return measurements

    def _convert_rapl_name(self, package, name, pattern) -> Union[None, str]:
        match = re.match(pattern, package)
        name = name if "package" not in name else "cpu"
        if match:
            return name + ":" + match.group(1)

    def init(self):
        # Get amount of intel-rapl folders
        packages = list(filter(lambda x: ":" in x, os.listdir(RAPL_DIR)))
        self.device_count = len(packages)
        self._devices: List[str] = []
        self._rapl_devices: List[str] = []
        self.parts_pattern = re.compile(r"intel-rapl:(\d):(\d)")
        devices_pattern = re.compile(r"intel-rapl:(\d)(:\d)?")

        for package in packages:
            if re.fullmatch(devices_pattern, package):
                with open(os.path.join(RAPL_DIR, package, "name"), "r") as f:
                    name = f.read().strip()
                if name != "psys" and ("package" in name or "dram" in name):
                    self._rapl_devices.append(package)
                    rapl_name = self._convert_rapl_name(package, name, devices_pattern)
                    if rapl_name is not None:
                        self._devices.append(rapl_name)

    def shutdown(self):
        pass
