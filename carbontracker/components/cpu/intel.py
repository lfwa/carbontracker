#import pyrapl # Check if it works on Colab
# We can also use pyJoules for measuring everything, if we can get it working.
from carbontracker.components.handler import Handler

class IntelCPU(Handler):
    def info(self):
        pass

    def available(self):
        return False
    
    def power_usage(self):
        pass
    
    def init(self):
        pass
    
    def shutdown(self):
        pass