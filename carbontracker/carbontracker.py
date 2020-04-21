import time
import numpy as np
from threading import Thread

from carbontracker.components.gpu import gpu
from carbontracker.components.cpu import cpu
from carbontracker.emissions.intensity import intensity as ci
from carbontracker.emissions.conversion import co2eq

# TODO: use thread local data instead
# mydata = threading.local()
# mydata.x = 1
# https://docs.python.org/3/library/threading.html
# TODO: Support multiple epochs as well as logging for full training.
# TODO: Warning for training in high carbon intensity region? This could include how much could be saved by moving the job to a low impact region?
# TODO: Add redirect prints to different pipes.
class CarbonTrackerThread(Thread):
    def __init__(
            self,
            components,
            update_interval=10
        ):
        super(CarbonTrackerThread, self).__init__()
        self.name = "CarbonTrackerThread"
        self.update_interval = update_interval
        self.components = components
        self.running = True
        self.measuring = False

        self.start()
    
    def run(self):
        """Thread's activity."""
        while self.running:
            if not self.measuring:
                continue
            self.collect_measurements()
            time.sleep(self.update_interval)
        
        # TODO: On unexpected exits, should we run nvmlShutdown()?
        # Shutdown in thread's activity instead of epoch_end() to ensure that we
        # only shutdown after last measurement.
        self.components_shutdown()
    
    def epoch_start(self):
        self.components_remove_unavailable()
        self.components_init()
        self.measuring = True
        self.start_time = time.time()

    def epoch_end(self):
        self.epoch_time = time.time() - self.start_time
        self.measuring = False
        self.running = False

    def components_remove_unavailable(self):
        for component in self.components:
            if not component.available():
                self.components.remove(component)
    
    def components_init(self):
        for component in self.components:
            component.init()
    
    def components_shutdown(self):
        for component in self.components:
            component.shutdown()
    
    def collect_measurements(self):
        """Collect one round of measurements."""
        for component in self.components:
            component.collect_power_usage()
    
    def energy_usage(self, component, time):
        """Returns energy (kWh) used by component during time."""
        power_usage_means = np.mean(component.power_usages, axis=0)
        energy_usage = np.multiply(power_usage_means, time).sum()
        # Convert from J to kWh.
        energy_usage /= 3600000
        return energy_usage

    def total_energy_usage(self):
        """Retrieves the total energy (kWh) used by all components."""
        total_energy = 0
        for component in self.components:
            total_energy += self.energy_usage(component, self.epoch_time)
        return total_energy
    
    def co2eq(self, total_energy_usage):
        """Returns the CO2eq (g) of the total energy usage."""
        carbon_intensity = ci.carbon_intensity()
        co2eq = total_energy_usage * carbon_intensity
        return co2eq
    
    def co2eq_interpretable(self, g_co2eq):
        """Converts CO2eq (g) to interpretable units."""
        return co2eq_conversion.convert(g_co2eq)
    
    def predict_total(self, epochs, epoch_energy_usage, epoch_time):
        """Predicts energy (kWh) usage and time (s) of all epochs."""
        # TODO: Make a more advanced prediction based on trained model or similar.
        total_energy = epochs * epoch_energy_usage
        total_time = epochs * epoch_time
        return total_energy, total_time


# TODO: If we call a function of our thread object is that necesarrily run in another thread or only those in the run()? Should co2eq, co2eq_interpretable and carbon_intensity and stuff be fetched in a different thread or does it not matter since we only fetch when the first epoch is done?

class CarbonTracker:
    def __init__(
            self,
            epochs,
            update_interval=10,
            interpretable=True,
            stop_and_confirm=False,
            ignore_errors=False,
            components="all",
            #warnings=True,
            #logger=True,
            #monitor_epochs="all"
        ):
        self.epochs = epochs
        self.interpretable = interpretable
        self.stop_and_confirm = stop_and_confirm
        # TODO: If ignore_errors print instead of letting errors through.
        self.ignore_errors = ignore_errors

        comps = self._choose_components(components)
        self.tracker = CarbonTrackerThread(
            update_interval=update_interval,
            components=comps
        )
        
        self.deleted = False
    
    def epoch_start(self):
        if self.deleted:
            return
        
        self.tracker.epoch_start()
    
    def epoch_end(self):
        if self.deleted:
            return

        self.tracker.epoch_end()
        self._print()
        if self.stop_and_confirm:
            self._user_query()
        self._delete()
    
    def _choose_components(self, comp_str):
        components_dict = {
            "gpu": gpu.GPU(),
            "cpu": cpu.CPU()
        }
        components = []
        comp_str = comp_str.split(",")
        for comp in comp_str:
            if comp == "all":
                components = list(components_dict.values())
            else:
                component = components_dict.get(comp)
                if component is not None:
                    components.append(component)
                else:
                    raise Exception(f"Invalid component '{comp}' specified.")
        return components
    
    def _print_stats(self, description, time, energy, co2eq, conversions=None):
        print(description)
        print(f"\tTime: {time} s")
        print(f"\tEnergy: {energy} kWh")
        print(f"\tCO2eq: {co2eq} g")

        if conversions:
            print(f"\tThis is equivalent to:")
            for conversion in conversions:
                units, unit = conversion
                print(f"\t\t{units} {unit}")
    
    def _print(self):
        # TODO: Print stats for each component separately?
        epoch_energy = self.tracker.total_energy_usage()
        epoch_time = self.tracker.epoch_time
        epoch_co2eq = self.tracker.co2eq(epoch_energy)
        epoch_conversions = self.tracker.co2eq_interpretable(epoch_co2eq) if self.interpretable else []

        self._print_stats("First epoch:", epoch_time, epoch_energy, epoch_co2eq, epoch_conversions)

        total_energy, total_time = self.tracker.predict_total(self.epochs, epoch_energy, epoch_time)
        total_co2eq = self.tracker.co2eq(total_energy)
        total_conversions = self.tracker.co2eq_interpretable(total_co2eq) if self.interpretable else []

        self._print_stats(f"Prediction for {self.epochs} epochs:", total_time, total_energy, total_co2eq, total_conversions)

    
    def _user_query(self):
        print("Continue training (y/n)?")
        user_input = input()
        self._check_input(user_input)
    
    def _check_input(self, user_input):
        if user_input == "y":
            print("Continuing...")
            return
        elif user_input == "n":
            print("Quitting...")
            quit()
        else:
            print("Input not recognized. Try again (y/n):")
            user_input = input()
            self._check_input(user_input)
    
    def _delete(self):
        del self.tracker
        self.deleted = True