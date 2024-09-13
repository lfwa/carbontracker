import os
import threading
import time
import traceback
import unittest
from unittest import mock, skipIf
from unittest.mock import Mock, patch, MagicMock
from threading import Event
from typing import List, Any
import numpy as np

from carbontracker import exceptions, constants
from carbontracker.tracker import (
    CarbonIntensityThread,
    CarbonTrackerThread,
    CarbonTracker,
)
from carbontracker.components.component import Component
from carbontracker.components.gpu import nvidia
from carbontracker.components.cpu import intel


class TestCarbonIntensityThread(unittest.TestCase):
    def setUp(self):
        self.logger = Mock()
        self.stop_event = Event()

    def test_init(self):
        thread = CarbonIntensityThread(self.logger, self.stop_event)
        self.assertEqual(thread.name, "CarbonIntensityThread")
        self.assertEqual(thread.daemon, True)

    @patch("carbontracker.tracker.intensity")
    def test_fetch_carbon_intensity_success(self, mock_intensity):
        mock_intensity.carbon_intensity.return_value.success = True
        mock_intensity.carbon_intensity.return_value.carbon_intensity = 10.5

        thread = CarbonIntensityThread(self.logger, self.stop_event)
        thread._fetch_carbon_intensity()

        self.assertEqual(thread.carbon_intensities[0].carbon_intensity, 10.5)

    @patch("carbontracker.tracker.intensity")
    def test_fetch_carbon_intensity_failure(self, mock_intensity):
        mock_intensity.carbon_intensity.return_value.success = False

        thread = CarbonIntensityThread(self.logger, self.stop_event)
        thread._fetch_carbon_intensity()

        self.assertEqual(len(thread.carbon_intensities), 0)

    @patch("carbontracker.tracker.intensity.CarbonIntensity")
    @patch("carbontracker.tracker.intensity")
    def test_predict_carbon_intensity(self, mock_intensity, mock_carbon_intensity):
        mock_ci_return = Mock()
        mock_ci_return.success = True
        mock_ci_return.carbon_intensity = 10.5

        mock_intensity.carbon_intensity.return_value = mock_ci_return

        mock_carbon_intensity.return_value = mock_ci_return

        thread = CarbonIntensityThread(self.logger, self.stop_event)
        thread.carbon_intensities.append(mock_ci_return)

        pred_time_dur = 1000
        ci = thread.predict_carbon_intensity(pred_time_dur)

        self.assertEqual(ci.carbon_intensity, 10.5)
        mock_intensity.set_carbon_intensity_message.assert_called_with(
            ci, pred_time_dur
        )
        self.logger.info.assert_called()
        self.logger.output.assert_called()

    @patch("carbontracker.tracker.intensity.CarbonIntensity")
    @patch("carbontracker.tracker.intensity")
    def test_average_carbon_intensity(self, mock_intensity, mock_carbon_intensity):
        mock_ci_return = Mock()
        mock_ci_return.success = True
        mock_ci_return.carbon_intensity = 10.5
        mock_ci_return.address = "test_address"

        mock_intensity.carbon_intensity.return_value = mock_ci_return

        mock_carbon_intensity.return_value = mock_ci_return

        thread = CarbonIntensityThread(self.logger, self.stop_event)
        thread.carbon_intensities.append(mock_ci_return)

        avg_ci = thread.average_carbon_intensity()

        self.assertEqual(avg_ci.carbon_intensity, 10.5)

    @patch("carbontracker.tracker.CarbonIntensityThread._fetch_carbon_intensity")
    def test_run_with_fetch_exception(self, mock_fetch_carbon_intensity):
        mock_fetch_carbon_intensity.side_effect = Exception("Test exception")
        mock_stop_event = MagicMock()
        mock_logger = MagicMock()

        thread = CarbonIntensityThread(mock_logger, mock_stop_event)
        thread.run()

        assert mock_logger.err_warn.called

    @patch("carbontracker.tracker.CarbonIntensityThread._fetch_carbon_intensity")
    def test_run_with_multiple_fetch_calls(self, mock_fetch_carbon_intensity):
        update_interval = 0.001
        wait_duration = 0.5

        mock_logger = MagicMock()
        stop_event = threading.Event()
        CarbonIntensityThread(mock_logger, stop_event, update_interval)
        time.sleep(wait_duration)

        assert mock_fetch_carbon_intensity.call_count > 1

    @patch("carbontracker.tracker.intensity.carbon_intensity")
    def test_average_carbon_intensity_empty_intensities(self, mock_carbon_intensity):
        mock_logger = MagicMock()
        stop_event = threading.Event()

        thread = CarbonIntensityThread(mock_logger, stop_event)
        thread.carbon_intensities = []
        thread.average_carbon_intensity()

        assert len(thread.carbon_intensities) == 1


