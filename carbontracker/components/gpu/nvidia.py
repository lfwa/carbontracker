"""Utilities to query NVIDIA GPUs.

This module provides utilities to query NVIDIA GPUs using NVIDIA Management
Library (NVML). It is important to run nvmlInit() before any queries are made
and nvmlShutdown() after all queries are finished. For performance, it is
recommended to run nvmlInit() and nvmlShutdown() as few times as possible, e.g.
by running queries in batches (initializing and shutdown after each query can
result in more than a 10x slowdown).
"""
import pynvml
import traceback

from carbontracker.components.handler import Handler


class NvidiaGPU(Handler):
    def devices(self):
        """Retrieves the name of all GPUs in a list.

        Note:
            Requires NVML to be initialized.
        """
        names = [pynvml.nvmlDeviceGetName(handle) for handle in self._handles]
        devices = [name.decode("utf-8") for name in names]
        return devices

    def available(self):
        """Checks if NVML and any GPUs are available."""
        try:
            self.init()
            if len(self._handles) > 0:
                available = True
            else:
                available = False
            self.shutdown()
        except pynvml.NVMLError:
            available = False
        return available

    def power_usage(self):
        """Retrieves instantaneous power usages (W) of all GPUs in a list.

        Note:
            Requires NVML to be initialized.
        """
        gpu_power_usages = []

        for handle in self._handles:
            try:
                # Retrieves power usage in mW, divide by 1000 to get in W.
                power_usage = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
            except pynvml.NVMLError:
                power_usage = None
            gpu_power_usages.append(power_usage)

        return gpu_power_usages

    def init(self):
        pynvml.nvmlInit()
        self._handles = self._get_active_devices()

    def shutdown(self):
        pynvml.nvmlShutdown()

    def _get_active_devices(self):
        """Get GPUs where at least one of the current processes are running.
        
        Note:
            Requires NVML to be initialized.
            If we cannot retrieve any PIDs at all on any GPUs then we assume
            the container was not started with --pid=host, which is a known
            NVML bug https://github.com/NVIDIA/nvidia-docker/issues/179.
        """
        device_count = pynvml.nvmlDeviceGetCount()
        fallback = []
        devices = []
        gpu_pids_available = False

        for index in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            fallback.append(handle)
            gpu_pids = [
                p.pid
                for p in pynvml.nvmlDeviceGetComputeRunningProcesses(handle) +
                pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
            ]

            if gpu_pids:
                gpu_pids_available = True

            if set(gpu_pids).intersection(self.pids):
                devices.append(handle)

        return devices if gpu_pids_available else fallback
