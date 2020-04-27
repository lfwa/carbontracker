import os
import time
import numpy as np
import traceback
from threading import Thread

from carbontracker import loggerutil
from carbontracker import predictor
from carbontracker.components import component
from carbontracker.emissions.intensity import intensity
from carbontracker.emissions.conversion import co2eq


# TODO: MONITORING MODULE
# TODO: Warning for training in high carbon intensity region? This could include how much could be saved by moving the job to a low impact region?
class CarbonTrackerThread(Thread):
    def __init__(
            self,
            components,
            logger,
            update_interval=10,
        ):
        super(CarbonTrackerThread, self).__init__()
        self.name = "CarbonTrackerThread"
        self.components = components
        self.update_interval = update_interval
        self.logger = logger
        self.epoch_times = []
        self.running = True
        self.measuring = False
        self.epoch_counter = 0

        self.start()
    
    def run(self):
        """Thread's activity."""
        while self.running:
            if not self.measuring:
                continue
            self._collect_measurements()
            time.sleep(self.update_interval)
        
        # TODO: On unexpected exits, should we run nvmlShutdown()?
        # Shutdown in thread's activity instead of epoch_end() to ensure that we
        # only shutdown after last measurement.
        self._components_shutdown()
    
    def begin(self):
        self._components_remove_unavailable()
        self._components_init()
        self.measuring = True
        self.logger.info("Monitoring thread started.")

    def stop(self):
        if self.running == False:
            return

        self.measuring = False
        self.running = False
        self.logger.info("Monitoring thread ended.")
    
    def epoch_start(self):
        self.epoch_counter += 1
        self.cur_epoch_time = time.time()
        self.logger.info(f"Epoch {self.epoch_counter} started.")

    def epoch_end(self):
        self.epoch_times.append(time.time() - self.cur_epoch_time)
        self.logger.info(f"Epoch {self.epoch_counter} ended.")

    def _components_remove_unavailable(self):
        self.components = [comp for comp in self.components if comp.available()]
        # TODO: Print which devices were found and their names.
    
    def _components_init(self):
        for component in self.components:
            component.init()
    
    def _components_shutdown(self):
        for component in self.components:
            component.shutdown()
    
    def _collect_measurements(self):
        """Collect one round of measurements."""
        for component in self.components:
            component.collect_power_usage(self.epoch_counter)

    def total_energy_per_epoch(self):
        """Retrieves the total energy (kWh) per epoch used by all components."""
        total_energy = np.zeros(len(self.epoch_times))
        for component in self.components:
            energy_usage = component.energy_usage(self.epoch_times)
            total_energy += energy_usage
        return total_energy
    
    def co2eq(self, total_energy_usage):
        """Returns the CO2eq (g) of the total energy usage."""
        # TODO: Print intensity information. Location and message.
        carbon_intensity = intensity.carbon_intensity().carbon_intensity
        co2eq = total_energy_usage * carbon_intensity
        return co2eq
    
    def co2eq_interpretable(self, g_co2eq):
        """Converts CO2eq (g) to interpretable units."""
        return co2eq.convert(g_co2eq)

    def predict_total(self, total_epochs, epoch_energy_usages, epoch_times):
        """Predicts energy (kWh) usage and time (s) of all epochs."""
        return predictor.predict_total(total_epochs, epoch_energy_usages, epoch_times)

class CarbonTracker:
    def __init__(
            self,
            epochs,
            epochs_before_pred=1, # Set to < 1 for all epochs.
            monitor_epochs=1, # Cannot be less than epochs_before_pred.
            update_interval=10,
            interpretable=True,
            stop_and_confirm=False,
            ignore_errors=False,
            components="all",
            log_dir=None,
            verbose=0
            #warnings=True,
        ):
        self.epochs = epochs
        self.epochs_before_pred = epochs_before_pred if epochs_before_pred > 0 else epochs
        if monitor_epochs < 0:
            self.monitor_epochs = epochs
        elif monitor_epochs < self.epochs_before_pred:
            self.monitor_epochs = self.epochs_before_pred
        else:
            self.monitor_epochs = monitor_epochs
        self.interpretable = interpretable
        self.stop_and_confirm = stop_and_confirm
        self.ignore_errors = ignore_errors
        self.epoch_counter = 0
        self.deleted = False

        try:
            self.logger = loggerutil.Logger(log_dir=log_dir)
            self.tracker = CarbonTrackerThread(
                components=component.create_components(components),
                logger = self.logger,
                update_interval=update_interval
            )
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
            if self.epoch_counter < self.epochs_before_pred:
                return
            
            if self.epoch_counter == self.monitor_epochs:
                self.tracker.stop()

            if self.epoch_counter == self.epochs_before_pred:
                self._print()
                if self.stop_and_confirm:
                    self._user_query()

            if self.epoch_counter == self.monitor_epochs:
                self._delete()
        except Exception as e:
            self._handle_error(e)
    
    def _handle_error(self, error):
        if self.ignore_errors:
            err_str = traceback.format_exc()
            self.logger.critical(err_str)
            self.logger.output(err_str)
        else:
            raise error
    
    def _print_stats(self, description, time, energy, co2eq, conversions=None):
        output = (f"{description}\n"
                  f"\tTime: {time} s\n"
                  f"\tEnergy: {energy} kWh\n"
                  f"\tCO2eq: {co2eq} g")

        if conversions:
            conv_str = "\n\tThis is equivalent to:"
            for units, unit in conversions:
                conv_str += f"\n\t{units} {unit}"
            output += conv_str

        self.logger.output(output)
    
    def _print(self):
        # TODO: Print stats for each component separately?
        epoch_energy_usages = self.tracker.total_energy_per_epoch()
        epoch_energy_usage = epoch_energy_usages.sum()
        epoch_times = self.tracker.epoch_times
        epoch_time = np.sum(epoch_times)
        epoch_co2eq = self.tracker.co2eq(epoch_energy_usage)
        epoch_conversions = self.tracker.co2eq_interpretable(epoch_co2eq) if self.interpretable else []

        total_energy, total_time = self.tracker.predict_total(self.epochs, epoch_energy_usages, epoch_times)
        total_co2eq = self.tracker.co2eq(total_energy)
        total_conversions = self.tracker.co2eq_interpretable(total_co2eq) if self.interpretable else []

        self._print_stats(f"First {self.epochs_before_pred} epoch(s):", epoch_time, epoch_energy_usage, epoch_co2eq, epoch_conversions)

        self._print_stats(f"Prediction for {self.epochs} epoch(s):", total_time, total_energy, total_co2eq, total_conversions)

    def _user_query(self):
        self.logger.output("Continue training (y/n)?")
        user_input = input()
        self._check_input(user_input)
    
    def _check_input(self, user_input):
        if user_input == "y":
            self.logger.output("Continuing...")
            return
        elif user_input == "n":
            self.logger.info("Session ended by user.")
            self.logger.output("Quitting...")
            os._exit(os.EX_OK)
        else:
            self.logger.output("Input not recognized. Try again (y/n):")
            user_input = input()
            self._check_input(user_input)
    
    def _delete(self):
        del self.logger
        del self.tracker
        self.deleted = True