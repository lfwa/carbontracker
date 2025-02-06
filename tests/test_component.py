import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from carbontracker import exceptions
from carbontracker.components.gpu import nvidia
from carbontracker.components.component import (
    Component,
    create_components,
    error_by_name,
)


class TestComponent(unittest.TestCase):
    @patch("carbontracker.components.component.component_names", return_value=["gpu"])
    @patch(
        "carbontracker.components.component.error_by_name",
        return_value=exceptions.GPUError("No GPU(s) available."),
    )
    @patch(
        "carbontracker.components.component.handlers_by_name",
        return_value=[MagicMock(spec=nvidia.NvidiaGPU)],
    )
    def test_init_valid_component(
        self, mock_handlers_by_name, mock_error_by_name, mock_component_names
    ):
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        self.assertEqual(component.name, "gpu")
        self.assertEqual(component._handler, mock_handlers_by_name()[0]())

    def test_init_invalid_component(self):
        with self.assertRaises(exceptions.ComponentNameError):
            Component(name="unknown", pids=[], devices_by_pid=False, logger=None)

    def test_devices(self):
        handler_mock = MagicMock(devices=MagicMock(return_value=["Test GPU"]))
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        component._handler = handler_mock
        self.assertEqual(component.devices(), ["Test GPU"])

    def test_available_true(self):
        handler_mock = MagicMock(available=MagicMock(return_value=True))
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        component._handler = handler_mock
        self.assertTrue(component.available())

    @patch(
        "carbontracker.components.gpu.nvidia.NvidiaGPU.available", return_value=False
    )
    @patch(
        "carbontracker.components.apple_silicon.powermetrics.AppleSiliconGPU.available",
        return_value=False,
    )
    def test_available_false(self, mock_apple_gpu_available, mock_nvidia_gpu_available):
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        self.assertFalse(component.available())

    def test_collect_power_usage_no_measurement(self):
        handler_mock = MagicMock(
            power_usage=MagicMock(side_effect=exceptions.IntelRaplPermissionError(file_names=["file1", "file2"]))
        )
        component = Component(name="cpu", pids=[], devices_by_pid=False, logger=MagicMock(err_critical=MagicMock()))
        component._handler = handler_mock
        component.collect_power_usage(epoch=1)
        self.assertEqual(component.power_usages, [[], [0]])

    def test_collect_power_usage_with_measurement(self):
        handler_mock = MagicMock(power_usage=MagicMock(return_value=[1000]))
        component = Component(name="cpu", pids=[], devices_by_pid=False, logger=None)
        component._handler = handler_mock
        component.collect_power_usage(epoch=1)
        self.assertEqual(component.power_usages, [[1000]])

    def test_collect_power_usage_with_measurement_but_no_epoch(self):
        power_collector = Component(name="cpu", pids=[], devices_by_pid=False, logger=None)
        power_collector._handler = MagicMock(power_usage=MagicMock(return_value=[1000]))
        power_collector.collect_power_usage(epoch=0)
        assert len(power_collector.power_usages) == 0

    def test_collect_power_usage_with_previous_measurement(self):
        power_collector = Component(name="cpu", pids=[], devices_by_pid=False, logger=None)
        power_collector._handler = MagicMock(power_usage=MagicMock(return_value=[1000]))
        power_collector.collect_power_usage(epoch=1)
        power_collector.collect_power_usage(epoch=3)
        assert len(power_collector.power_usages) == 3

    def test_collect_power_usage_GPUPowerUsageRetrievalError(self):
        handler_mock = MagicMock(
            power_usage=MagicMock(side_effect=exceptions.GPUPowerUsageRetrievalError)
        )
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=MagicMock(err_critical=MagicMock()))
        component._handler = handler_mock
        component.collect_power_usage(epoch=1)
        self.assertEqual(component.power_usages, [[], [0]])

    def test_energy_usage(self):
        component = Component(name="cpu", pids=[], devices_by_pid=False, logger=None)
        component.power_usages = [[1000], [2000], [3000]]
        epoch_times = [1, 2, 3]
        energy_usages = component.energy_usage(epoch_times)
        self.assertEqual(
            energy_usages, [0.0002777777777777778, 0.0011111111111111111, 0.0025]
        )
        self.assertTrue(np.all(np.array(energy_usages) > 0))

    def test_energy_usage_no_measurements(self):
        component = Component(name="cpu", pids=[], devices_by_pid=False, logger=None)
        component.power_usages = [[]]
        epoch_times = [1]
        energy_usages = component.energy_usage(epoch_times)
        self.assertEqual(energy_usages, [0])

    def test_energy_usage_with_power_from_later_epoch(self):
        component = Component(name="cpu", pids=[], devices_by_pid=False, logger=None)
        component.power_usages = [[1000], [2000], [3000]]
        epoch_times = [1, 2, 3, 4]
        energy_usages = component.energy_usage(epoch_times)
        self.assertEqual(
            energy_usages,
            [0.0002777777777777778, 0.0011111111111111111, 0.0025, 0.0025],
        )

    def test_energy_usage_no_power(self):
        component = Component(name="cpu", pids=[], devices_by_pid=False, logger=None)
        component.power_usages = [[], [], [], [], []]
        epoch_times = [1, 2, 3, 4, 5]
        energy_usages = component.energy_usage(epoch_times)
        expected_energy_usages = [0, 0, 0, 0, 0]
        assert np.allclose(
            energy_usages, expected_energy_usages, atol=1e-8
        ), f"Expected {expected_energy_usages}, but got {energy_usages}"

    def test_init(self):
        handler_mock = MagicMock()
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        component._handler = handler_mock
        component.init()
        handler_mock.init.assert_called_once()

        self.assertEqual(component.name, "gpu")
        self.assertEqual(component._handler, handler_mock)
        self.assertEqual(component.power_usages, [])
        self.assertEqual(component.cur_epoch, -1)

    def test_shutdown(self):
        handler_mock = MagicMock()
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        component._handler = handler_mock
        component.shutdown()
        handler_mock.shutdown.assert_called_once()

    def test_create_components(self):
        gpu = create_components("gpu", pids=[], devices_by_pid=False, logger=None)
        cpu = create_components("cpu", pids=[], devices_by_pid=False, logger=None)
        all_components = create_components("all", pids=[], devices_by_pid=False, logger=None)
        self.assertEqual(len(gpu), 1)
        self.assertEqual(len(cpu), 1)
        self.assertEqual(len(all_components), 2)

    def test_error_by_name(self):
        self.assertEqual(
            str(error_by_name("gpu")), str(exceptions.GPUError("No GPU(s) available."))
        )
        self.assertEqual(
            str(error_by_name("cpu")), str(exceptions.CPUError("No CPU(s) available."))
        )

    def test_handler_property_with_handler_set(self):
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        component._handler = "test"
        self.assertEqual(component.handler, "test")

    def test_handler_property_without_handler(self):
        component = Component(name="gpu", pids=[], devices_by_pid=False, logger=None)
        component._handler = None
        with self.assertRaises(exceptions.GPUError):
            component.handler()


if __name__ == "__main__":
    unittest.main()
