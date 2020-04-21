#import pyrapl # Check if it works on Colab
# We can also use pyJoules for measuring everything, if we can get it working.

class IntelCPU:
    def available(self):
        return False
    
    def power_usage(self):
        pass
    
    def init(self):
        pass
    
    def shutdown(self):
        pass