class TestCarbonTrackerThread(unittest.TestCase):
    def setUp(self):
        self.mock_components: List[Any] = [
            MagicMock(name="Component1"),
            MagicMock(name="Component2"),
        ]

        for component in self.mock_components:
            component.available.return_value = True

        self.mock_logger = MagicMock(name="Logger")
        self.mock_delete = MagicMock(name="Delete")

        self.thread = CarbonTrackerThread(
            self.mock_components,
            self.mock_logger,
            False,
            self.mock_delete,
            update_interval=0.1,
        )

    def tearDown(self):
        self.thread.running = False
        self.thread.epoch_counter = 0
        self.thread.epoch_times = []

    def test_stop_tracker(self):
        self.thread.running = True
        self.thread.stop()

        self.assertFalse(self.thread.running)

        # assert_any_call because different log statements races in Python 3.11 in Github Actions
        self.mock_logger.info.assert_any_call("Monitoring thread ended.")
        self.mock_logger.output.assert_called_with(
            "Finished monitoring.", verbose_level=1
        )

    def test_stop_tracker_not_running(self):
        self.thread.running = False
        result = self.thread.stop()

        assert result is None

    @patch(
        "carbontracker.components.component.component_names",
        return_value=["gpu", "cpu"],
    )
    @patch(
        "carbontracker.components.component.handlers_by_name",
        return_value=[nvidia.NvidiaGPU, intel.IntelCPU],
    )
    def test_run_and_measure(self, mock_component_names, mock_handlers_by_name):
        self.thread.epoch_start()

        time.sleep(0.4)

        self.thread.epoch_end()
        for component in self.mock_components:
            component.collect_power_usage.assert_called_with(self.thread.epoch_counter)

    def test_init(self):
        mock_components: List[Component] = [
            MagicMock(name="Component1"),
            MagicMock(name="Component2"),
        ]
        mock_logger = MagicMock(name="Logger")
        mock_delete = MagicMock(name="Delete")

        thread = CarbonTrackerThread(mock_components, mock_logger, False, mock_delete)

        self.assertEqual(thread.components, mock_components)
        self.assertEqual(thread.logger, mock_logger)
        self.assertTrue(thread.running)
        self.assertEqual(thread.epoch_counter, 0)
        self.assertEqual(thread.epoch_times, [])
        self.assertEqual(thread.running, True)
        self.assertEqual(thread.daemon, True)

    def test_run_with_exception_ignore_errors(self):
        self.thread._components_remove_unavailable = MagicMock()
        self.thread._components_remove_unavailable.return_value = self.mock_components

        self.thread._components_init = MagicMock()
        self.thread._log_components_info = MagicMock()
        self.thread._components_shutdown = MagicMock()
        self.thread.ignore_errors = True

        self.thread._collect_measurements = MagicMock(
            side_effect=Exception("Mocked exception")
        )

        self.thread.logger.err_critical = MagicMock()
        self.thread.logger.output = MagicMock()

        os._exit = MagicMock()

        self.thread.running = True

        time.sleep(0.2)

        self.assertFalse(os._exit.called)

    def test_epoch_start(self):
        self.thread.epoch_counter = 0

        self.thread.epoch_start()

        self.assertEqual(self.thread.epoch_counter, 1)
        self.assertIsNotNone(self.thread.cur_epoch_time)

    def test_epoch_end(self):
        self.thread.cur_epoch_time = (
            time.time() - 1
        )  # Set a non-zero value for cur_epoch_time

        self.thread.epoch_end()
        time.sleep(0.2)

        self.assertTrue(self.thread.epoch_times)
        self.assertAlmostEqual(self.thread.epoch_times[-1], 1, delta=0.1)

    def test_epoch_end_too_short(self):
        mock_component: Any = MagicMock(name="Component")
        mock_component.power_usages = []

        self.thread.components = [mock_component]

        self.thread.cur_epoch_time = time.time()

        self.thread.epoch_end()

        self.assertTrue(self.thread.epoch_times)
        self.assertIsNotNone(self.thread.epoch_times[-1])
        self.mock_logger.err_warn.assert_called_with(
            "Epoch duration is too short for a measurement to be collected."
        )

    def test_no_components_available(self):
        self.thread.components = []

        with self.assertRaises(exceptions.NoComponentsAvailableError):
            self.thread.begin()

    def test_total_energy_per_epoch(self):
        mock_component1: Any = MagicMock(name="Component1")
        mock_component1.energy_usage.return_value = np.array([1.0, 2.0, 3.0])
        mock_component2: Any = MagicMock(name="Component2")
        mock_component2.energy_usage.return_value = np.array([2.0, 3.0, 4.0])

        self.thread.components = [mock_component1, mock_component2]

        self.thread.epoch_times = [1.0, 1.0, 1.0]

        total_energy = self.thread.total_energy_per_epoch()

        expected_total_energy = np.array([3.0, 5.0, 7.0]) * constants.PUE_2023
        np.testing.assert_array_equal(total_energy, expected_total_energy)

    @mock.patch("os._exit")
    def test_handle_error_ignore(self, mock_os_exit):
        self.thread.ignore_errors = True
        error = Exception("Test error")
        expected_err_str = f"Ignored error: {traceback.format_exc()}Continued training without monitoring..."

        self.thread._handle_error(error)

        self.mock_logger.err_critical.assert_called_with(expected_err_str)
        self.mock_logger.output.assert_called_with(expected_err_str)
        self.thread.delete.assert_called()
        mock_os_exit.assert_not_called()

    @mock.patch("os._exit")
    def test_handle_error_no_ignore_errors(self, mock_os_exit):
        self.thread.ignore_errors = False
        self.thread.logger = self.mock_logger
        self.thread._handle_error(Exception("Test exception"))

        self.mock_logger.err_critical.assert_called()
        self.mock_logger.output.assert_called()

        mock_os_exit.assert_called_with(70)

    @mock.patch("carbontracker.tracker.CarbonTrackerThread._handle_error")
    def test_run_exception_handling(self, mock_handle_error):
        mock_wait = mock.MagicMock()
        mock_wait.side_effect = Exception("Test exception")

        self.thread.measuring_event.wait = mock_wait
        self.thread.run()

        mock_handle_error.assert_called()


