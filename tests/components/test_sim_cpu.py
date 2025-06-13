import unittest
from carbontracker.components.cpu.sim_cpu import SimulatedCPUHandler

class TestSimulatedCPU(unittest.TestCase):
    def test_simulated_cpu_initialization(self):
        handler = SimulatedCPUHandler("Intel Xeon", 150.0)
        self.assertEqual(handler.cpu_brand, "Intel Xeon")
        self.assertEqual(handler.tdp, 75.0)  # 150W * 0.5 (default utilization)

    def test_simulated_cpu_custom_utilization(self):
        handler = SimulatedCPUHandler("Intel Xeon", 150.0, utilization=0.75)
        self.assertEqual(handler.cpu_brand, "Intel Xeon")
        self.assertEqual(handler.tdp, 112.5)  # 150W * 0.75

    def test_simulated_cpu_devices(self):
        handler = SimulatedCPUHandler("Intel Xeon", 150.0)
        devices = handler.devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0], "Intel Xeon")

    def test_simulated_cpu_available(self):
        handler = SimulatedCPUHandler("Intel Xeon", 150.0)
        self.assertTrue(handler.available())

    def test_simulated_cpu_power_usage(self):
        handler = SimulatedCPUHandler("Intel Xeon", 150.0)
        power_usage = handler.power_usage()
        self.assertEqual(len(power_usage), 1)
        self.assertEqual(power_usage[0], 75.0)  # 150W * 0.5

    def test_simulated_cpu_power_usage_custom_util(self):
        handler = SimulatedCPUHandler("Intel Xeon", 150.0, utilization=0.75)
        power_usage = handler.power_usage()
        self.assertEqual(len(power_usage), 1)
        self.assertEqual(power_usage[0], 112.5)  # 150W * 0.75

    def test_simulated_cpu_invalid_utilization(self):
        with self.assertRaises(ValueError):
            SimulatedCPUHandler("Intel Xeon", 150.0, utilization=1.5)  # > 1.0
        with self.assertRaises(ValueError):
            SimulatedCPUHandler("Intel Xeon", 150.0, utilization=-0.1)  # < 0.0

    def test_simulated_cpu_invalid_tdp(self):
        with self.assertRaises(ValueError):
            SimulatedCPUHandler("Intel Xeon", -150.0)  # Negative TDP

    def test_simulated_cpu_missing_tdp(self):
        with self.assertRaises(ValueError):
            SimulatedCPUHandler("Intel Xeon", None) 