import sys
import traceback
from typing import List, Optional, Tuple, Type

import geocoder
import pandas as pd

from carbontracker import constants, exceptions, loggerutil
from carbontracker.emissions.intensity.fetcher import IntensityFetch, IntensityFetcher
from carbontracker.emissions.intensity.fetchers import electricitymaps
from carbontracker.emissions.intensity.location import Location


class IntensityService():
    def __init__(self,
                 logger : loggerutil.Logger,
                 intensity_fetcher : Optional[IntensityFetcher] = None,
                 ) -> None:
        self.logger = logger
        self.intensity_fetcher = intensity_fetcher
        self.geo_location = self._fetch_geo_location()
        self.address = self._get_address()
        self.country = self._get_country()
        self.default_carbon_intensity = self._get_default_carbon_intensity()
        self._log_state()


    def fetch_carbon_intensity(self, time_duration = None) -> IntensityFetch:
        if self.intensity_fetcher is None or self.geo_location is None:
            return self.default_carbon_intensity
        else:
            if not self.intensity_fetcher.suitable(self.geo_location):
                self._log_fetch_failed()
                return self.default_carbon_intensity
            else:
                try:
                    result : IntensityFetch = self.intensity_fetcher.fetch_carbon_intensity(g_location=self.geo_location,time_dur=time_duration)

                    return result
                except Exception:

                    self._log_fetch_failed()
                    return self.default_carbon_intensity

    def _get_default_carbon_intensity(self) -> IntensityFetch:
        """Retrieve static default carbon intensity value based on location."""
        if self.geo_location is None:
            intensity = constants.WORLD_AVG_CARBON_INTENSITY

            return IntensityFetch(
            carbon_intensity=float(intensity),
            address=self.address,
            country=self.country,
            is_localized=False,
            is_fetched=False,
            is_prediction=False,
        )

        else:
            try:
                # importlib.resources.files was introduced in Python 3.9
                if sys.version_info < (3, 9):
                    import pkg_resources

                    path = pkg_resources.resource_filename(
                        "carbontracker", "data/carbon-intensities.csv"
                    ) # pyright: ignore[reportOptionalCall]
                else:
                    import importlib.resources

                    path = importlib.resources.files("carbontracker").joinpath(
                        "data", "carbon-intensities.csv" # type: ignore
                    )
                carbon_intensities_df = pd.read_csv(str(path))
                intensity_row = carbon_intensities_df[
                    carbon_intensities_df["alpha-2"] == self.country
                ].iloc[0]
                intensity = intensity_row["Carbon intensity of electricity (gCO2eq/kWh)"]
                return IntensityFetch(
                    carbon_intensity=float(intensity),
                    address=self.address,
                    country=self.country,
                    is_fetched=False,
                    is_localized=True,
                    is_prediction=False,
                )
            except Exception as err:
                self.logger.err_debug(err)
                intensity = constants.WORLD_AVG_CARBON_INTENSITY
                return IntensityFetch(
                carbon_intensity=float(intensity),
                address=self.address,
                country=self.country,
                is_localized=False,
                is_fetched=False,
                is_prediction=False,
            )

    def _fetch_geo_location(self) -> Optional[Location]:
            try:
                g_location: Location = geocoder.ip("me")
                if g_location.ok is False:
                    self.logger.err_debug(f"Geolocation fetch failed: {g_location}")
                    return None
            except Exception as err:
                self.logger.err_debug(f"Geolocation fetch failed. Error; {err}")
                return None
            return g_location

    def _get_address(self) -> str:
        if self.geo_location is None or not self.geo_location.ok:
            return "Unknown"
        else:
            return self.geo_location.address

    def _get_country(self) -> str:
        if self.geo_location is None or not self.geo_location.ok:
            return "Unknown"
        else:
            return self.geo_location.country

    def _log_state(self):
        if self.intensity_fetcher is None:
            if self.default_carbon_intensity.is_localized is False:
                self.logger.err_warn(
                    f"No carbon intensity provider specified and no location detected. "
                    f"Defaulting to global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                    f"{constants.WORLD_AVG_CARBON_INTENSITY:.2f} gCO2eq/kWh."
                )
                return
            else:
                self.logger.err_warn(
                    f"No carbon intensity provider specified. "
                    f"Using average carbon intensity for {self.default_carbon_intensity.country}: "
                    f"{self.default_carbon_intensity.carbon_intensity:.2f} gCO2eq/kWh."
                )
                return

        if self.geo_location is None:
            self.logger.err_warn(
                f"Location could not be determined. "
                f"Using global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                f"{constants.WORLD_AVG_CARBON_INTENSITY:.2f} gCO2eq/kWh."
            )
            return

        self.logger.err_info(
            f"Using realtime localized carbon intensity based on location: {self.address}."
        )
            

    def _log_fetch_failed(self):
        self.logger.err_warn(
            f"Fetcher is unable to retrieve carbon intensity data for your detected location {self.address}. "
            f"Carbon emissions calculations will fall back to the average carbon intensity for {self.default_carbon_intensity.country}: {self.default_carbon_intensity.carbon_intensity:.2f} gCO2eq/kWh.")
