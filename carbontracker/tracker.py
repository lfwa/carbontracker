import os
import sys
import time
import traceback
import psutil
import math
from threading import Thread, Event
from typing import List, Union

import numpy as np
from random import randint

from carbontracker import constants
from carbontracker import loggerutil
from carbontracker import predictor
from carbontracker import exceptions
from carbontracker.components import component
from carbontracker.components.component import Component
from carbontracker.emissions.intensity import intensity
from carbontracker.emissions.conversion import co2eq
from carbontracker.emissions.intensity.fetchers import electricitymaps


class CarbonIntensityThread(Thread):
    """Sleeper thread to update Carbon Intensity every 15 minutes."""

    def __init__(self, logger, stop_event, update_interval: Union[float, int] = 900):
        super(CarbonIntensityThread, self).__init__()
        self.name = "CarbonIntensityThread"
        self.logger = logger
        self.update_interval: Union[float, int] = update_interval
        self.daemon = True
        self.stop_event = stop_event
        self.carbon_intensities = []

        self.start()

    def run(self):
        try:
            self._fetch_carbon_intensity()
            while not self.stop_event.wait(self.update_interval):
                self._fetch_carbon_intensity()
        except Exception:
            err_str = traceback.format_exc()
            self.logger.err_warn(err_str)

    def _fetch_carbon_intensity(self):
        ci = intensity.carbon_intensity(self.logger)
        if (
            ci.success
            and isinstance(ci.carbon_intensity, (int, float))
            and not np.isnan(ci.carbon_intensity)
        ):
            self.carbon_intensities.append(ci)

    def predict_carbon_intensity(self, pred_time_dur):
        ci = intensity.carbon_intensity(self.logger, time_dur=pred_time_dur)
        weighted_intensities = [
            ci.carbon_intensity for ci in self.carbon_intensities
        ] + [ci.carbon_intensity]

        # Account for measured intensities by taking weighted average.
        weight = math.floor(pred_time_dur / self.update_interval)

        for _ in range(weight):
            weighted_intensities.append(ci.carbon_intensity)

        ci.carbon_intensity = np.mean(weighted_intensities)
        intensity.set_carbon_intensity_message(ci, pred_time_dur)

        self.logger.info(ci.message)
        self.logger.output(ci.message, verbose_level=2)

        return ci

    def average_carbon_intensity(self):
        if not self.carbon_intensities:
            ci = intensity.carbon_intensity(self.logger)
            self.carbon_intensities.append(ci)

        # Ensure that we have some carbon intensities.
        assert self.carbon_intensities

        location = self.carbon_intensities[-1].address
        intensities = [ci.carbon_intensity for ci in self.carbon_intensities]
        avg_intensity = np.mean(intensities)
        msg = (
            f"Average carbon intensity during training was {avg_intensity:.2f}"
            f" gCO2/kWh at detected location: {location}."
        )
        avg_ci = intensity.CarbonIntensity(
            carbon_intensity=avg_intensity, message=msg, success=True
        )

        self.logger.info(
            "Carbon intensities (gCO2/kWh) fetched every "
            f"{self.update_interval} s at detected location {location}: "
            f"{intensities}"
        )
        self.logger.info(avg_ci.message)
        self.logger.output(avg_ci.message, verbose_level=2)

        return avg_ci


