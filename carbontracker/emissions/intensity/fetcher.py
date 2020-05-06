from abc import ABCMeta, abstractmethod


class IntensityFetcher:
    __metaclass__ = ABCMeta

    @abstractmethod
    def suitable(self, g_location):
        """Returns True if it can be used based on geocoder location."""
        raise NotImplementedError

    @abstractmethod
    def carbon_intensity(self, g_location, time_dur=None):
        """Returns the carbon intensity by location and duration (s)."""
        raise NotImplementedError
