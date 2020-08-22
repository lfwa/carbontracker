import traceback

import geocoder

import numpy as np

from carbontracker import loggerutil
from carbontracker import exceptions
from carbontracker import constants
from carbontracker.emissions.intensity.fetchers import co2signal
from carbontracker.emissions.intensity.fetchers import carbonintensitygb
from carbontracker.emissions.intensity.fetchers import energidataservice


class CarbonIntensity:
    def __init__(self,
                 carbon_intensity=None,
                 g_location=None,
                 address="UNDETECTED",
                 message=None,
                 success=False,
                 is_prediction=False,
                 default=False):
        self.carbon_intensity = carbon_intensity
        self.g_location = g_location
        self.address = address
        self.message = message
        self.success = success
        self.is_prediction = is_prediction
        if default:
            self._set_as_default()

    def _set_as_default(self):
        self.carbon_intensity = constants.EU_28_2017_CARBON_INTENSITY


def carbon_intensity(logger, time_dur=None):
    # Will iterate over and find *first* suitable() api
    fetchers = [
        energidataservice.EnergiDataService(),
        carbonintensitygb.CarbonIntensityGB(),
        co2signal.CO2Signal()
    ]

    carbon_intensity = CarbonIntensity(default=True)

    try:
        g_location = geocoder.ip("me")
        if not g_location.ok:
            raise exceptions.IPLocationError(
                "Failed to retrieve location based on IP.")
        carbon_intensity.address = g_location.address
    except:
        err_str = traceback.format_exc()
        logger.err_info(err_str)
        return carbon_intensity

    for fetcher in fetchers:
        if not fetcher.suitable(g_location):
            continue
        try:
            carbon_intensity = fetcher.carbon_intensity(g_location, time_dur)
            if not np.isnan(carbon_intensity.carbon_intensity):
                carbon_intensity.success = True
            set_carbon_intensity_message(carbon_intensity, time_dur)
            carbon_intensity.address = g_location.address
            break
        except:
            err_str = traceback.format_exc()
            logger.err_info(err_str)

    return carbon_intensity


def set_carbon_intensity_message(ci, time_dur):
    if ci.is_prediction:
        if ci.success:
            ci.message = (
                "Carbon intensity for the next "
                f"{loggerutil.convert_to_timestring(time_dur)} is "
                f"predicted to be {ci.carbon_intensity:.2f} gCO2/kWh")
        else:
            ci.message = ("Failed to predict carbon intensity for the next "
                          f"{loggerutil.convert_to_timestring(time_dur)}, "
                          f"fallback on average measured intensity")
    else:
        if ci.success:
            ci.message = (
                f"Current carbon intensity is {ci.carbon_intensity:.2f} gCO2/kWh"
            )
        else:
            ci.message = (
                f"Live carbon intensity could not be fetched at detected location: {ci.address}. "
                "Defaulted to average carbon intensity for EU-28 in 2017 of "
                f"{constants.EU_28_2017_CARBON_INTENSITY:.2f} gCO2/kWh.")
            return
    ci.message += f" at detected location: {ci.address}."
