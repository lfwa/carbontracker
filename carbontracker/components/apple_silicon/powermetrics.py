import platform
import subprocess
import re
import time
from carbontracker.components.handler import Handler
from typing import Union, List, Pattern


class PowerMetricsUnified:
    _output: Union[None, str] = None
    _last_updated: Union[None, float] = None

    @staticmethod
    def get_output():
        if (
            PowerMetricsUnified._output is None
            or PowerMetricsUnified._last_updated is None
            or time.time() - PowerMetricsUnified._last_updated > 1
        ):
            PowerMetricsUnified._output = subprocess.check_output(
                ["sudo", "powermetrics", "-n", "1", "-i", "100", "--samplers", "all"],
                universal_newlines=True,
            )
            PowerMetricsUnified._last_updated = time.time()
        return PowerMetricsUnified._output


class AppleSiliconCPU(Handler):
    def init(self, pids=None, devices_by_pid=False):
        self.devices_list = ["CPU"]
        self.cpu_pattern = re.compile(r"CPU Power: (\d+) mW")

    def shutdown(self):
        pass

    def devices(self) -> List[str]:
        """Returns a list of devices (str) associated with the component."""
        return self.devices_list

    def available(self) -> bool:
        return platform.system() == "Darwin"

    def power_usage(self) -> List[float]:
        output = PowerMetricsUnified.get_output()
        cpu_power = self.parse_power(output, self.cpu_pattern)
        return [cpu_power]

    def parse_power(self, output: str, pattern: Pattern[str]) -> float:
        match = pattern.search(output)
        if match:
            power = float(match.group(1)) / 1000  # Convert mW to W
            return power
        else:
            return 0.0


class AppleSiliconGPU(Handler):
    def init(self, pids=None, devices_by_pid=False):
        self.devices_list = ["GPU", "ANE"]
        self.gpu_pattern = re.compile(r"GPU Power: (\d+) mW")
        self.ane_pattern = re.compile(r"ANE Power: (\d+) mW")

    def devices(self) -> List[str]:
        """Returns a list of devices (str) associated with the component."""
        return self.devices_list

    def available(self) -> bool:
        return platform.system() == "Darwin"

    def power_usage(self):
        output = PowerMetricsUnified.get_output()
        gpu_power = self.parse_power(output, self.gpu_pattern)
        ane_power = self.parse_power(output, self.ane_pattern)
        return [gpu_power + ane_power]

    def parse_power(self, output: str, pattern: Pattern[str]) -> float:
        match = pattern.search(output)
        if match:
            power = float(match.group(1)) / 1000  # Convert mW to W (J/s)
            return power
        else:
            return 0.0
        
    def shutdown(self):
        pass
