import requests

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetcher import IntensityFetcher
from carbontracker.emissions.intensity import intensity

API_URL = "https://api-access.electricitymaps.com/free-tier/carbon-intensity/latest"


class ElectricityMap(IntensityFetcher):
    _api_key = None

    @classmethod
    def set_api_key(cls, key):
        cls._api_key = key

    def suitable(self, g_location):
        return self._api_key is not None

    def carbon_intensity(self, g_location, time_dur=None):
        carbon_intensity = intensity.CarbonIntensity(g_location=g_location)

        try:
            ci = self._carbon_intensity_by_location(lon=g_location.lng, lat=g_location.lat)
        except:
            ci = self._carbon_intensity_by_location(zone=g_location.country)

        carbon_intensity.carbon_intensity = ci

        return carbon_intensity

    def _carbon_intensity_by_location(self, lon=None, lat=None, zone=None):
        """Retrieves carbon intensity (gCO2eq/kWh) by location.

        Note:
            Only use arguments (lon, lat) or country_code.

        Args:
            lon (float): Longitude. Defaults to None.
            lat (float): Lattitude. Defaults to None.
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
            raise exceptions.CarbonIntensityFetcherError(response.json())
        carbon_intensity = response.json()["carbonIntensity"]

        return carbon_intensity