class CarbonTrackerThread(Thread):
    """Thread to fetch consumptions"""

    def __init__(
        self,
        components: List[Component],
        logger,
        ignore_errors,
        delete,
        update_interval: Union[int, float] = 1,
    ):
        super(CarbonTrackerThread, self).__init__()
        self.cur_epoch_time = time.time()
        self.name = "CarbonTrackerThread"
        self.delete = delete
        self.components = components
        self.update_interval = update_interval
        self.ignore_errors = ignore_errors
        self.logger = logger
        self.epoch_times = []
        self.running = True
        self.measuring_event = Event()
        self.epoch_counter = 0
        self.daemon = True

        self.start()

    def run(self):
        """Thread's activity."""
        try:
            self.begin()
            while self.running:
                # Wait for the measuring_event to be set
                self.measuring_event.wait()
                self._collect_measurements()
                time.sleep(self.update_interval)

            # Shutdown in thread's activity instead of epoch_end() to ensure
            # that we only shutdown after last measurement.
            self._components_shutdown()
        except Exception as e:
            self._handle_error(e)

    def begin(self):
        self._components_remove_unavailable()
        self._components_init()
        self._log_components_info()
        self.logger.info("Monitoring thread started.")

    def stop(self):
        if not self.running:
            return

        self.running = False
        self.logger.info("Monitoring thread ended.")
        self.logger.output("Finished monitoring.", verbose_level=1)

    def epoch_start(self):
        self.epoch_counter += 1
        self.cur_epoch_time = time.time()
        self.measuring_event.set()  # Set the event to start measuring

    def epoch_end(self):
        self.measuring_event.clear()  # Clear the event to stop measuring
        self.epoch_times.append(time.time() - self.cur_epoch_time)
        self._log_epoch_measurements()

    def _log_components_info(self):
        log = ["The following components were found:"]
        for comp in self.components:
            name = comp.name.upper()
            devices = ", ".join(comp.devices())
            log.append(f"{name} with device(s) {devices}.")
        log_str = " ".join(log)
        self.logger.info(log_str)
        self.logger.output(log_str, verbose_level=1)

    def _log_epoch_measurements(self):
        self.logger.info(f"Epoch {self.epoch_counter}:")
        duration = self.epoch_times[-1]
        self.logger.info(
            f"Duration: {loggerutil.convert_to_timestring(duration, True)}"
        )
        for comp in self.components:
            if comp.power_usages and comp.power_usages[-1]:
                power_avg = np.mean(comp.power_usages[-1], axis=0)
                # If np.mean is calculated during a measurement, it will get an
                # empty list and return nan, if this is the case we take the
                #  previous measurement.
                # TODO: Use semaphores to wait for measurement to finish.
                if np.isnan(power_avg).all():
                    power_avg = (
                        np.mean(comp.power_usages[-2], axis=0)
                        if len(comp.power_usages) >= 2
                        else None
                    )
            else:
                self.logger.err_warn(
                    "Epoch duration is too short for a measurement to be " "collected."
                )
                power_avg = None

            self.logger.info(f"Average power usage (W) for {comp.name}: {power_avg}")

    def _components_remove_unavailable(self):
        self.components = [cmp for cmp in self.components if cmp.available()]
        if not self.components:
            raise exceptions.NoComponentsAvailableError()

    def _components_init(self):
        for comp in self.components:
            comp.init()

    def _components_shutdown(self):
        for comp in self.components:
            comp.shutdown()

    def _collect_measurements(self):
        """Collect one round of measurements."""
        for comp in self.components:
            comp.collect_power_usage(self.epoch_counter)

    def total_energy_per_epoch(self):
        """Retrieves total energy (kWh) per epoch used by all components
        including PUE."""
        total_energy = np.zeros(len(self.epoch_times))
        for comp in self.components:
            energy_usage = comp.energy_usage(self.epoch_times)
            total_energy += energy_usage
        return total_energy * constants.PUE_2023

    def _handle_error(self, error):
        err_str = traceback.format_exc()
        if self.ignore_errors:
            err_str = (
                f"Ignored error: {err_str}Continued training without " "monitoring..."
            )

        self.logger.err_critical(err_str)
        self.logger.output(err_str)

        if self.ignore_errors:
            # Stop monitoring but continue training.
            self.delete()
        else:
            os._exit(70)


