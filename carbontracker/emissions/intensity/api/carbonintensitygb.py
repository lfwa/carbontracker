import requests
import datetime

from co2_api import CO2API
from carbon_intensity import CarbonIntensity

API_URL = "https://api.carbonintensity.org.uk"

class CarbonIntensityGB(CO2API):
    def suitable(self, g_location):
        if g_location.country != "GB":
            return False
        return True

    def carbon_intensity(self, g_location, time_len=None):
        carbon_intensity = CarbonIntensity(g_location=g_location)

        try:
            postcode = g_location.postal
            ci = self._carbon_intensity_gb_regional(postcode, time_len=time_len)
            carbon_intensity.carbon_intensity = ci
        except:
            ci = self._carbon_intensity_gb_national(time_len=time_len)
            carbon_intensity.carbon_intensity = ci
            carbon_intensity.message = f"Failed to fetch carbon intensity by regional postcode: {postcode}. Fetched by national instead."

        return carbon_intensity
    
    def _carbon_intensity_gb_regional(self, postcode, time_len=None):
        """"Retrieves forecasted carbon intensity (gCO2eq/kWh) in GB by postcode."""
        url = f"{API_URL}/regional"

        if time_len is not None:
            from_str, to_str = self._time_from_to_str(time_len)
            url += f"/intensity/{from_str}/{to_str}"

        url += f"/postcode/{postcode}"

        response = requests.get(url).json()
        carbon_intensity = response["data"]
        # CO2Signal has a bug, where if we query the time, no list is returned.
        if time_len is None:
            carbon_intensity = carbon_intensity[0]
        carbon_intensity = carbon_intensity["data"][0]["intensity"]["forecast"]
        
        return carbon_intensity

    def _carbon_intensity_gb_national(self, time_len=None):
        """Retrieves forecasted national carbon intensity (gCO2eq/kWh) in GB."""
        url = f"{API_URL}/intensity"

        if time_len is not None:
            from_str, to_str = self._time_from_to_str(time_len)
            url += f"/{from_str}/{to_str}"

        response = requests.get(url).json()
        carbon_intensity = response["data"][0]["intensity"]["forecast"]
        return carbon_intensity

    def _time_from_to_str(self, time_len):
        """Returns the current date in UTC (from) and time_len seconds ahead (to)
        in ISO8601 format YYYY-MM-DDThh:mmZ."""
        date_format = "%Y-%m-%dT%H:%MZ"
        time_from = datetime.datetime.utcnow()
        time_to = time_from + datetime.timedelta(seconds=time_len)
        from_str = time_from.strftime(date_format)
        to_str = time_to.strftime(date_format)
        return from_str, to_str