class TestCarbonTracker(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_tracker_thread = MagicMock()
        self.mock_intensity_thread = MagicMock()

        with patch(
            "carbontracker.tracker.CarbonTrackerThread",
            return_value=self.mock_tracker_thread,
        ), patch(
            "carbontracker.tracker.CarbonIntensityThread",
            return_value=self.mock_intensity_thread,
        ), patch(
            "carbontracker.tracker.loggerutil.Logger", return_value=self.mock_logger
        ), patch(
            "carbontracker.tracker.CarbonTracker._output_actual"
        ) as self.mock_output_actual, patch(
            "carbontracker.tracker.CarbonTracker._delete"
        ) as self.mock_delete:
            self.tracker = CarbonTracker(
                epochs=5,
                epochs_before_pred=1,
                monitor_epochs=3,
                update_interval=10,
                interpretable=True,
                stop_and_confirm=True,
                ignore_errors=False,
                components="all",
                devices_by_pid=False,
                log_dir=None,
                log_file_prefix="",
                verbose=1,
                decimal_precision=6,
            )

    def tearDown(self):
        self.mock_logger = None
        self.mock_intensity_thread = None
        self.mock_tracker_thread = None
        self.tracker = None

    def test_epoch_start_increments_epoch_counter_and_starts_measurement(self):
        assert self.tracker is not None
        assert self.mock_tracker_thread is not None
        initial_epoch_counter = self.tracker.epoch_counter
        self.tracker.epoch_start()
        self.assertEqual(self.tracker.epoch_counter, initial_epoch_counter + 1)
        self.assertTrue(self.mock_tracker_thread.measuring_event.is_set())

    def test_check_input_yes(self):
        with patch("builtins.input", return_value="y"):
            assert self.tracker is not None
            assert self.mock_logger is not None
            self.tracker._check_input("y")
            self.mock_logger.output.assert_called_with("Continuing...")

    def test_check_input_no(self):
        assert self.tracker is not None
        with patch("builtins.input", return_value="n"):
            with self.assertRaises(SystemExit):
                self.tracker._check_input("n")

    @patch("carbontracker.tracker.CarbonTracker._check_input")
    def test_user_query(self, mock_check_input):
        assert self.tracker is not None
        with patch("builtins.input", return_value="y"), patch.object(
            self.tracker.logger, "output"
        ) as mock_logger_output:
            self.tracker._user_query()
            mock_logger_output.assert_called_once_with("Continue training (y/n)?")

        mock_check_input.assert_called_once()

    def test_check_input_invalid(self):
        assert self.tracker is not None
        assert self.mock_logger is not None
        with patch("builtins.input", side_effect=["a", "y"]):
            self.tracker._check_input("a")
            self.mock_logger.output.assert_any_call(
                "Input not recognized. Try again (y/n):"
            )
            self.tracker._check_input("y")
            self.mock_logger.output.assert_any_call("Continuing...")

    def test_delete(self):
        assert self.tracker is not None
        assert self.mock_tracker_thread is not None
        self.tracker._delete()
        self.mock_tracker_thread.stop.assert_called_once()
        self.assertTrue(self.tracker.deleted)

    @patch("carbontracker.tracker.psutil.Process")
    def test_get_pids(self, mock_process):
        assert self.tracker is not None
        mock_process.return_value.pid = 1234
        mock_process.return_value.children.return_value = [MagicMock(pid=5678)]
        pids = self.tracker._get_pids()
        self.assertEqual(pids, [1234, 5678])

    def test_stop_when_already_deleted(self):
        """Test the stop method when the tracker has already been marked as deleted."""
        assert self.tracker is not None
        assert self.mock_logger is not None
        self.tracker.deleted = True

        self.tracker.stop()

        self.mock_logger.info.assert_not_called()
        self.mock_output_actual.assert_not_called()
        self.mock_delete.assert_not_called()

    @patch("carbontracker.tracker.CarbonTracker._output_actual")
    def test_stop_behavior(self, mock_output_actual):
        assert self.tracker is not None
        self.assertFalse(self.tracker.deleted)

        initial_epoch_counter = 2
        self.tracker.epoch_counter = initial_epoch_counter
        self.tracker.stop()

        expected_epoch_counter = initial_epoch_counter - 1
        self.assertEqual(
            self.tracker.epoch_counter,
            expected_epoch_counter,
            "Epoch counter should be decremented by 1.",
        )

        mock_output_actual.assert_called_once()

        self.assertTrue(
            self.tracker.deleted,
            "Tracker should be marked as deleted after stop is called.",
        )

    def test_epoch_end_when_deleted(self):
        assert self.tracker is not None
        assert self.mock_tracker_thread is not None
        self.tracker.deleted = True
        self.tracker.epoch_end()
        self.mock_tracker_thread.epoch_end.assert_not_called()

    @patch("carbontracker.tracker.CarbonTracker._output_actual", autospec=True)
    @patch("carbontracker.tracker.CarbonTracker._delete", autospec=True)
    def test_epoch_end_output_actual_and_delete(self, mock_delete, mock_output_actual):
        assert self.tracker is not None
        self.tracker.epoch_counter = self.tracker.monitor_epochs
        self.tracker.epoch_end()

        mock_output_actual.assert_called_once()
        mock_delete.assert_called_once()

    @patch("carbontracker.tracker.CarbonTracker._output_pred", autospec=True)
    @patch("carbontracker.tracker.CarbonTracker._user_query", autospec=True)
    def test_epoch_end_output_pred_and_user_query(
        self, mock_user_query, mock_output_pred
    ):
        assert self.tracker is not None
        self.tracker.epoch_counter = self.tracker.epochs_before_pred
        self.tracker.epoch_end()

        mock_output_pred.assert_called_once()
        mock_user_query.assert_called_once()

    @patch("carbontracker.tracker.CarbonTracker._handle_error", autospec=True)
    def test_epoch_end_exception_handling(self, mock_handle_error):
        assert self.tracker is not None
        assert self.mock_tracker_thread is not None
        self.mock_tracker_thread.epoch_end.side_effect = Exception("Test Exception")
        self.tracker.epoch_end()

        mock_handle_error.assert_called_once()

    def test_invalid_monitor_epochs_value(self):
        with self.assertRaises(ValueError):
            CarbonTracker(
                epochs=5,
                monitor_epochs=0,  # Invalid value
                epochs_before_pred=2,
                update_interval=10,
                interpretable=True,
                stop_and_confirm=False,
                ignore_errors=False,
                components="all",
                devices_by_pid=False,
                log_dir=None,
                log_file_prefix="",
                verbose=1,
                decimal_precision=6,
            )

    def test_invalid_monitor_epochs_less_than_epochs_before_pred(self):
        with self.assertRaises(ValueError):
            CarbonTracker(
                epochs=5,
                monitor_epochs=1,
                epochs_before_pred=3,
                update_interval=10,
                interpretable=True,
                stop_and_confirm=False,
                ignore_errors=False,
                components="all",
                devices_by_pid=False,
                log_dir=None,
                log_file_prefix="",
                verbose=1,
                decimal_precision=6,
            )

    @patch("carbontracker.tracker.CarbonTracker._handle_error")
    def test_epoch_start_deleted(self, mock_handle_error):
        assert self.tracker is not None
        self.tracker.deleted = True
        self.tracker.epoch_start()

        self.assertEqual(self.tracker.epoch_counter, 0)

        mock_handle_error.assert_not_called()

    @skipIf(os.environ.get("CI") == "true", "Skipped due to CI")
    @patch("carbontracker.tracker.CarbonTrackerThread.epoch_start")
    @patch("carbontracker.tracker.CarbonTracker._handle_error")
    def test_epoch_start_exception(
        self, mock_handle_error, mock_tracker_thread_epoch_start
    ):
        tracker = CarbonTracker(
            epochs=5,
            epochs_before_pred=1,
            monitor_epochs=3,
            update_interval=10,
            interpretable=True,
            stop_and_confirm=True,
            ignore_errors=False,
            components="all",
            devices_by_pid=False,
            log_dir=None,
            log_file_prefix="",
            verbose=1,
            decimal_precision=6,
        )

        tracker.deleted = False
        mock_tracker_thread_epoch_start.side_effect = Exception("Test Exception")
        tracker.epoch_start()
        self.assertEqual(tracker.epoch_counter, 0)

        mock_tracker_thread_epoch_start.assert_called_once()
        mock_handle_error.assert_called_once()

    def test_handle_error_ignore_errors(self):
        assert self.tracker is not None
        assert self.mock_logger is not None
        self.tracker.ignore_errors = True
        self.tracker._handle_error(Exception("Test exception"))
        self.mock_logger.err_critical.assert_called_once()

    def test_handle_error_no_ignore_errors(self):
        assert self.tracker is not None
        self.tracker.ignore_errors = False
        with self.assertRaises(SystemExit):
            self.tracker._handle_error(Exception("Test exception"))

    @skipIf(os.environ.get("CI") == "true", "Skipped due to CI")
    @patch(
        "carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap.set_api_key"
    )
    def test_set_api_keys_electricitymaps(self, mock_set_api_key):
        tracker = CarbonTracker(epochs=1)
        api_dict = {"ElectricityMaps": "mock_api_key"}
        tracker.set_api_keys(api_dict)

        mock_set_api_key.assert_called_once_with("mock_api_key")

    @skipIf(os.environ.get("CI") == "true", "Skipped due to CI")
    @patch("carbontracker.tracker.CarbonTracker.set_api_keys")
    def test_carbontracker_api_key(self, mock_set_api_keys):
        api_dict = {"ElectricityMaps": "mock_api_key"}
        _tracker = CarbonTracker(epochs=1, api_keys=api_dict)

        mock_set_api_keys.assert_called_once_with(api_dict)

    def test_output_energy(self):
        assert self.tracker is not None
        assert self.mock_logger is not None

        description = "Test description"
        time = 1000
        energy = 50.123
        co2eq = 100.456
        conversions = [(100, "km"), (200, "kg")]

        self.tracker._output_energy(description, time, energy, co2eq, conversions)

        expected_output = (
            "\nTest description\n"
            "\tTime:\t0:16:40\n"
            "\tEnergy:\t50.123000 kWh\n"
            "\tCO2eq:\t100.456000 g"
            "\n\tThis is equivalent to:"
            "\n\t100.000000 km"
            "\n\t200.000000 kg"
        )
        self.mock_logger.output.assert_called_once_with(
            expected_output, verbose_level=1
        )

    def test_output_actual_zero_epochs(self):
        assert self.tracker is not None
        assert self.mock_logger is not None

        self.tracker.epochs_before_pred = 0
        self.tracker.tracker.total_energy_per_epoch = MagicMock(
            return_value=np.array([10, 20, 30])
        )
        self.tracker.tracker.epoch_times = [100, 200, 300]
        self.tracker._co2eq = MagicMock(return_value=150)
        self.tracker.interpretable = True

        self.tracker._output_actual()

        expected_output = (
            "\nActual consumption:\n"
            "\tTime:\t0:10:00\n"
            "\tEnergy:\t60.000000 kWh\n"
            "\tCO2eq:\t150.000000 g"
            "\n\tThis is equivalent to:\n"
            "\t1.395349 km travelled by car"
        )

        self.mock_logger.output.assert_called_once_with(
            expected_output, verbose_level=1
        )

    def test_output_actual_nonzero_epochs(self):
        assert self.tracker is not None
        assert self.mock_logger is not None

        self.tracker.epochs_before_pred = 1
        self.tracker.epoch_counter = 2
        self.tracker.tracker.total_energy_per_epoch = MagicMock(
            return_value=np.array([10, 20, 30])
        )
        self.tracker.tracker.epoch_times = [100, 200, 300]
        self.tracker._co2eq = MagicMock(return_value=150)
        self.tracker.interpretable = True

        self.tracker._output_actual()

        expected_description = "Actual consumption for 2 epoch(s):"

        expected_output = (
            f"\n{expected_description}\n"
            "\tTime:\t0:10:00\n"
            "\tEnergy:\t60.000000 kWh\n"
            "\tCO2eq:\t150.000000 g"
            "\n\tThis is equivalent to:\n"
            "\t1.395349 km travelled by car"
        )

        self.mock_logger.output.assert_called_once_with(
            expected_output, verbose_level=1
        )

    def test_output_pred(self):
        assert self.tracker is not None
        assert self.mock_logger is not None

        predictor = MagicMock()
        predictor.predict_energy = MagicMock(return_value=100)
        predictor.predict_time = MagicMock(return_value=1000)

        self.tracker.epochs = 5
        self.tracker.tracker.total_energy_per_epoch = MagicMock(
            return_value=[10, 20, 30]
        )
        self.tracker.tracker.epoch_times = [100, 200, 300]
        self.tracker._co2eq = MagicMock(return_value=150)
        self.tracker.interpretable = True

        self.tracker._output_pred()

        expected_description = "Predicted consumption for 5 epoch(s):"

        expected_output = (
            f"\n{expected_description}\n"
            "\tTime:\t0:16:40\n"
            "\tEnergy:\t100.000000 kWh\n"
            "\tCO2eq:\t150.000000 g"
            "\n\tThis is equivalent to:\n"
            "\t1.395349 km travelled by car"
        )

        self.mock_logger.output.assert_called_once_with(
            expected_output, verbose_level=1
        )

    def test_co2eq_with_pred_time_dur(self):
        assert self.tracker is not None
        intensity_updater = MagicMock()
        intensity_updater.predict_carbon_intensity = MagicMock(
            return_value=MagicMock(carbon_intensity=0.5)
        )

        energy_usage = 100
        pred_time_dur = 1000

        self.tracker.intensity_updater = intensity_updater

        co2eq = self.tracker._co2eq(energy_usage, pred_time_dur)

        expected_co2eq = 50
        self.assertEqual(co2eq, expected_co2eq)

    def test_co2eq_without_pred_time_dur(self):
        assert self.tracker is not None
        intensity_updater = MagicMock()
        intensity_updater.average_carbon_intensity = MagicMock(
            return_value=MagicMock(carbon_intensity=0.5)
        )

        energy_usage = 100

        self.tracker.intensity_updater = intensity_updater

        co2eq = self.tracker._co2eq(energy_usage)

        expected_co2eq = 50
        self.assertEqual(co2eq, expected_co2eq)

    @patch("sys.exit")
    def test_set_api_keys_with_invalid_name_exits(self, mock_exit):
        assert self.tracker is not None
        self.tracker.set_api_keys({"invalid_name": "test_key"})
        mock_exit.assert_called_once_with(70)

    @mock.patch("carbontracker.tracker.CarbonTracker._get_pids")
    @mock.patch("carbontracker.tracker.loggerutil.Logger")
    @mock.patch("carbontracker.tracker.CarbonTrackerThread")
    @mock.patch("carbontracker.tracker.CarbonIntensityThread")
    def test_exception_handling(
        self, mock_intensity_thread, mock_tracker_thread, mock_logger, mock_get_pids
    ):
        mock_get_pids.side_effect = Exception("Test exception in _get_pids")
        mock_logger.side_effect = Exception("Test exception in Logger initialization")
        mock_tracker_thread.side_effect = Exception(
            "Test exception in CarbonTrackerThread initialization"
        )
        mock_intensity_thread.side_effect = Exception(
            "Test exception in CarbonIntensityThread initialization"
        )

        with self.assertRaises(Exception) as context:
            CarbonTracker(log_dir=None, verbose=False, log_file_prefix="", epochs=1)

        self.assertEqual(
            str(context.exception), "'CarbonTracker' object has no attribute 'logger'"
        )

    # # Instantiating a second instance should not make this instance log twice
    # @mock.patch("carbontracker.tracker.CarbonIntensityThread")
    # def test_multiple_instances(self, mock_intensity_thread):
    #     assert self.mock_logger is not None
    #     assert self.tracker is not None

    #     tracker2 = CarbonTracker(
    #         epochs=5,
    #         epochs_before_pred=1,
    #         monitor_epochs=3,
    #         update_interval=10,
    #         interpretable=True,
    #         stop_and_confirm=True,
    #         ignore_errors=False,
    #         components="all",
    #         devices_by_pid=False,
    #         log_dir=None,
    #         log_file_prefix="",
    #         verbose=1,
    #         decimal_precision=6,
    #     )

    #     predictor = MagicMock()
    #     predictor.predict_energy = MagicMock(return_value=100)
    #     predictor.predict_time = MagicMock(return_value=1000)

    #     self.tracker.epochs = 5
    #     self.tracker.tracker.total_energy_per_epoch = MagicMock(
    #         return_value=[10, 20, 30]
    #     )
    #     self.tracker.tracker.epoch_times = [100, 200, 300]
    #     self.tracker._co2eq = MagicMock(return_value=150)
    #     self.tracker.interpretable = True

    #     self.tracker._output_pred()

    #     expected_description = "Predicted consumption for 5 epoch(s):"

    #     expected_output = (
    #         f"\n{expected_description}\n"
    #         "\tTime:\t0:16:40\n"
    #         "\tEnergy:\t100.000000 kWh\n"
    #         "\tCO2eq:\t150.000000 g"
    #         "\n\tThis is equivalent to:\n"
    #         "\t1.395349 km travelled by car"
    #     )

    #     self.mock_logger.output.assert_called_once_with(
    #         expected_output, verbose_level=1
    #     )


if __name__ == "__main__":
    unittest.main()
