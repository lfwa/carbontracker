import numpy as np

from carbontracker import exceptions
from carbontracker.components.gpu import nvidia
from carbontracker.components.cpu import intel, generic
from carbontracker.components.apple_silicon.powermetrics import (
    AppleSiliconCPU,
    AppleSiliconGPU,
)
from carbontracker.components.handler import Handler
from typing import Iterable, List, Union, Type, Sized
from carbontracker.loggerutil import Logger
import os
from carbontracker.components.cpu.sim_cpu import SimulatedCPUHandler
from carbontracker.components.gpu.sim_gpu import SimulatedGPUHandler

COMPONENTS = [
    {
        "name": "gpu",
        "error": exceptions.GPUError("No GPU(s) available."),
        "handlers": [nvidia.NvidiaGPU, AppleSiliconGPU],
    },
    {
        "name": "cpu",
        "error": exceptions.CPUError("No CPU(s) available."),
        "handlers": [intel.IntelCPU, AppleSiliconCPU, generic.GenericCPU],
    },
]


def component_names() -> List[str]:
    return [comp["name"] for comp in COMPONENTS]


def error_by_name(name) -> Exception:
    for comp in COMPONENTS:
        if comp["name"] == name:
            return comp["error"]
    raise exceptions.ComponentNameError()


def handlers_by_name(
    name, 
    sim_cpu=None, 
    sim_cpu_tdp=None, 
    sim_cpu_util=None,
    sim_gpu=None, 
    sim_gpu_watts=None,
    sim_gpu_util=None
):
    for comp in COMPONENTS:
        if comp["name"] == name:
            if name == "cpu" and sim_cpu is not None and sim_cpu_tdp is not None:
                return [lambda pids, devices_by_pid: SimulatedCPUHandler(
                    sim_cpu, 
                    float(sim_cpu_tdp),
                    float(sim_cpu_util) if sim_cpu_util is not None else 0.5
                )]
            elif name == "gpu" and sim_gpu is not None and sim_gpu_watts is not None:
                return [lambda pids, devices_by_pid: SimulatedGPUHandler(
                    sim_gpu, 
                    float(sim_gpu_watts),
                    float(sim_gpu_util) if sim_gpu_util is not None else 0.5
                )]
            return comp["handlers"]
    raise exceptions.ComponentNameError()


