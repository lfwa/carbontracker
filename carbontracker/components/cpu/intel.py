import os
import re
import time

from carbontracker.components.handler import Handler

# RAPL Literature:
# https://www.researchgate.net/publication/322308215_RAPL_in_Action_Experiences_in_Using_RAPL_for_Power_Measurements

RAPL_DIR = "/sys/class/powercap/"
CPU = 0
DRAM = 2
MEASURE_DELAY = 1


class IntelCPU(Handler):
    def devices(self):
        """Returns the name of all RAPL Domains"""
        return self._devices

    def available(self):
        return os.path.exists(RAPL_DIR) and bool(os.listdir(RAPL_DIR))

    def power_usage(self):
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

    def _compute_power(self, before, after):
        """Compute avg. power usage from two samples in microjoules."""
        joules = (after - before) / 1000000
        watt = joules / MEASURE_DELAY
        return watt

    def _read_energy(self, path):
        with open(os.path.join(path, "energy_uj"), 'r') as f:
            return int(f.read())

    def _get_measurements(self):
        measurements = []
        for package in self._rapl_devices:
            try:
                power_usage = self._read_energy(os.path.join(
                    RAPL_DIR, package))
                measurements.append(power_usage)
            except FileNotFoundError:
                # check cpu/gpu/dram
                parts = [
                    f for f in os.listdir(os.path.join(RAPL_DIR, package))
                    if re.match(self.parts_pattern, f)
                ]
                total_power_usage = 0
                for part in parts:
                    total_power_usage += self._read_energy(
                        os.path.join(RAPL_DIR, package, part))

                measurements.append(total_power_usage)

        return measurements

    def _convert_rapl_name(self, name, pattern):
        if re.match(pattern, name):
            return "cpu:" + name[-1]

    def init(self):
        # Get amount of intel-rapl folders
        packages = list(filter(lambda x: ':' in x, os.listdir(RAPL_DIR)))
        self.device_count = len(packages)
        self._devices = []
        self._rapl_devices = []
        self.parts_pattern = re.compile(r"intel-rapl:(\d):(\d)")
        devices_pattern = re.compile("intel-rapl:.")

        for package in packages:
            if re.fullmatch(devices_pattern, package):
                with open(os.path.join(RAPL_DIR, package, "name"), "r") as f:
                    name = f.read().strip()
                if name != "psys":
                    self._rapl_devices.append(package)
                    self._devices.append(
                        self._convert_rapl_name(package, devices_pattern))

    def shutdown(self):
        pass
