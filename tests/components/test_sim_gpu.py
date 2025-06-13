import unittest
from carbontracker.components.gpu.sim_gpu import SimulatedGPUHandler

class TestSimulatedGPU(unittest.TestCase):
    def test_simulated_gpu_initialization(self):
        handler = SimulatedGPUHandler("NVIDIA A100", 400.0)
        self.assertEqual(handler.gpu_brand, "NVIDIA A100")
        self.assertEqual(handler.watts, 200.0)  # 400W * 0.5 (default utilization)

    def test_simulated_gpu_custom_utilization(self):
        handler = SimulatedGPUHandler("NVIDIA A100", 400.0, utilization=0.6)
        self.assertEqual(handler.gpu_brand, "NVIDIA A100")
        self.assertEqual(handler.watts, 240.0)  # 400W * 0.6

    def test_simulated_gpu_devices(self):
        handler = SimulatedGPUHandler("NVIDIA A100", 400.0)
        devices = handler.devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0], "NVIDIA A100")

    def test_simulated_gpu_available(self):
        handler = SimulatedGPUHandler("NVIDIA A100", 400.0)
        self.assertTrue(handler.available())

    def test_simulated_gpu_power_usage(self):
        handler = SimulatedGPUHandler("NVIDIA A100", 400.0)
        power_usage = handler.power_usage()
        self.assertEqual(len(power_usage), 1)
        self.assertEqual(power_usage[0], 200.0)  # 400W * 0.5

    def test_simulated_gpu_power_usage_custom_util(self):
        handler = SimulatedGPUHandler("NVIDIA A100", 400.0, utilization=0.6)
        power_usage = handler.power_usage()
        self.assertEqual(len(power_usage), 1)
        self.assertEqual(power_usage[0], 240.0)  # 400W * 0.6

    def test_simulated_gpu_invalid_utilization(self):
        with self.assertRaises(ValueError):
            SimulatedGPUHandler("NVIDIA A100", 400.0, utilization=1.5)  # > 1.0
        with self.assertRaises(ValueError):
            SimulatedGPUHandler("NVIDIA A100", 400.0, utilization=-0.1)  # < 0.0

    def test_simulated_gpu_invalid_watts(self):
        with self.assertRaises(ValueError):
            SimulatedGPUHandler("NVIDIA A100", -400.0)  # Negative watts

    def test_simulated_gpu_missing_watts(self):
        with self.assertRaises(ValueError):
            SimulatedGPUHandler("NVIDIA A100", None) 