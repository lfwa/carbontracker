import datetime

import requests
import numpy as np

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetcher import IntensityFetcher
from carbontracker.emissions.intensity import intensity


class EnergiDataService(IntensityFetcher):
    def suitable(self, g_location):
        return g_location.country == "DK"

    def carbon_intensity(self, g_location, time_dur=None):
        carbon_intensity = intensity.CarbonIntensity(g_location=g_location)
        if time_dur is None:
            ci = self._emission_current()
        else:
            ci = self._emission_prognosis(time_dur=time_dur)
            carbon_intensity.is_prediction = True

        carbon_intensity.carbon_intensity = ci

        return carbon_intensity

    def _emission_current(self):
        def url_creator(area):
            return (
                'https://api.energidataservice.dk/dataset/CO2emis?filter={"PriceArea":"'
                + area
                + '"}'
            )

        areas = ["DK1", "DK2"]
        carbon_intensities = []

        for area in areas:
            url = url_creator(area)
            response = requests.get(url)
            if not response.ok:
                raise exceptions.CarbonIntensityFetcherError(response.json())
            carbon_intensities.append(response.json()["records"][0]["CO2Emission"])
        return np.mean(carbon_intensities)

    def _emission_prognosis(self, time_dur):
        from_str, to_str = self._interval(time_dur=time_dur)
        url = (
            "https://api.energidataservice.dk/dataset/CO2Emis?start="
            + from_str
            + "&end="
            + to_str
            + "&limit=4"
        )
        response = requests.get(url)
        if not response.ok:
            raise exceptions.CarbonIntensityFetcherError(response.json())
        data = response.json()["records"]
        carbon_intensities = [record["CO2Emission"] for record in data]
        return np.mean(carbon_intensities)

    def _interval(self, time_dur):
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
