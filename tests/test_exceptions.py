import unittest
from carbontracker import exceptions

class TestExceptions(unittest.TestCase):
    def test_no_components_available_error(self):
        with self.assertRaises(exceptions.NoComponentsAvailableError):
            raise exceptions.NoComponentsAvailableError

    def test_unit_error(self):
        with self.assertRaises(exceptions.UnitError):
            raise exceptions.UnitError("Expected", "Received", "Message")

    def test_intel_rapl_permission_error(self):
        with self.assertRaises(exceptions.IntelRaplPermissionError):
            raise exceptions.IntelRaplPermissionError(file_names=["file1", "file2"])

    def test_gpu_power_usage_retrieval_error(self):
        with self.assertRaises(exceptions.GPUPowerUsageRetrievalError):
            raise exceptions.GPUPowerUsageRetrievalError

    def test_carbon_intensity_fetcher_error(self):
        with self.assertRaises(exceptions.CarbonIntensityFetcherError):
            raise exceptions.CarbonIntensityFetcherError

    def test_ip_location_error(self):
        with self.assertRaises(exceptions.IPLocationError):
            raise exceptions.IPLocationError

    def test_gpu_error(self):
        with self.assertRaises(exceptions.GPUError):
            raise exceptions.GPUError

    def test_cpu_error(self):
        with self.assertRaises(exceptions.CPUError):
            raise exceptions.CPUError

    def test_component_name_error(self):
        with self.assertRaises(exceptions.ComponentNameError):
            raise exceptions.ComponentNameError

    def test_fetcher_name_error(self):
        with self.assertRaises(exceptions.FetcherNameError):
            raise exceptions.FetcherNameError

    def test_mismatched_log_files_error(self):
        with self.assertRaises(exceptions.MismatchedLogFilesError):
            raise exceptions.MismatchedLogFilesError
