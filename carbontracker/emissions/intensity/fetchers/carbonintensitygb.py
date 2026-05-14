import datetime
from typing import TYPE_CHECKING

import numpy as np
import requests

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetcher import IntensityFetch, IntensityFetcher

if TYPE_CHECKING:
    from carbontracker.loggerutil import Logger

API_URL = "https://api.carbonintensity.org.uk"


class CarbonIntensityGB(IntensityFetcher):
    id = "carbonintensitygb"

    def __init__(self, logger: "Logger"):
        super().__init__(logger=logger)

    def suitable(self, g_location):
        return getattr(g_location, "country", None) == "GB"

    def fetch_carbon_intensity(self, g_location, time_dur=None) -> IntensityFetch:
        postcode = getattr(g_location, "postal", None)
        ci = None

        if postcode:
            try:
                ci = float(
                    self._carbon_intensity_gb_regional(postcode, time_dur=time_dur)
                )
            except Exception:  # noqa: BLE001
                ci = None

        if ci is None:
            ci = float(self._carbon_intensity_gb_national(time_dur=time_dur))

        return IntensityFetch(
            carbon_intensity=ci,
            address=g_location.address,
            country=g_location.country,
            is_fetched=True,
            is_localized=True,
            is_prediction= True if time_dur is not None else False,
            time_duration=time_dur
        )

    def _carbon_intensity_gb_regional(self, postcode, time_dur=None) -> float:
        """Retrieves forecasted carbon intensity (gCO2eq/kWh) in GB by postcode."""
        url = f"{API_URL}/regional"

        if time_dur is not None:
            from_str, to_str = self._time_from_to_str(time_dur)
            url += f"/intensity/{from_str}/{to_str}"

        url += f"/postcode/{postcode}"
        response = requests.get(url)

        if not response.ok:
            self._raise_for_bad_response(response)

        data = response.json()["data"]

        # API returns a list when querying current intensity, otherwise nested dicts.
        if isinstance(data, list):
            if not data:
                raise exceptions.CarbonIntensityFetcherError(
                    f"No carbon intensity data returned for postcode {postcode}."
                )
            region_data = data[0]
        else:
            region_data = data

        carbon_intensities = [
            entry["intensity"]["forecast"] for entry in region_data["data"]
        ]
        return float(np.mean(carbon_intensities))

    def _carbon_intensity_gb_national(self, time_dur=None) -> float:
        """Retrieves forecasted national carbon intensity (gCO2eq/kWh) in GB."""
        url = f"{API_URL}/intensity"

        if time_dur is not None:
            from_str, to_str = self._time_from_to_str(time_dur)
            url += f"/{from_str}/{to_str}"

        response = requests.get(url)

        if not response.ok:
            self._raise_for_bad_response(response)

        carbon_intensity = response.json()["data"][0]["intensity"]["forecast"]
        return float(carbon_intensity)

    def _time_from_to_str(self, time_dur):
        """Returns the current date in UTC (from) and time_dur seconds ahead."""
        date_format = "%Y-%m-%dT%H:%MZ"
        time_from = datetime.datetime.now(datetime.timezone.utc)
        time_to = time_from + datetime.timedelta(seconds=time_dur)
        from_str = time_from.strftime(date_format)
        to_str = time_to.strftime(date_format)
        return from_str, to_str

    def _raise_for_bad_response(self, response):
        try:
            error_details = response.json()
        except Exception:  # noqa: BLE001
            error_details = "Bad response received from API. Could not parse JSON"
        raise exceptions.CarbonIntensityFetcherError(error_details)
