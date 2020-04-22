from pynvml import *
import time
import nvidia

start_time = time.time()

for i in range(10000):
    nvmlInit()
    nvidia.gpu_power_usages_all()
    nvmlShutdown()

end_time = time.time()

start_time_2 = time.time()

nvmlInit()
for i in range(10000):
    nvidia.gpu_power_usages_all()
nvmlShutdown()

end_time_2 = time.time()

print(f"Init every time: {end_time - start_time}")
print(f"Init once: {end_time_2 - start_time_2}")