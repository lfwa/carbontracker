from carbontracker.components.gpu import nvidia
from carbontracker.components.cpu import intel

class GPUError(Exception):
    pass

class CPUError(Exception):
    pass

class ComponentNameError(Exception):
    pass

components = [
    {
        "name": "gpu",
        "error": GPUError("No GPU(s) available."),
        "handlers": [nvidia.NvidiaGPU()]
    },
    {
        "name": "cpu",
        "error": CPUError("No CPU(s) available."),
        "handlers": [intel.IntelCPU()]
    }
]

def component_names():
    return [comp["name"] for comp in components]

def error_by_name(name):
    for comp in components:
        if comp["name"] == name:
            return comp["error"]

def handlers_by_name(name):
    for comp in components:
        if comp["name"] == name:
            return comp["handlers"]

class Component:
    def __init__(self, name):
        self.name = name
        if name not in component_names():
            raise ComponentNameError(f"No component found with name '{self.name}'.")
        self._handler = self._determine_handler()
        self.power_usages = []
    
    @property
    def handler(self):
        if self._handler is None:
            raise error_by_name(self.name)
        return self._handler
    
    def _determine_handler(self):
        handlers = handlers_by_name(self.name)
        for handler in handlers:
            if handler.available():
                return handler
        return None
    
    def info(self):
        return self.handler.info()
    
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
        return [Component(name=comp_name) for comp_name in component_names()]
    else:
        return [Component(name=comp_name) for comp_name in comp_str.split(",")]