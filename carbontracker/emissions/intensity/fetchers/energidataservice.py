import datetime
from typing import TYPE_CHECKING, List

import numpy as np
import requests

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetcher import IntensityFetch, IntensityFetcher

if TYPE_CHECKING:
    from carbontracker.loggerutil import Logger

CURRENT_DATASET = "CO2emis"
PROGNOSIS_DATASET = "CO2Emis"
BASE_URL = "https://api.energidataservice.dk/dataset"


class EnergiDataService(IntensityFetcher):
    id = "energidataservice"

    def __init__(self, logger: "Logger"):
        super().__init__(logger=logger)

    def suitable(self, g_location):
        return getattr(g_location, "country", None) == "DK"

    def fetch_carbon_intensity(self, g_location, time_dur=None) -> IntensityFetch:
        if time_dur is None:
            ci = float(self._emission_current())
        else: 
            ci = float(self._emission_prognosis(time_dur=time_dur))

        return IntensityFetch(
            carbon_intensity=ci,
            address=g_location.address,
            country=g_location.country,
            is_fetched=True,
            is_localized=True,
            is_prediction= True if time_dur is not None else False,
            time_duration=time_dur,
        )

    def _emission_current(self) -> float:
        areas = ["DK1", "DK2"]
        carbon_intensities: List[float] = []

        for area in areas:
            params = f'{{"PriceArea":"{area}"}}'
            url = f"{BASE_URL}/{CURRENT_DATASET}?filter={params}"
            response = requests.get(url)

            if not response.ok:
                self._raise_for_bad_response(response)

            records = response.json()["records"]
            if not records:
                raise exceptions.CarbonIntensityFetcherError(
                    f"No CO2 emission records returned for area {area}."
                )

            carbon_intensities.append(records[0]["CO2Emission"])

        return float(np.mean(carbon_intensities))

    def _emission_prognosis(self, time_dur: int) -> float:
        from_str, to_str = self._interval(time_dur=time_dur)
        url = (
            f"{BASE_URL}/{PROGNOSIS_DATASET}?start={from_str}&end={to_str}&limit=4"
        )
        response = requests.get(url)

        if not response.ok:
            self._raise_for_bad_response(response)

        data = response.json()["records"]
        if not data:
            raise exceptions.CarbonIntensityFetcherError(
                "No CO2 emission prognosis data returned."
            )

        carbon_intensities = [record["CO2Emission"] for record in data]
        return float(np.mean(carbon_intensities))

    def _interval(self, time_dur: int):
        from_time = datetime.datetime.now(datetime.timezone.utc)
        to_time = from_time + datetime.timedelta(seconds=time_dur)
        from_str = self._nearest_5_min(from_time)
        to_str = self._nearest_5_min(to_time)
        return from_str, to_str

    def _nearest_5_min(self, time):
        date_format = "%Y-%m-%dT%H:%M"
        nearest_5_min = time - datetime.timedelta(
            minutes=time.minute % 5, seconds=time.second, microseconds=time.microsecond
        )
        return nearest_5_min.strftime(date_format)

    def _raise_for_bad_response(self, response):
        try:
            error_details = response.json()
        except Exception:  # noqa: BLE001
            error_details = "Bad response received from API. Could not parse JSON"
        raise exceptions.CarbonIntensityFetcherError(error_details)
