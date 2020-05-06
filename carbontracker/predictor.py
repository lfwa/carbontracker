import numpy as np


# TODO: Do advanced prediction based on profiling work.
def predict_energy(total_epochs, epoch_energy_usages):
    avg_epoch_energy = np.mean(epoch_energy_usages)
    return total_epochs * avg_epoch_energy


def predict_time(total_epochs, epoch_times):
    avg_epoch_time = np.mean(epoch_times)
    return total_epochs * avg_epoch_time
