import unittest
from unittest.mock import patch
from carbontracker.components.cpu.generic import GenericCPU

class TestGenericCPU(unittest.TestCase):
    def setUp(self):
        self.generic_cpu = GenericCPU(pids=[], devices_by_pid=False)
        self.cpu_power_data = self.generic_cpu.load_cpu_power_data()
        self.average_tdp = self.generic_cpu.calculate_average_tdp()

    @patch('cpuinfo.get_cpu_info')
    def test_known_intel_cpu_tdp(self, mock_cpuinfo):
        known_cpu = "Intel Core i7-9700K"
        known_tdp = 95 / 2  # 50% utilization

        mock_cpuinfo.return_value = {'brand_raw': known_cpu}

        self.generic_cpu = GenericCPU(pids=[], devices_by_pid=False)
        self.generic_cpu.init()

        self.assertEqual(self.generic_cpu.cpu_brand, known_cpu)
        self.assertTrue(self.generic_cpu.available())
        power_usage = self.generic_cpu.power_usage()
        self.assertAlmostEqual(power_usage[0], known_tdp, places=2)

    @patch('cpuinfo.get_cpu_info')
    def test_known_amd_cpu_tdp(self, mock_cpuinfo):
        known_cpu = "6th Gen AMD PRO A10-8770 APU"
        known_tdp = 65 / 2  # 50% utilization

        mock_cpuinfo.return_value = {'brand_raw': known_cpu}

        self.generic_cpu = GenericCPU(pids=[], devices_by_pid=False)
        self.generic_cpu.init()

        self.assertEqual(self.generic_cpu.cpu_brand, known_cpu)
        self.assertTrue(self.generic_cpu.available())
        power_usage = self.generic_cpu.power_usage()
        self.assertAlmostEqual(power_usage[0], known_tdp, places=2)

    @patch('cpuinfo.get_cpu_info')
    def test_unknown_cpu_average_tdp(self, mock_cpuinfo):
        mock_cpuinfo.return_value = {'brand_raw': 'Unknown CPU Model'}

        self.generic_cpu = GenericCPU(pids=[], devices_by_pid=False)
        self.generic_cpu.init()

        self.assertEqual(self.generic_cpu.cpu_brand, 'Unknown CPU Model')
        self.assertTrue(self.generic_cpu.available())
        power_usage = self.generic_cpu.power_usage()
        self.assertAlmostEqual(power_usage[0], self.average_tdp, places=2)  # average_tdp is already halved

    @patch('cpuinfo.get_cpu_info')
    def test_no_cpu_info(self, mock_cpuinfo):
        mock_cpuinfo.return_value = {}

        self.generic_cpu = GenericCPU(pids=[], devices_by_pid=False)
        self.generic_cpu.init()

        self.assertEqual(self.generic_cpu.cpu_brand, 'Unknown CPU')
        self.assertTrue(self.generic_cpu.available())
        power_usage = self.generic_cpu.power_usage()
        self.assertAlmostEqual(power_usage[0], self.average_tdp, places=2)  # average_tdp is already halved

if __name__ == '__main__':
    unittest.main()
