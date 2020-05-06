"""Utilities to query NVIDIA GPUs.

This module provides utilities to query NVIDIA GPUs using NVIDIA Management
Library (NVML). It is important to run nvmlInit() before any queries are made
and nvmlShutdown() after all queries are finished. For performance, it is
recommended to run nvmlInit() and nvmlShutdown() as few times as possible, e.g.
by running queries in batches (initializing and shutdown after each query can
result in more than a 10x slowdown).
"""
import pynvml

from carbontracker.components.handler import Handler


class NvidiaGPU(Handler):
    def devices(self):
        """Retrieves the name of all GPUs in a list.

        Note:
            Requires NVML to be initialized.
        """
        device_count = pynvml.nvmlDeviceGetCount()
        devices = []

        for index in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(handle)
            devices.append(name.decode("utf-8"))

        return devices

    def available(self):
        """Checks if NVML and any GPUs are available."""
        try:
            self.init()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                available = True
            self.shutdown()
        except pynvml.NVMLError:
            available = False
        return available

    def _power_usage_by_index(self, index):
        """Retrieves power usage (W) of a GPU by index.

        Note:
            Requires NVML to be initialized.

        Args:
            index (int): Index of the GPU.

        Returns:
            Instantaneous power usage of GPU in W. None on failure to retrieve.
        """
        handle = pynvml.nvmlDeviceGetHandleByIndex(index)
        try:
            # Retrieves power usage in mW, divide by 1000 to get in W.
            power_usage = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
        except pynvml.NVMLError:
            power_usage = None
        return power_usage

    def power_usage(self):
        """Retrieves power usages (W) of all GPUs in a list.

        Note:
            Requires NVML to be initialized.
        """
        gpu_power_usages = []
        device_count = pynvml.nvmlDeviceGetCount()

        for index in range(device_count):
            power_usage = self._power_usage_by_index(index)
            gpu_power_usages.append(power_usage)

        return gpu_power_usages

    def init(self):
        pynvml.nvmlInit()

    def shutdown(self):
        pynvml.nvmlShutdown()
