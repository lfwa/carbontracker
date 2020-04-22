from carbontracker.components.gpu import nvidia
from carbontracker.components.cpu import intel

COMPONENT_NAMES = ["gpu", "cpu"]

class GPUError(Exception):
    pass

class CPUError(Exception):
    pass

class ComponentNameError(Exception):
    pass

class Component:
    def __init__(self, name):
        self.name = name
        if self.name not in COMPONENT_NAMES:
            raise ComponentNameError(f"No component found with name '{self.name}'.")
        self._handler = self._determine_handler()
        self.power_usages = []
    
    @property
    def handler(self):
        # TODO: Better way to ensure that keys are in COMPONENT_NAMES?
        errors = {
            "gpu": GPUError("No GPU(s) available."),
            "cpu": CPUError("No CPU(s) available.")
        }
        if self._handler is None:
            raise errors[self.name]
        return self._handler
    
    def _determine_handler(self):
        # TODO: Better way to ensure that keys are in COMPONENT_NAMES?
        handlers = {
            "gpu": [nvidia.NvidiaGPU()],
            "cpu": [intel.IntelCPU()]
        }
        for handler in handlers[self.name]:
            if handler.available():
                return handler
        return None
    
    def available(self):
        return self._handler is not None
    
    def collect_power_usage(self):
        self.power_usages.append(self.handler.power_usage())
    
    def init(self):
        self.handler.init()
    
    def shutdown(self):
        self.handler.shutdown()

def create_components(comp_str):
    comp_str = comp_str.strip().replace(" ", "")
    if comp_str == "all":
        return [Component(name=comp_name) for comp_name in COMPONENT_NAMES]
    else:
        return [Component(name=comp_name) for comp_name in comp_str.split(",")]