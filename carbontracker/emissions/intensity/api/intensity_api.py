from abc import ABCMeta, abstractmethod

class IntensityAPI:
    __metaclass__ = ABCMeta

    @abstractmethod
    def suitable(self, g_location):
        """Returns True if this API should be used based on geocoder object."""
        raise NotImplementedError

    @abstractmethod
    def carbon_intensity(self, g_location, time_len=None):
        """ """
        raise NotImplementedError