#import pyJoules
from pyJoules.energy_meter import measureit
from pyJoules.energy_handler import CsvHandler
#from pyJoules.energy_device.rapl_device import RaplPackageDomain
#from pyJoules.energy_device.nvidia_device import NvidiaGPUDomain

csv_handler = CsvHandler('result.csv')

@measureit(handler=csv_handler)
def foo():
    counter = 0
    for i in range(10000):
        counter += 10
    return counter

foo()