import requests
import datetime

import numpy as np

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetcher import IntensityFetcher
from carbontracker.emissions.intensity import intensity

API_URL = "https://api.carbonintensity.org.uk"


class CarbonIntensityGB(IntensityFetcher):
    def suitable(self, g_location):
        return g_location.country == "GB"

    def carbon_intensity(self, g_location, time_dur=None):
        carbon_intensity = intensity.CarbonIntensity(g_location=g_location)

        if time_dur is not None:
            carbon_intensity.is_prediction = True

        try:
            postcode = g_location.postal
            ci = self._carbon_intensity_gb_regional(postcode, time_dur=time_dur)
        except:
            ci = self._carbon_intensity_gb_national(time_dur=time_dur)

        carbon_intensity.carbon_intensity = ci

        return carbon_intensity

    def _carbon_intensity_gb_regional(self, postcode, time_dur=None):
        """ "Retrieves forecasted carbon intensity (gCO2eq/kWh) in GB by
        postcode."""
        url = f"{API_URL}/regional"

        if time_dur is not None:
            from_str, to_str = self._time_from_to_str(time_dur)
            url += f"/intensity/{from_str}/{to_str}"

        url += f"/postcode/{postcode}"
        response = requests.get(url)
        if not response.ok:
            raise exceptions.CarbonIntensityFetcherError(response.json())
        data = response.json()["data"]

        # API has a bug s.t. if we query current then we get a list.
        if time_dur is None:
            data = data[0]

        carbon_intensities = []
        for ci in data["data"]:
            carbon_intensities.append(ci["intensity"]["forecast"])
        carbon_intensity = np.mean(carbon_intensities)

        return carbon_intensity

    def _carbon_intensity_gb_national(self, time_dur=None):
        """Retrieves forecasted national carbon intensity (gCO2eq/kWh) in GB."""
        url = f"{API_URL}/intensity"

        if time_dur is not None:
            from_str, to_str = self._time_from_to_str(time_dur)
            url += f"/{from_str}/{to_str}"

        response = requests.get(url)
        if not response.ok:
            raise exceptions.CarbonIntensityFetcherError(response.json())
        carbon_intensity = response.json()["data"][0]["intensity"]["forecast"]
        return carbon_intensity

    def _time_from_to_str(self, time_dur):
        """Returns the current date in UTC (from) and time_dur seconds ahead
        (to) in ISO8601 format YYYY-MM-DDThh:mmZ."""
        date_format = "%Y-%m-%dT%H:%MZ"
        time_from = datetime.datetime.now(datetime.timezone.utc)
        time_to = time_from + datetime.timedelta(seconds=time_dur)
        from_str = time_from.strftime(date_format)
        to_str = time_to.strftime(date_format)
        return from_str, to_str
