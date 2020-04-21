from carbontracker.components.cpu import intel_rapl

class CPUError(Exception):
    pass

class CPU:
    def __init__(self):
        self.name = "CPU"
        self._cpu = self._determine_cpu([
            intel_rapl.IntelCPU()
        ])
        self.power_usages = []
    
    @property
    def cpu(self):
        if self._cpu is None:
            raise CPUError("No CPU(s) available.")
        return self._cpu
    
    def _determine_cpu(self, cpus):
        for cpu in cpus:
            if cpu.available():
                return cpu
        return None

    def available(self):
        return self._cpu is not None

    def collect_power_usage(self):
        self.power_usages.append(self.cpu.power_usage())

    def init(self):
        self.cpu.init()

    def shutdown(self):
        self.cpu.shutdown()