import requests

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetcher import IntensityFetcher
from carbontracker.emissions.intensity import intensity

AUTH_TOKEN = None
API_URL = "https://api.co2signal.com/v1/latest"

class CO2Signal(IntensityFetcher):
    def suitable(self, g_location):
        return True

    def carbon_intensity(self, g_location, time_dur=None):
        carbon_intensity = intensity.CarbonIntensity(g_location=g_location)

        try:
            ci = self._carbon_intensity_by_location(
                lon=g_location.lng, 
                lat=g_location.lat
            )
            carbon_intensity.carbon_intensity = ci
            carbon_intensity.message = f"Training location was determined to be {g_location.address}."
        except:
            ci = self._carbon_intensity_by_location(
                country_code=g_location.country
            )
            carbon_intensity.carbon_intensity = ci
            carbon_intensity.message = f"Failed to retrieve carbon intensity by coordinates. Fetched by country code {g_location.country} instead."

        carbon_intensity.message += f" Current carbon intensity is {carbon_intensity.carbon_intensity:.2f} gCO2/kWh."

        return carbon_intensity

    def _carbon_intensity_by_location(self, lon=None, lat=None, country_code=None):
        """Retrieves carbon intensity (gCO2eq/kWh) by location.
        
        Note:
            Only use arguments (lon, lat) or country_code.
        
        Args:
            lon (float): Longitude. Defaults to None.
            lat (float): Lattitude. Defaults to None.
            country_code (str): Alpha-2 country code. Defaults to None.

        Returns:
            Carbon intensity in gCO2eq/kWh.
        
        Raises:
            UnitError: The unit of the carbon intensity does not match the
                expected unit.
        """
        if country_code is not None:
            params = (
                ("countryCode", country_code),
            )
            assert(lon is None and lat is None)
        elif lon is not None and lat is not None:
            params = (
                ("lon", lon),
                ("lat", lat)
            )
            assert(country_code is None)
        
        headers = {
            "auth-token": AUTH_TOKEN
        }

        response = requests.get(API_URL,
                                headers=headers,
                                params=params).json()
        carbon_intensity = response["data"]["carbonIntensity"]
        unit = response["units"]["carbonIntensity"]
        expected_unit = "gCO2eq/kWh"
        if unit != expected_unit:
            raise exceptions.UnitError(expected_unit, unit,
                            "Carbon intensity query returned the wrong unit.")

        return carbon_intensity