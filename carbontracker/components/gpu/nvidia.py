"""Utilities to query NVIDIA GPUs.

This module provides utilities to query NVIDIA GPUs using NVIDIA Management
Library (NVML). It is important to run nvmlInit() before any queries are made
and nvmlShutdown() after all queries are finished. For performance, it is
recommended to run nvmlInit() and nvmlShutdown() as few times as possible, e.g.
by running queries in batches (initializing and shutdown after each query can
result in more than a 10x slowdown).
"""

import sys

import pynvml
import os

from carbontracker import exceptions
from carbontracker.components.handler import Handler
from typing import List, Union


class NvidiaGPU(Handler):
    def __init__(self, pids: List[int], devices_by_pid: bool):
        super().__init__(pids, devices_by_pid)
        self._handles = []

    def devices(self) -> List[str]:
        """
        Note:
            Requires NVML to be initialized.
        """
        names = [pynvml.nvmlDeviceGetName(handle) for handle in self._handles]

        # Decode names if Python version is less than 3.9
        if sys.version_info < (3, 10):
            names = [name.decode() for name in names]

        return names

    def available(self) -> bool:
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

    def power_usage(self) -> List[float]:
        """Retrieves instantaneous power usages (W) of all GPUs in a list.

        Note:
            Requires NVML to be initialized.
        """
        gpu_power_usages = []

        for handle in self._handles:
            try:
                # Retrieves power usage in mW, divide by 1000 to get in W.
                power_usage = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
                gpu_power_usages.append(power_usage)
            except pynvml.NVMLError:
                raise exceptions.GPUPowerUsageRetrievalError()
        return gpu_power_usages

    def init(self):
        pynvml.nvmlInit()
        if self.devices_by_pid:
            self._handles = self._get_handles_by_pid()
        else:
            self._handles = self._get_handles()

    def shutdown(self):
        pynvml.nvmlShutdown()
        self._handles = []

    def _get_handles(self) -> List:
        """Returns handles of GPUs in slurm job if existent otherwise all
        available GPUs."""
        device_indices = self._slurm_gpu_indices()

        # If we cannot retrieve indices from slurm then we retrieve all GPUs.
        if not device_indices:
            device_count = pynvml.nvmlDeviceGetCount()
            device_indices = range(device_count)

        return [pynvml.nvmlDeviceGetHandleByIndex(i) for i in device_indices]

    def _slurm_gpu_indices(self) -> Union[List[int], None]:
        """Returns indices of GPUs for the current slurm job if existent.

        Note:
            Relies on the environment variable CUDA_VISIBLE_DEVICES to not
            overwritten. Alternative variables could be SLURM_JOB_GPUS and
            GPU_DEVICE_ORDINAL.
        """
        index_str = os.environ.get("CUDA_VISIBLE_DEVICES")
        try:
            indices = (
                [int(i) for i in index_str.split(",")]
                if index_str is not None
                else None
            )
        except:
            indices = None
        return indices

    def _get_handles_by_pid(self) -> List:
        """Returns handles of GPU running at least one process from PIDS.

        Note:
            GPUs need to have started work before showing any processes.
            Requires NVML to be initialized.
            Bug: Containers need to be started with --pid=host for NVML to show
            processes: https://github.com/NVIDIA/nvidia-docker/issues/179.
        """
        device_count = pynvml.nvmlDeviceGetCount()
        devices = []

        for index in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            gpu_pids = [
                p.pid
                for p in pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                + pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
            ]

            if set(gpu_pids).intersection(self.pids):
                devices.append(handle)

        return devices
