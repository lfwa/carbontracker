import os
import time
import numpy as np
import traceback
from threading import Thread

from carbontracker import loggerutil
from carbontracker import predictor
from carbontracker import exceptions
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
        self._log_components_info()
        self.logger.info("Monitoring thread started.")

    def stop(self):
        if self.running == False:
            return

        self.measuring = False
        self.running = False
        self.logger.info("Monitoring thread ended.")
    
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
        if not self.components:
            raise exceptions.NoComponentsAvailableError()
        else:
            log = ["The following components were found:"]
            for component in self.components:
                name = component.name
                devices = ", ".join(component.devices())
                log.append(f" {name} with device(s) {devices}.")
            log_str = " ".join(log)
            self.logger.info(log_str)
            self.logger.output(log_str, verbose_level=1)
    
    def _log_epoch_measurements(self):
        for component in self.components:
            epoch_power_usages = component.power_usages[-1]
            self.logger.info(f"Power usages for {component.name}: {epoch_power_usages}.")

    def _components_remove_unavailable(self):
        self.components = [comp for comp in self.components if comp.available()]
    
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
                self._output()
                if self.stop_and_confirm:
                    self._user_query()

            if self.epoch_counter == self.monitor_epochs:
                self._delete()
        except Exception as e:
            self._handle_error(e)
    
    def _handle_error(self, error):
        err_str = traceback.format_exc()

        if self.ignore_errors:
            err_str = f"Ignored error: {err_str}Continued training..."
            self.logger.critical(err_str)
            self.logger.output(err_str)
            self._delete()
        else:
            # TODO: Stop training in main thread.
            self.logger.critical(err_str)
            raise error
    
    def _output_energy(self, description, time, energy, co2eq, conversions):
        output = (f"\n{description}\n"
                  f"\tTime: {time} s\n"
                  f"\tEnergy: {energy} kWh\n"
                  f"\tCO2eq: {co2eq} g")

        if conversions:
            conv_str = "\n\tThis is equivalent to:"
            for units, unit in conversions:
                conv_str += f"\n\t{units} {unit}"
            output += conv_str

        self.logger.output(output)
    
    def _output(self):
        # Measurements from before prediction epochs.
        epoch_energy_usages = self.tracker.total_energy_per_epoch()
        epoch_energy = epoch_energy_usages.sum()
        epoch_times = self.tracker.epoch_times
        epoch_times = np.sum(epoch_times)
        # Predictions.
        pred_energy = predictor.predict_energy(self.epochs, epoch_energy_usages)
        pred_time = predictor.predict_time(self.epochs, epoch_times)
        
        # CO2eq and conversions.
        epoch_co2eq, pred_co2eq = self._co2eq(epoch_energy, pred_energy, pred_time)
        epoch_conversions = co2eq.convert(epoch_co2eq) if self.interpretable else None
        pred_conversions = co2eq.convert(pred_co2eq) if self.interpretable else None

        # Output measurements and predictions.
        self._output_energy(f"First {self.epochs_before_pred} epoch(s):", epoch_times, epoch_energy, epoch_co2eq, epoch_conversions)
        self._output_energy(f"Prediction for {self.epochs} epoch(s):", pred_time, pred_energy, pred_co2eq, pred_conversions)
    
    def _co2eq(self, epoch_energy_usage, pred_energy_usage, pred_time_dur=None):
        """Returns the CO2eq (g) of the total energy usage."""
        epoch_ci = intensity.carbon_intensity()
        epoch_co2eq = epoch_energy_usage * epoch_ci.carbon_intensity

        self.logger.output(epoch_ci.message, verbose_level=2)
        self.logger.info(epoch_ci.message)

        pred_ci = intensity.carbon_intensity(time_dur=pred_time_dur)
        # If query is not a success or a prediction,
        # we default to the epoch carbon intensity.
        if pred_ci.success and pred_ci.is_prediction:
            self.logger.output(pred_ci.message, verbose_level=2)
            self.logger.info(pred_ci.message)
        else:
            self.logger.info(pred_ci.message)
            pred_ci = epoch_ci
            self.logger.info("Defaulted to carbon intensity for epoch in prediction of total carbon footprint.")
        pred_co2eq = pred_energy_usage * pred_ci.carbon_intensity
        
        return epoch_co2eq, pred_co2eq

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