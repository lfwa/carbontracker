from typing import Optional
import requests

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetcher import IntensityFetch, IntensityFetcher

API_URL = "https://api.electricitymaps.com/v3/carbon-intensity/latest"


class ElectricityMap(IntensityFetcher):
    id = "electricitymaps"

    def __init__(self, logger, api_key: str):
        self.logger = logger
        self._api_key = api_key

    def suitable(self, g_location):
        return True
    ## Prediction is not supported for electricityMaps, thus time_dur is not used.
    def fetch_carbon_intensity(self, g_location, time_dur=None) -> IntensityFetch:
        try:
            ci = self._carbon_intensity_by_location(lon=g_location.lng, lat=g_location.lat)
        except:
            ci = self._carbon_intensity_by_location(zone=g_location.country)
        
        return IntensityFetch(
                    carbon_intensity=float(ci),
                    address=g_location.address,
                    country=g_location.country,
                    is_fetched=True,
                    is_localized=True,
                    is_prediction=False,)
 

    def _carbon_intensity_by_location(self, lon=None, lat=None, zone=None,) -> float:
        """Retrieves carbon intensity (gCO2eq/kWh) by location.

        Note:
            Only use arguments (lon, lat) or country_code.

        Args:
            lon (float): Longitude. Defaults to None.
            lat (float): Latitude. Defaults to None.
            zone (str): Alpha-2 country code. Defaults to None.

        Returns:
            Carbon intensity in gCO2eq/kWh.
        """
        if zone is not None:
            params = (("zone", zone),)
            assert lon is None and lat is None
        elif lon is not None and lat is not None:
            params = (("lon", lon), ("lat", lat))
            assert zone is None

        headers = {"auth-token": self._api_key}

        response = requests.get(API_URL, headers=headers, params=params)
        if not response.ok:
            try:
                errorDetails = response.json()
            except:
                errorDetails = "Bad response received from API. Could not parse JSON"
            raise exceptions.CarbonIntensityFetcherError(errorDetails)

        carbon_intensity = response.json()["carbonIntensity"]
        return carbon_intensity