class Component:
    def __init__(
        self, 
        name: str, 
        pids: Iterable[int], 
        devices_by_pid: bool, 
        logger: Logger, 
        sim_cpu=None,
        sim_cpu_tdp=None,
        sim_cpu_util=None,
        sim_gpu=None,
        sim_gpu_watts=None,
        sim_gpu_util=None
    ):
        self.name = name
        if name not in component_names():
            raise exceptions.ComponentNameError(
                f"No component found with name '{self.name}'."
            )
        self._handler = self._determine_handler(
            pids=pids, 
            devices_by_pid=devices_by_pid, 
            sim_cpu=sim_cpu,
            sim_cpu_tdp=sim_cpu_tdp,
            sim_cpu_util=sim_cpu_util,
            sim_gpu=sim_gpu,
            sim_gpu_watts=sim_gpu_watts,
            sim_gpu_util=sim_gpu_util
        )
        self.power_usages: List[List[float]] = []
        self.cur_epoch: int = -1
        self.logger = logger

    @property
    def handler(self) -> Handler:
        if self._handler is None:
            raise error_by_name(self.name)
        return self._handler

    def _determine_handler(
        self, 
        pids: Iterable[int], 
        devices_by_pid: bool, 
        sim_cpu=None,
        sim_cpu_tdp=None,
        sim_cpu_util=None,
        sim_gpu=None,
        sim_gpu_watts=None,
        sim_gpu_util=None
    ) -> Union[Handler, None]:
        handlers = handlers_by_name(
            self.name, 
            sim_cpu=sim_cpu,
            sim_cpu_tdp=sim_cpu_tdp,
            sim_cpu_util=sim_cpu_util,
            sim_gpu=sim_gpu,
            sim_gpu_watts=sim_gpu_watts,
            sim_gpu_util=sim_gpu_util
        )
        for h in handlers:
            handler = h(pids=pids, devices_by_pid=devices_by_pid) if callable(h) else h(pids=pids, devices_by_pid=devices_by_pid)
            if handler.available():
                return handler
        return None

    def devices(self) -> List[str]:
        return self.handler.devices()

    def available(self) -> bool:
        return self._handler is not None

    def collect_power_usage(self, epoch: int):
        if epoch < 1:
            return

        if epoch != self.cur_epoch:
            self.cur_epoch = epoch
            # If we haven't measured for some epochs due to too slow
            # update_interval, we copy previous epoch measurements s.t.
            # there exists measurements for every epoch.
            diff = self.cur_epoch - len(self.power_usages) - 1
            if diff != 0:
                for _ in range(diff):
                    # Copy previous measurement lists.
                    latest_measurements = (
                        self.power_usages[-1] if self.power_usages else []
                    )
                    self.power_usages.append(latest_measurements)
            self.power_usages.append([])
        try:
            self.power_usages[-1] += self.handler.power_usage()
        except exceptions.IntelRaplPermissionError as e:
            energy_paths = " and ".join(e.file_names)
            commands = ["sudo chmod +r " + energy_path for energy_path in e.file_names]
            # Only raise error if no measurements have been collected.
            if not self.power_usages[-1]:
                self.logger.err_critical(
                    "Could not read CPU/DRAM energy consumption due to lack of read-permissions.\n\tPlease run the following command(s): \n\t\t" + "\n\t\t".join(commands)
                    )
            # Append zero measurement to avoid further errors.
            self.power_usages.append([0])
        except exceptions.GPUPowerUsageRetrievalError:
            if not self.power_usages[-1]:
                self.logger.err_critical(
                    "GPU model does not support retrieval of power usages in NVML."
                    "\nSee issue: https://github.com/lfwa/carbontracker/issues/36"
                )
                # Append zero measurement to avoid further errors.
                self.power_usages.append([0])

    def energy_usage(self, epoch_times: List[int]) -> List[int]:
        """Returns energy (mWh) used by component per epoch."""
        energy_usages = []
        # We have to compute each epoch in a for loop since numpy cannot
        # handle lists of uneven length.
        for idx, (power, time) in enumerate(zip(self.power_usages, epoch_times)):
            # If no power measurement exists, try to use measurements from
            # later epochs.
            while not power and idx != len(self.power_usages) - 1:
                idx += 1
                power = self.power_usages[idx]
            if not power:
                power = [[0]]
            avg_power_usage = np.mean(power, axis=0)
            energy_usage = np.multiply(avg_power_usage, time).sum()
            # Convert from J to kWh.
            if energy_usage != 0:
                energy_usage /= 3600000
            energy_usages.append(energy_usage)

        # Ensure energy_usages and epoch_times have same length by
        # copying latest measurement if it exists.
        diff = len(epoch_times) - len(energy_usages)
        if diff != 0:
            for _ in range(0, diff):
                # TODO: Warn that no measurements have been fetched.
                latest_energy = energy_usages[-1] if energy_usages else 0
                energy_usages.append(latest_energy)

        return energy_usages

    def init(self):
        self.handler.init()

    def shutdown(self):
        self.handler.shutdown()


def create_components(
    components: str, 
    pids: Iterable[int], 
    devices_by_pid: bool, 
    logger: Logger, 
    sim_cpu=None,
    sim_cpu_tdp=None,
    sim_cpu_util=None,
    sim_gpu=None,
    sim_gpu_watts=None,
    sim_gpu_util=None
) -> List[Component]:
    components = components.strip().replace(" ", "").lower()
    if components == "all":
        return [
            Component(
                name=comp_name, 
                pids=pids, 
                devices_by_pid=devices_by_pid, 
                logger=logger, 
                sim_cpu=sim_cpu,
                sim_cpu_tdp=sim_cpu_tdp,
                sim_cpu_util=sim_cpu_util,
                sim_gpu=sim_gpu,
                sim_gpu_watts=sim_gpu_watts,
                sim_gpu_util=sim_gpu_util
            )
            for comp_name in component_names()
        ]
    else:
        return [
            Component(
                name=comp_name, 
                pids=pids, 
                devices_by_pid=devices_by_pid, 
                logger=logger, 
                sim_cpu=sim_cpu,
                sim_cpu_tdp=sim_cpu_tdp,
                sim_cpu_util=sim_cpu_util,
                sim_gpu=sim_gpu,
                sim_gpu_watts=sim_gpu_watts,
                sim_gpu_util=sim_gpu_util
            )
            for comp_name in components.split(",")
        ]
