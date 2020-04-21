import geocoder
import requests
import datetime

from emissions.intensity.api import co2signal
from emissions.intensity.api import carbonintensitygb
# TODO: If we get access to full API (api.electricitymap.org) then fetch forecasted carbon intensity so we can account for long training times.

# TODO: There is a lot of variation between CO2_SIGNAL and CARBON_INTENSITY IN GB. Up to 50g differences for same locations. This is likely caused by CO2_SIGNAL includes only electricity consumption, while CARBON_INTENSITY includes electricity generated. CARBON_INTENSITY SHOULD BE ABLE TO PROVIDE MUCH MORE FINE DETAILS IN GB. Should we mix these?

# TODO: Auth token should probably be hidden. We might time out if too many requests are being sent with this auth token. Contact them?
AUTH_TOKEN = "2e7f70fa1f2ef4e5"
CO2_SIGNAL_URL = "https://api.co2signal.com/v1/latest"
CARBON_INTENSITY_GB_URL = "https://api.carbonintensity.org.uk"
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
        self.message = f"Live carbon intensity could not be fetched. Used average carbon intensity for EU-28 in 2017 of {EU_28_2017_CARBON_INTENSITY} gCO2/kWh."

def carbon_intensity(time_len=None):
    api_list = [co2signal.CO2Signal(), carbonintensitygb.CarbonIntensityGB()]

    default_ci = CarbonIntensity(default=True)

    try:
        g_location = geocoder.ip("me")
        if not g_location.ok:
            raise Exception()
    except:
        default_ci.message = f"Failed to retrieve location based on IP. {default_ci.message}"
        return default_ci

    for api in api_list:
        if not api.suitable(g_location):
            continue
        try:
            carbon_intensity = api.carbon_intensity(g_location, time_len=time_len)
            break
        except:
            carbon_intensity = default_ci
    
    return carbon_intensity

class UnitError(Exception):
    """Raised when the expected unit does not match the received unit."""
    def __init__(self, expected_unit, received_unit, message):
        self.expected_unit = expected_unit
        self.received_unit = received_unit
        self.message = message