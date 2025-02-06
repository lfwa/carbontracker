from typing import List

class NoComponentsAvailableError(Exception):
    def __init__(
        self,
        msg=(
            "No components were available. CarbonTracker supports Intel "
            "CPUs with the RAPL interface and NVIDIA GPUs."
        ),
        *args,
        **kwargs,
    ):
        super().__init__(msg, *args, **kwargs)


class UnitError(Exception):
    """Raised when the expected unit does not match the received unit."""

    def __init__(self, expected_unit, received_unit, message):
        self.expected_unit = expected_unit
        self.received_unit = received_unit
        self.message = message


class IntelRaplPermissionError(Exception):
    """Raised when an Intel RAPL permission error occurs."""

    def __init__(self, file_names: List[str]):
        self.file_names = file_names


class GPUPowerUsageRetrievalError(Exception):
    """Raised when a GPU power usage retrieval error occurs."""

    pass


class CarbonIntensityFetcherError(Exception):
    pass


class IPLocationError(Exception):
    pass


class GPUError(Exception):
    pass


class CPUError(Exception):
    pass


class ComponentNameError(Exception):
    pass


class FetcherNameError(Exception):
    pass


class MismatchedLogFilesError(Exception):
    pass


class MismatchedEpochsError(Exception):
    pass
