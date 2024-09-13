import os.path
import traceback

import geocoder
import numpy as np
import pandas as pd
import sys
from typing import Union

from carbontracker import loggerutil
from carbontracker import exceptions
from carbontracker import constants
from carbontracker.emissions.intensity.fetchers import carbonintensitygb
from carbontracker.emissions.intensity.fetchers import energidataservice
from carbontracker.emissions.intensity.fetchers import electricitymaps
from carbontracker.emissions.intensity.location import Location


def get_default_intensity():
    """Retrieve static default carbon intensity value based on location."""
    try:
        g_location: Location = geocoder.ip("me")
        if not g_location.ok:
            raise exceptions.IPLocationError("Failed to retrieve location based on IP.")
        address = g_location.address
        country = g_location.country
    except Exception as err:
        address = "Unknown"
        country = "Unknown"

    try:
        # importlib.resources.files was introduced in Python 3.9
        if sys.version_info < (3, 9):
            import pkg_resources

            path = pkg_resources.resource_filename(
                "carbontracker", "data/carbon-intensities.csv"
            )
        else:
            import importlib.resources

            path = importlib.resources.files("carbontracker").joinpath(
                "data", "carbon-intensities.csv"
            )
        carbon_intensities_df = pd.read_csv(str(path))
        intensity_row = carbon_intensities_df[
            carbon_intensities_df["alpha-2"] == country
        ].iloc[0]
        intensity: float = intensity_row["Carbon intensity of electricity (gCO2/kWh)"]
        year: int = intensity_row["Year"]
        description = f"Defaulted to average carbon intensity for {country} in {year} of {intensity:.2f} gCO2/kWh."
    except Exception as err:
        intensity = constants.WORLD_2019_CARBON_INTENSITY
        description = f"Defaulted to average carbon intensity for world in 2019 of {intensity:.2f} gCO2/kWh."

    description = (
        f"Live carbon intensity could not be fetched at detected location: {address}. "
        + description
    )
    default_intensity = {
        "carbon_intensity": intensity,
        "description": description,
    }
    return default_intensity


default_intensity = get_default_intensity()


class CarbonIntensity:
    def __init__(
        self,
        carbon_intensity: Union[float, None] = None,
        g_location=None,
        address="UNDETECTED",
        message: Union[str, None] = None,
        success=False,
        is_prediction=False,
        default=False,
    ):
        self.carbon_intensity = carbon_intensity
        self.g_location = g_location
        self.address = address
        self.message = message
        self.success = success
        self.is_prediction = is_prediction
        if default:
            self.set_as_default()

    def set_as_default(self):
        self.set_default_intensity()
        self.set_default_message()

    def set_default_intensity(self):
        self.carbon_intensity = default_intensity["carbon_intensity"]

    def set_default_message(self):
        self.message = default_intensity["description"]


def carbon_intensity(logger, time_dur=None, fetchers=None):
    if fetchers is None:
        fetchers = [
            electricitymaps.ElectricityMap(logger=logger),
            #energidataservice.EnergiDataService(), # UPDATE 2024: EnergiDataService/CarbonIntensityGB has been deprecated
            #carbonintensitygb.CarbonIntensityGB(),
        ]

    carbon_intensity = CarbonIntensity(default=True)

    try:
        g_location = geocoder.ip("me")
        if not g_location.ok:
            raise exceptions.IPLocationError("Failed to retrieve location based on IP.")
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
        except:
            err_str = traceback.format_exc()
            logger.err_info(err_str)

    if not carbon_intensity.success:
        logger.err_warn(
            "Failed to retrieve carbon intensity: Defaulting to average carbon intensity {} gCO2/kWh.".format(
                default_intensity["carbon_intensity"]
            )
        )
    return carbon_intensity


def set_carbon_intensity_message(ci: CarbonIntensity, time_dur):
    if ci.is_prediction:
        if ci.success:
            ci.message = (
                "Carbon intensity for the next "
                f"{loggerutil.convert_to_timestring(time_dur)} is "
                f"predicted to be {ci.carbon_intensity:.2f} gCO2/kWh"
            )
        else:
            ci.message = (
                "Failed to predict carbon intensity for the next "
                f"{loggerutil.convert_to_timestring(time_dur)}, "
                f"fallback on average measured intensity"
            )
    else:
        if ci.success:
            ci.message = (
                f"Current carbon intensity is {ci.carbon_intensity:.2f} gCO2/kWh"
            )
        else:
            ci.set_default_message()
    if ci.message is not None:
        ci.message += f" at detected location: {ci.address}."
