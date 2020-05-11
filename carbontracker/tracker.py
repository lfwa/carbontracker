import os
import sys
import time
import traceback
from threading import Thread

import numpy as np

from carbontracker import loggerutil
from carbontracker import predictor
from carbontracker import exceptions
from carbontracker.components import component
from carbontracker.emissions.intensity import intensity
from carbontracker.emissions.conversion import co2eq
from carbontracker.emissions.intensity.fetchers import co2signal


class CarbonTrackerThread(Thread):
    def __init__(self, components, logger, ignore_errors, update_interval=10):
        super(CarbonTrackerThread, self).__init__()
        self.name = "CarbonTrackerThread"
        self.components = components
        self.update_interval = update_interval
        self.ignore_errors = ignore_errors
        self.logger = logger
        self.epoch_times = []
        self.running = True
        self.measuring = False
        self.epoch_counter = 0
        self.daemon = True

        self.start()

    def run(self):
        """Thread's activity."""
        try:
            while self.running:
                if not self.measuring:
                    continue
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

        self.measuring = False
        self.running = False
        self.logger.info("Monitoring thread ended.")
        self.logger.output("Finished monitoring.")

    def epoch_start(self):
        self.epoch_counter += 1
        self.measuring = True
        self.cur_epoch_time = time.time()
        self.logger.info(f"Epoch {self.epoch_counter} started.")

    def epoch_end(self):
        self.measuring = False
        self.epoch_times.append(time.time() - self.cur_epoch_time)
        self.logger.info(f"Epoch {self.epoch_counter} ended.")
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
        for comp in self.components:
            duration = self.epoch_times[-1]
            epoch_power_usages = comp.power_usages[-1]
            self.logger.info(
                f"Duration: {loggerutil.convert_to_timestring(duration)}")
            self.logger.info(
                f"Power usages (W) for {comp.name}: {epoch_power_usages}")

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
        """Retrieves total energy (kWh) per epoch used by all components."""
        total_energy = np.zeros(len(self.epoch_times))
        for comp in self.components:
            energy_usage = comp.energy_usage(self.epoch_times)
            total_energy += energy_usage
        return total_energy

    def _handle_error(self, error):
        err_str = traceback.format_exc()
        if self.ignore_errors:
            err_str = (f"Ignored error: {err_str}Continued training without "
                       "monitoring...")

        self.logger.critical(err_str)
        self.logger.output(err_str)

        if self.ignore_errors:
            # Stop monitoring but continue training.
            self._delete()
        else:
            os._exit(os.EX_SOFTWARE)


