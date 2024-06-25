import unittest
from unittest.mock import patch
from carbontracker.components.apple_silicon.powermetrics import (
    AppleSiliconCPU,
    AppleSiliconGPU,
    PowerMetricsUnified,
)


class TestAppleSiliconCPU(unittest.TestCase):
    def setUp(self):
        self.cpu_handler = AppleSiliconCPU(pids=[], devices_by_pid=False)
        self.cpu_handler.init()

    def test_shutdown(self):
        self.cpu_handler.shutdown()

    @patch("platform.system", return_value="Darwin")
    def test_available_darwin(self, mock_platform):
        self.assertTrue(self.cpu_handler.available())

    @patch("platform.system", return_value="AlienOS")
    def test_available_not_darwin(self, mock_platform):
        self.assertFalse(self.cpu_handler.available())

    def test_devices(self):
        self.assertEqual(self.cpu_handler.devices(), ["CPU"])

    @patch(
        "carbontracker.components.apple_silicon.powermetrics.PowerMetricsUnified.get_output",
        return_value="CPU Power: 1000 mW",
    )
    def test_power_usage_with_match(self, mock_get_output):
        self.assertEqual(self.cpu_handler.power_usage(), [1.0])

    @patch(
        "carbontracker.components.apple_silicon.powermetrics.PowerMetricsUnified.get_output",
        return_value="No CPU Power data",
    )
    def test_power_usage_no_match(self, mock_get_output):
        self.assertEqual(self.cpu_handler.power_usage(), [0.0])


class TestAppleSiliconGPU(unittest.TestCase):
    def setUp(self):
        self.gpu_handler = AppleSiliconGPU(pids=[], devices_by_pid=False)
        self.gpu_handler.init()

    @patch("platform.system", return_value="Darwin")
    def test_available_darwin(self, mock_platform):
        self.assertTrue(self.gpu_handler.available())

    @patch("platform.system", return_value="Windows")
    def test_available_not_darwin(self, mock_platform):
        self.assertFalse(self.gpu_handler.available())

    def test_devices(self):
        self.assertEqual(self.gpu_handler.devices(), ["GPU", "ANE"])

    @patch(
        "carbontracker.components.apple_silicon.powermetrics.PowerMetricsUnified.get_output",
        return_value="GPU Power: 500 mW\nANE Power: 300 mW",
    )
    def test_power_usage_with_match(self, mock_get_output):
        self.assertEqual(len(self.gpu_handler.power_usage()), 1)
        self.assertAlmostEqual(self.gpu_handler.power_usage()[0], 0.8, places=2)

    @patch(
        "carbontracker.components.apple_silicon.powermetrics.PowerMetricsUnified.get_output",
        return_value="No GPU Power data",
    )
    def test_power_usage_no_match(self, mock_get_output):
        self.assertEqual(self.gpu_handler.power_usage(), [0.0])


class TestPowerMetricsUnified(unittest.TestCase):
    @patch("subprocess.check_output", return_value="Sample Output")
    @patch("time.time", side_effect=[100, 101, 102, 200, 202])
    def test_get_output_with_actual_call(self, mock_time, mock_check_output):
        # First call - should call subprocess
        output1 = PowerMetricsUnified.get_output()

        # Second call - should use cached output
        output2 = PowerMetricsUnified.get_output()
        self.assertIsNotNone(PowerMetricsUnified._last_updated)
        if PowerMetricsUnified._last_updated is None:
            self.fail()
        # Advance time to invalidate cache
        PowerMetricsUnified._last_updated -= 2

        # Third call - should call subprocess again
        output3 = PowerMetricsUnified.get_output()

        self.assertEqual(mock_check_output.call_count, 2)
        self.assertEqual(output1, "Sample Output")
        self.assertEqual(output2, "Sample Output")
        self.assertEqual(output3, "Sample Output")


class TestAppleSiliconGPUPowerUsage(unittest.TestCase):
    def setUp(self):
        self.gpu_handler = AppleSiliconGPU(pids=[], devices_by_pid=False)
        self.gpu_handler.init()

    @patch(
        "carbontracker.components.apple_silicon.powermetrics.PowerMetricsUnified.get_output",
        return_value="GPU Power: 500 mW\nANE Power: 300 mW",
    )
    def test_power_usage_with_match(self, mock_get_output):
        self.assertEqual(len(self.gpu_handler.power_usage()), 1)
        self.assertAlmostEqual(self.gpu_handler.power_usage()[0], 0.8, places=2)

    @patch(
        "carbontracker.components.apple_silicon.powermetrics.PowerMetricsUnified.get_output",
        return_value="No GPU Power data",
    )
    def test_power_usage_no_match(self, mock_get_output):
        self.assertEqual(self.gpu_handler.power_usage(), [0.0])


if __name__ == "__main__":
    unittest.main()
