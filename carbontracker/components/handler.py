from abc import ABCMeta, abstractmethod
from typing import List, Iterable


class Handler:
    __metaclass__ = ABCMeta

    def __init__(self, pids: Iterable[int], devices_by_pid: bool):
        self.pids = pids
        self.devices_by_pid = devices_by_pid

    @abstractmethod
    def devices(self) -> List[str]:
        """Returns a list of devices (str) associated with the component."""
        raise NotImplementedError

    @abstractmethod
    def available(self) -> bool:
        """Returns True if the handler is available."""
        raise NotImplementedError

    @abstractmethod
    def power_usage(self) -> List[float]:
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
