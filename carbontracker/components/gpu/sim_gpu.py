from carbontracker.components.handler import Handler
from typing import List

class SimulatedGPUHandler(Handler):
    def __init__(self, name: str, watts: float, utilization: float = 0.5):
        super().__init__(pids=[], devices_by_pid=False)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("GPU name must be a non-empty string.")
        if watts is None or not isinstance(watts, (int, float)) or watts < 0:
            raise ValueError("GPU watts must be a non-negative number.")
        if not isinstance(utilization, (int, float)) or not (0.0 <= utilization <= 1.0):
            raise ValueError("GPU utilization must be between 0.0 and 1.0.")
        self.gpu_brand = name
        self.utilization = utilization
        self.watts = watts * utilization

    def devices(self) -> List[str]:
        return [self.gpu_brand]

    def available(self) -> bool:
        return True

    def power_usage(self) -> List[float]:
        return [self.watts]

    def init(self):
        print(f"Using simulated GPU: {self.gpu_brand} with power consumption: {self.watts:.2f}W (at {self.utilization*100:.0f}% utilization)")

    def shutdown(self):
        pass

    def devices(self) -> List[str]:
        return [self.gpu_brand]

    def available(self) -> bool:
        return True

    def power_usage(self) -> List[float]:
        return [self.watts]

    def init(self):
        print(f"Using simulated GPU: {self.gpu_brand} with power consumption: {self.watts:.2f}W (at {self.utilization*100:.0f}% utilization)")

    def shutdown(self):
        pass 