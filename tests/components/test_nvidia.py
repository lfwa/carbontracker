import sys
import unittest
from unittest.mock import patch, MagicMock
import pynvml
from carbontracker import exceptions
from carbontracker.components.gpu.nvidia import NvidiaGPU


class PynvmlStub:
    @staticmethod
    def nvmlInit():
        pass

    @staticmethod
    def nvmlShutdown():
        # NvidiaGPU._handles = None
        pass

    @staticmethod
    def nvmlDeviceGetHandleByIndex(index):
        return index

    @staticmethod
    def nvmlDeviceGetCount():
        return 1

    @staticmethod
    def nvmlDeviceGetPowerUsage(handle):
        return 1000  # Returns power usage in mW

    @staticmethod
    def nvmlDeviceGetName(handle):
        if sys.version_info < (3, 10):
            return b"GPU"
        else:
            return "GPU"

    @staticmethod
    def nvmlDeviceGetComputeRunningProcesses(handle):
        mock_process = MagicMock()
        mock_process.pid = 1234
        return [mock_process]

    @staticmethod
    def nvmlDeviceGetGraphicsRunningProcesses(handle):
        mock_process = MagicMock()
        mock_process.pid = 1234
        return [mock_process]


class TestNvidiaGPU(unittest.TestCase):
    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_devices(self):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        gpu._handles = [0]
        self.assertEqual(gpu.devices(), ["GPU"])

    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_available(self):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        self.assertTrue(gpu.available())

    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_power_usage(self):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        gpu._handles = [0]
        self.assertEqual(gpu.power_usage(), [1])

    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_init_shutdown(self):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        gpu.init()
        self.assertNotEqual(gpu._handles, [])
        gpu.shutdown()
        self.assertEqual(gpu._handles, [])

    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_init(self):
        gpu = NvidiaGPU(pids=[1234], devices_by_pid=True)
        self.assertEqual(gpu.pids, [1234])
        self.assertEqual(gpu.devices_by_pid, True)
        self.assertEqual(gpu._handles, [])

    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_get_handles(self):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        gpu.init()
        self.assertEqual(gpu._handles, [0])
        gpu.shutdown()

    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    @patch("carbontracker.components.gpu.nvidia.os.environ.get", return_value="0")
    def test_slurm_gpu_indices(self, mock_get):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        self.assertEqual(gpu._slurm_gpu_indices(), [0])

    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_get_handles_by_pid(self):
        gpu = NvidiaGPU(pids=[1234], devices_by_pid=True)
        gpu.init()
        self.assertEqual(gpu._handles, [0])
        gpu.shutdown()

    @patch("sys.version_info", new=(3, 8))
    @patch("carbontracker.components.gpu.nvidia.pynvml", new=PynvmlStub)
    def test_devices_python_version_less_than_3_10(self):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        gpu._handles = [0]
        self.assertEqual(gpu.devices(), ["GPU"])

    @patch(
        "carbontracker.components.gpu.nvidia.pynvml.nvmlDeviceGetPowerUsage",
        side_effect=pynvml.NVMLError(pynvml.NVML_ERROR_UNKNOWN),
    )
    def test_power_usage_error_retrieving_power_usage(
        self, mock_nvmlDeviceGetPowerUsage
    ):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        gpu._handles = [0]
        with self.assertRaises(exceptions.GPUPowerUsageRetrievalError):
            gpu.power_usage()

    @patch(
        "carbontracker.components.gpu.nvidia.pynvml.nvmlDeviceGetComputeRunningProcesses",
        return_value=[],
    )
    @patch(
        "carbontracker.components.gpu.nvidia.pynvml.nvmlDeviceGetGraphicsRunningProcesses",
        return_value=[],
    )
    def test_get_handles_by_pid_no_gpus_running_processes(
        self,
        mock_nvmlDeviceGetComputeRunningProcesses,
        mock_nvmlDeviceGetGraphicsRunningProcesses,
    ):
        gpu = NvidiaGPU(pids=[1234], devices_by_pid=True)
        self.assertEqual(gpu._handles, [])

    @patch("carbontracker.components.gpu.nvidia.pynvml.nvmlInit")
    @patch(
        "carbontracker.components.gpu.nvidia.pynvml.nvmlDeviceGetCount", return_value=0
    )
    def test_available_no_gpus(self, mock_nvmlDeviceGetCount, mock_nvmlInit):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        self.assertFalse(gpu.available())

    @patch(
        "carbontracker.components.gpu.nvidia.pynvml.nvmlInit",
        side_effect=pynvml.NVMLError(pynvml.NVML_ERROR_UNKNOWN),
    )
    def test_available_nvml_error(self, mock_nvmlInit):
        gpu = NvidiaGPU(pids=[], devices_by_pid=False)
        self.assertFalse(gpu.available())


if __name__ == "__main__":
    unittest.main()