class CarbonTracker:
    def __init__(self,
                 epochs,
                 epochs_before_pred=1,
                 monitor_epochs=1,
                 update_interval=10,
                 interpretable=True,
                 stop_and_confirm=False,
                 ignore_errors=False,
                 components="all",
                 log_dir=None,
                 verbose=0):
        self.epochs = epochs
        self.epochs_before_pred = (epochs if epochs_before_pred < 0 else
                                   epochs_before_pred)
        self.monitor_epochs = (epochs
                               if monitor_epochs < 0 else monitor_epochs)
        if (self.monitor_epochs == 0
                or self.monitor_epochs < self.epochs_before_pred):
            raise ValueError(
                "Argument monitor_epochs expected a value in "
                f"{{-1, >0, >=epochs_before_pred}}, got {monitor_epochs}.")
        self.interpretable = interpretable
        self.stop_and_confirm = stop_and_confirm
        self.ignore_errors = ignore_errors
        self.epoch_counter = 0
        self.deleted = False

        try:
            self.logger = loggerutil.Logger(log_dir=log_dir, verbose=verbose)
            self.tracker = CarbonTrackerThread(
                components=component.create_components(components),
                logger=self.logger,
                ignore_errors=ignore_errors,
                update_interval=update_interval)
        except Exception as e:
            self._handle_error(e)

    def epoch_start(self):
        if self.deleted:
            return

        try:
            if self.epoch_counter == 0:
                self.tracker.begin()
            self.tracker.epoch_start()
            self.epoch_counter += 1
        except Exception as e:
            self._handle_error(e)

    def epoch_end(self):
        if self.deleted:
            return

        try:
            self.tracker.epoch_end()

            if self.epoch_counter == self.monitor_epochs:
                self._output_actual()

            if self.epoch_counter == self.epochs_before_pred:
                self._output_pred()
                if self.stop_and_confirm:
                    self._user_query()

            if self.epoch_counter == self.monitor_epochs:
                self._delete()
        except Exception as e:
            self._handle_error(e)

    def set_api_keys(self, api_dict):
        """Set API keys (given as {name:key}) for carbon intensity fetchers."""
        try:
            for name, key in api_dict.items():
                if name.lower() == "co2signal":
                    co2signal.AUTH_TOKEN = key
                else:
                    raise exceptions.FetcherNameError(
                        f"Invalid API name '{name}' given.")
        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error):
        err_str = traceback.format_exc()
        if self.ignore_errors:
            err_str = (f"Ignored error: {err_str}Continued training without "
                       "monitoring...")

        self.logger.critical(err_str)
        self.logger.output(err_str)

        if self.ignore_errors:
            # Stop monitoring but continue training.
            self._delete()
        else:
            sys.exit(os.EX_SOFTWARE)

    def _output_energy(self, description, time, energy, co2eq, conversions):
        output = (f"\n{description}\n"
                  f"\tTime:\t{loggerutil.convert_to_timestring(time)}\n"
                  f"\tEnergy:\t{energy:.6f} kWh\n"
                  f"\tCO2eq:\t{co2eq:.6f} g")

        if conversions:
            conv_str = "\n\tThis is equivalent to:"
            for units, unit in conversions:
                conv_str += f"\n\t{units:.6f} {unit}"
            output += conv_str

        self.logger.output(output)

    def _output_actual(self):
        """Output actual usage so far."""
        energy_usages = self.tracker.total_energy_per_epoch()
        energy = energy_usages.sum()
        times = self.tracker.epoch_times
        time = np.sum(times)
        _co2eq = self._co2eq(energy)
        conversions = co2eq.convert(_co2eq) if self.interpretable else None

        self._output_energy(
            f"Actual consumption for {self.epoch_counter} epoch(s):", time,
            energy, _co2eq, conversions)

    def _output_pred(self):
        """Output predicted usage for full training epochs."""
        epoch_energy_usages = self.tracker.total_energy_per_epoch()
        epoch_times = self.tracker.epoch_times
        pred_energy = predictor.predict_energy(self.epochs,
                                               epoch_energy_usages)
        pred_time = predictor.predict_time(self.epochs, epoch_times)
        pred_co2eq = self._co2eq(pred_energy, pred_time)
        conversions = co2eq.convert(pred_co2eq) if self.interpretable else None

        self._output_energy(
            f"Predicted consumption for {self.epochs} epoch(s):", pred_time,
            pred_energy, pred_co2eq, conversions)

    def _co2eq(self, energy_usage, pred_time_dur=None):
        """"Returns the CO2eq (g) of the energy usage (kWh)."""
        ci = intensity.carbon_intensity(self.logger, pred_time_dur)
        co2eq = energy_usage * ci.carbon_intensity
        return co2eq

    def _user_query(self):
        self.logger.output("Continue training (y/n)?")
        user_input = input().lower()
        self._check_input(user_input)

    def _check_input(self, user_input):
        if user_input == "y":
            self.logger.output("Continuing...")
            return
        elif user_input == "n":
            self.logger.info("Session ended by user.")
            self.logger.output("Quitting...")
            sys.exit(os.EX_OK)
        else:
            self.logger.output("Input not recognized. Try again (y/n):")
            user_input = input().lower()
            self._check_input(user_input)

    def _delete(self):
        self.tracker.stop()
        del self.logger
        del self.tracker
        self.deleted = True
