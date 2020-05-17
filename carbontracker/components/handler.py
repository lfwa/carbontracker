from abc import ABCMeta, abstractmethod


class Handler:
    __metaclass__ = ABCMeta

    def __init__(self, pids, devices_by_pid):
        self.pids = pids
        self.devices_by_pid = devices_by_pid

    @abstractmethod
    def devices(self):
        """Returns a list of devices (str) associated with the component."""
        raise NotImplementedError

    @abstractmethod
    def available(self):
        """Returns True if the handler is available."""
        raise NotImplementedError

    @abstractmethod
    def power_usage(self):
        """Returns the current power usage (W) in a list."""
        raise NotImplementedError

    @abstractmethod
    def init(self):
        """Initializes the handler."""
        raise NotImplementedError

    @abstractmethod
    def shutdown(self):
        """Shuts down the handler."""
        raise NotImplementedError
