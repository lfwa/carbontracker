# TODO: This is almost identical with cpu.py. Create a super class and inherit instead?
from carbontracker.components.gpu import nvidia

class GPUError(Exception):
    pass

class GPU:
    def __init__(self):
        self.name = "GPU"
        self._gpu = self._determine_gpu([
            nvidia.NvidiaGPU()
        ])
        self.power_usages = []
    
    @property
    def gpu(self):
        if self._gpu is None:
            raise GPUError("No GPU(s) available.")
        return self._gpu
    
    def _determine_gpu(self, gpus):
        for gpu in gpus:
            if gpu.available():
                return gpu
        return None

    def available(self):
        return self._gpu is not None
    
    def collect_power_usage(self):
        self.power_usages.append(self.gpu.power_usage())

    def init(self):
        self.gpu.init()

    def shutdown(self):
        self.gpu.shutdown()