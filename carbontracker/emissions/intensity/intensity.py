import geocoder
import requests
import datetime

from carbontracker.emissions.intensity.fetchers import co2signal
from carbontracker.emissions.intensity.fetchers import carbonintensitygb

# https://www.eea.europa.eu/data-and-maps/data/co2-intensity-of-electricity-generation
EU_28_2017_CARBON_INTENSITY = 294.2060978

class CarbonIntensity:
    def __init__(self, carbon_intensity=None, g_location=None, message=None, default=False):
        self.carbon_intensity = carbon_intensity
        self.g_location = g_location
        self.message = message
        if default:
            self._set_as_default()
    
    def _set_as_default(self):
        self.carbon_intensity = EU_28_2017_CARBON_INTENSITY
        self.g_location = None
        self.message = f"Location specific carbon intensity could not be fetched. Used average carbon intensity for EU-28 in 2017 of {EU_28_2017_CARBON_INTENSITY} gCO2/kWh."

def carbon_intensity(time_dur=None):
    fetchers = [co2signal.CO2Signal(), carbonintensitygb.CarbonIntensityGB()]

    carbon_intensity = CarbonIntensity(default=True)

    try:
        g_location = geocoder.ip("me")
        if not g_location.ok:
            raise Exception()
    except:
        carbon_intensity.message = f"Failed to retrieve location based on IP. {carbon_intensity.message}"
        return carbon_intensity

    for fetcher in fetchers:
        if not fetcher.suitable(g_location):
            continue
        try:
            carbon_intensity = fetcher.carbon_intensity(g_location,
                time_dur=time_dur)
            break
        except:
            pass
    
    return carbon_intensity

class UnitError(Exception):
    """Raised when the expected unit does not match the received unit."""
    def __init__(self, expected_unit, received_unit, message):
        self.expected_unit = expected_unit
        self.received_unit = received_unit
        self.message = message