class CarbonTracker:
    """

    The CarbonTracker class is the main interface for starting, stopping and reporting through **carbontracker**.

    Args:
        epochs (int): Total epochs of your training loop.
        api_keys (dict, optional): Dictionary of Carbon Intensity API keys following the {name:key} format. Can also be set using `CarbonTracker.set_api_keys`

            Example: `{ \\"electricitymaps\\": \\"abcdefg\\" }`
        epochs_before_pred (int, optional): Epochs to monitor before outputting predicted consumption. Set to -1 for all epochs. Set to 0 for no prediction.
        monitor_epochs (int, optional): Total number of epochs to monitor. Outputs actual consumption when reached. Set to -1 for all epochs. Cannot be less than `epochs_before_pred` or equal to 0.
        update_interval (int, optional): Interval in seconds between power usage measurements are taken by sleeper thread.
        interpretable (bool, optional): If set to `True` then the CO2eq are also converted to interpretable numbers such as the equivalent distance travelled in a car, etc. Otherwise, no conversions are done.
        stop_and_confirm (bool, optional): If set to `True` then the main thread (with your training loop) is paused after epochs_before_pred epochs to output the prediction and the user will need to confirm to continue training. Otherwise, prediction is output and training is continued instantly.
        ignore_errors (bool, optional): If set to `True` then all errors will cause energy monitoring to be stopped and training will continue. Otherwise, training will be interrupted as with regular errors.
        components (str, optional): Comma-separated string of which components to monitor. Options are: `"all"`, `"gpu"`, `"cpu"`, or `"gpu,cpu"`.
        devices_by_pid (bool, optional): If `True`, only devices (under the chosen components) running processes associated with the main process are measured. If False, all available devices are measured. Note that this requires your devices to have active processes before instantiating the CarbonTracker class.
        log_dir (str, optional): Path to the desired directory to write log files. If `None`, then no logging will be done.
        log_file_prefix (str, optional): Prefix to add to the log file name.
        verbose (int, optional): Sets the level of verbosity.
        decimal_precision (int, optional): Desired decimal precision of reported values.

    Example:
        Tracking the carbon intensity of PyTorch model training:

            from carbontracker.tracker import CarbonTracker

            tracker = CarbonTracker(epochs=max_epochs)
            # Training loop.
            for epoch in range(max_epochs):
                tracker.epoch_start()
                # Your model training.
                tracker.epoch_end()

            # Optional: Add a stop in case of early termination before all monitor_epochs has
            # been monitored to ensure that actual consumption is reported.
            tracker.stop()

    """

    def __init__(
        self,
        epochs,
        epochs_before_pred=1,
        monitor_epochs=-1,
        update_interval=1,
        interpretable=True,
        stop_and_confirm=False,
        ignore_errors=False,
        components="all",
        devices_by_pid=False,
        log_dir=None,
        log_file_prefix="",
        verbose=1,
        decimal_precision=12,
        api_keys=None,
    ):
        if api_keys is not None:
            self.set_api_keys(api_keys)

        self.epochs = epochs
        self.epochs_before_pred = (
            epochs if epochs_before_pred < 0 else epochs_before_pred
        )
        self.monitor_epochs = epochs if monitor_epochs < 0 else monitor_epochs
        if self.monitor_epochs == 0 or self.monitor_epochs < self.epochs_before_pred:
            raise ValueError(
                "Argument monitor_epochs expected a value in "
                f"{{-1, >0, >=epochs_before_pred}}, got {monitor_epochs}."
            )
        self.interpretable = interpretable
        self.stop_and_confirm = stop_and_confirm
        self.ignore_errors = ignore_errors
        self.epoch_counter = 0
        self.decimal_precision = decimal_precision
        self.deleted = False

        try:
            pids = self._get_pids()
            self.logger = loggerutil.Logger(
                log_dir=log_dir,
                verbose=verbose,
                log_prefix=log_file_prefix,
                logger_id=str(randint(1, 999999)),
            )
            self.tracker = CarbonTrackerThread(
                delete=self._delete,
                components=component.create_components(
                    components=components, pids=pids, devices_by_pid=devices_by_pid, logger=self.logger
                ),
                logger=self.logger,
                ignore_errors=ignore_errors,
                update_interval=update_interval,
            )
            self.intensity_stopper = Event()
            self.intensity_updater = CarbonIntensityThread(
                self.logger, self.intensity_stopper
            )
        except Exception as e:
            self._handle_error(e)

    def epoch_start(self):
        """
        Starts tracking energy consumption for current epoch. Call in the beginning of training loop.
        """
        if self.deleted:
            return

        try:
            self.tracker.epoch_start()
            self.epoch_counter += 1
        except Exception as e:
            self._handle_error(e)

    def epoch_end(self):
        """
        Ends tracking energy consumption for current epoch. Call in the end of training loop.
        """
        if self.deleted:
            return

        try:
            self.tracker.epoch_end()

            if self.epoch_counter == self.epochs_before_pred:
                self._output_pred()
                if self.stop_and_confirm:
                    self._user_query()

            if self.epoch_counter == self.monitor_epochs:
                self._output_actual()

            if self.epoch_counter == self.monitor_epochs:
                self._delete()
        except Exception as e:
            self._handle_error(e)

    def stop(self):
        """Ensure that tracker is stopped and deleted. E.g. use with early
        stopping, where not all monitor_epochs have been run."""
        if self.deleted:
            return
        self.logger.info(
            f"Training was interrupted before all {self.monitor_epochs} epochs"
            " were monitored."
        )
        # Decrement epoch_counter with 1 since measurements for ultimate epoch
        # was interrupted and is not accounted for.
        self.epoch_counter -= 1
        self._output_actual()
        self._delete()

    def set_api_keys(self, api_dict):
        """Set API keys (given as {name:key}) for carbon intensity fetchers."""
        try:
            for name, key in api_dict.items():
                if name.lower() == "electricitymaps":
                    electricitymaps.ElectricityMap.set_api_key(key)
                else:
                    raise exceptions.FetcherNameError(
                        f"Invalid API name '{name}' given."
                    )
        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error):
        err_str = traceback.format_exc()
        if self.ignore_errors:
            err_str = (
                f"Ignored error: {err_str}Continued training without " "monitoring..."
            )

        self.logger.err_critical(err_str)
        self.logger.output(err_str)

        if self.ignore_errors:
            # Stop monitoring but continue training.
            self._delete()
        else:
            sys.exit(70)

    def _output_energy(self, description, time, energy, co2eq, conversions):
        precision = self.decimal_precision
        output = (
            f"\n{description}\n"
            f"\tTime:\t{loggerutil.convert_to_timestring(time)}\n"
            f"\tEnergy:\t{energy:.{precision}f} kWh\n"
            f"\tCO2eq:\t{co2eq:.{precision}f} g"
        )

        if conversions:
            conv_str = "\n\tThis is equivalent to:"
            for units, unit in conversions:
                conv_str += f"\n\t{units:.{precision}f} {unit}"
            output += conv_str

        self.logger.output(output, verbose_level=1)

    def _output_actual(self):
        """Output actual usage so far."""
        energy_usages = self.tracker.total_energy_per_epoch()
        energy = energy_usages.sum()
        times = self.tracker.epoch_times
        time = np.sum(times)
        _co2eq = self._co2eq(energy)
        conversions = co2eq.convert(_co2eq) if self.interpretable else None
        if self.epochs_before_pred == 0:
            self._output_energy(
                "Actual consumption:", time, energy, _co2eq, conversions
            )
        else:
            self._output_energy(
                f"Actual consumption for {self.epoch_counter} epoch(s):",
                time,
                energy,
                _co2eq,
                conversions,
            )

    def _output_pred(self):
        """Output predicted usage for full training epochs."""
        epoch_energy_usages = self.tracker.total_energy_per_epoch()
        epoch_times = self.tracker.epoch_times
        pred_energy = predictor.predict_energy(self.epochs, epoch_energy_usages)
        pred_time = predictor.predict_time(self.epochs, epoch_times)
        pred_co2eq = self._co2eq(pred_energy, pred_time)
        conversions = co2eq.convert(pred_co2eq) if self.interpretable else None

        self._output_energy(
            f"Predicted consumption for {self.epochs} epoch(s):",
            pred_time,
            pred_energy,
            pred_co2eq,
            conversions,
        )

    def _co2eq(self, energy_usage, pred_time_dur=None):
        """ "Returns the CO2eq (g) of the energy usage (kWh)."""
        if pred_time_dur:
            ci = self.intensity_updater.predict_carbon_intensity(pred_time_dur)
        else:
            ci = self.intensity_updater.average_carbon_intensity()
        co2eq = energy_usage * ci.carbon_intensity
        return co2eq

    def _user_query(self):
        self.logger.output("Continue training (y/n)?")
        user_input = input().lower()
        self._check_input(user_input)

    def _check_input(self, user_input: str):
        if user_input == "y":
            self.logger.output("Continuing...")
            return
        elif user_input == "n":
            self.logger.info("Session ended by user.")
            self.logger.output("Quitting...")
            sys.exit(0)
        else:
            self.logger.output("Input not recognized. Try again (y/n):")
            user_input = input().lower()
            self._check_input(user_input)

    def _delete(self):
        self.tracker.stop()
        self.intensity_stopper.set()
        del self.logger
        del self.tracker
        del self.intensity_updater
        del self.intensity_stopper
        self.deleted = True

    def _get_pids(self) -> List[int]:
        """Get current process id and all children process ids."""
        process = psutil.Process()
        pids = [process.pid] + [child.pid for child in process.children(recursive=True)]
        return pids
