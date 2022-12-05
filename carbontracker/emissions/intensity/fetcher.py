from abc import ABCMeta, abstractmethod

""" 
    Information about the geocoder object g_location available
    here: https://geocoder.readthedocs.io
"""


class IntensityFetcher:
    __metaclass__ = ABCMeta

    @abstractmethod
    def suitable(self, g_location):
        """Returns True if it can be used based on geocoder location."""
        raise NotImplementedError

    @abstractmethod
    def carbon_intensity(self, g_location, time_dur=None):
        """
        Returns the carbon intensity by location and duration (s).
        If the API supports predicted intensities time_dur can be used.
        """
        raise NotImplementedError
