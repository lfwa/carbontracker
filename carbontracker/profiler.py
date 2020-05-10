import pickle
import pathlib
import os

from carbontracker import tracker
from carbontracker import loggerutil
from carbontracker.components import component


class CarbonProfiler:
    def __init__(self,
                 update_interval=10,
                 components="all",
                 log_dir=None,
                 pickle_dir=None):
        self.pickle_dir = pickle_dir
        if pickle_dir is not None:
            pathlib.Path(pickle_dir).mkdir(parents=True, exist_ok=True)
        self.logger = loggerutil.Logger(log_dir=log_dir)
        self.tracker = tracker.CarbonTrackerThread(
            components=component.create_components(components),
            logger=self.logger,
            ignore_errors=False,
            update_interval=update_interval)
        self.epoch_counter = 0

    def stop(self):
        self.tracker.stop()
        if self.pickle_dir is not None:
            self._pickle_results()

    def epoch_start(self):
        if self.epoch_counter == 0:
            self.tracker.begin()
        self.epoch_counter += 1
        self.tracker.epoch_start()

    def epoch_end(self):
        self.tracker.epoch_end()

    def _pickle_results(self):
        epoch_times = self.tracker.epoch_times
        components = []
        for comp in self.tracker.components:
            measurements = {
                "power_usages": comp.power_usages,
                "energy_usages": comp.energy_usage(epoch_times),
                "devices": comp.devices()
            }
            components.append((comp.name, measurements))
        pickle.dump(epoch_times,
                    open(os.path.join(self.pickle_dir, "epoch_times.p"), "wb"))
        pickle.dump(components,
                    open(os.path.join(self.pickle_dir, "components.p"), "wb"))


def load(pickle_dir):
    epoch_times = pickle.load(
        open(os.path.join(pickle_dir, "epoch_times.p"), "rb"))
    components = pickle.load(
        open(os.path.join(pickle_dir, "components.p"), "rb"))
    return epoch_times, components
