import io
from unittest import mock
import os
from carbontracker import exceptions
from pyfakefs import fake_filesystem_unittest

from carbontracker import parser
from carbontracker.parser import (
    extract_measurements,
    parse_logs,
    print_aggregate,
    get_stats,
    parse_equivalents,
)


class TestParser(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    @mock.patch("os.path.getsize")
    def test_get_all_logs(self, mock_getsize, mock_isfile, mock_listdir):
        log_dir = "/path/to/logs"

        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents="output_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker_output.log"),
            contents="output_log2 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents="std_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker.log"),
            contents="std_log2 content",
        )

        mock_listdir.return_value = [
            "10151_2024-03-26T105926Z_carbontracker_output.log",
            "32487_2024-06-26T141608Z_carbontracker_output.log",
            "10151_2024-03-26T105926Z_carbontracker.log",
            "32487_2024-06-26T141608Z_carbontracker.log",
        ]

        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_getsize.return_value = 100

        output_logs, std_logs = parser.get_all_logs(log_dir)

        expected_output_logs = [
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker_output.log"),
        ]
        expected_std_logs = [
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker.log"),
        ]

        self.assertCountEqual(output_logs, expected_output_logs)
        self.assertCountEqual(std_logs, expected_std_logs)

    @mock.patch("os.listdir")
    def test_get_devices(self, mock_open):
        log_data = """2022-11-14 15:42:43 - CarbonTracker: The following components were found: GPU with device(s) NVIDIA GeForce RTX 3060. CPU with device(s) cpu:0.
    2022-11-14 15:43:37 - CarbonTracker: 
    Actual consumption for 1 epoch(s):
    	Time:	0:00:53
    	Energy:	0.003504 kWh
    	CO2eq:	0.357451 g
    	This is equivalent to:
    	0.002969 km travelled by car
    2022-11-14 15:43:37 - CarbonTracker: 
    Predicted consumption for 4 epoch(s):
    	Time:	0:03:33
    	Energy:	0.014018 kWh
    	CO2eq:	1.429803 g
    	This is equivalent to:
    	0.011875 km travelled by car
    2022-11-14 15:43:37 - CarbonTracker: Finished monitoring."""

        mock_open.return_value.read.return_value = log_data

        devices = parser.get_devices(log_data)

        expected_devices = {"gpu": ["NVIDIA GeForce RTX 3060"], "cpu": ["cpu:0"]}

        self.assertEqual(devices, expected_devices)

    def test_get_epoch_durations(self):
        std_log_data = "2022-11-14 15:44:48 - Epoch 1:\nDuration: 0:02:21.90\n2022-11-14 15:44:48 - Epoch 2:\nDuration: 0:01:30"

        epoch_durations = parser.get_epoch_durations(std_log_data)

        expected_epoch_durations = [141.9, 90.0]

        self.assertEqual(epoch_durations, expected_epoch_durations)

    def test_get_avg_power_usages(self):
        std_log_data = (
            "2022-11-14 15:44:48 - Average power usage (W) for gpu: [136.86084615]\n"
            "2022-11-14 15:44:48 - Average power usage (W) for cpu: [13.389104]"
        )

        avg_power_usages = parser.get_avg_power_usages(std_log_data)

        expected_avg_power_usages = {"gpu": [[136.86084615]], "cpu": [[13.389104]]}

        self.assertEqual(avg_power_usages, expected_avg_power_usages)

    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    @mock.patch("os.path.getmtime")
    def test_get_most_recent_logs(self, mock_getmtime, mock_isfile, mock_listdir):
        log_dir = "/path/to/logs"

        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents="output_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker_output.log"),
            contents="output_log2 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents="std_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker.log"),
            contents="std_log2 content",
        )

        mock_listdir.return_value = [
            "10151_2024-03-26T105926Z_carbontracker_output.log",
            "32487_2024-06-26T141608Z_carbontracker_output.log",
            "10151_2024-03-26T105926Z_carbontracker.log",
            "32487_2024-06-26T141608Z_carbontracker.log",
        ]

        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_getmtime.side_effect = [
            100,
            200,
            300,
            400,
        ]  # Mock the modification timestamps

        std_log, output_log = parser.get_most_recent_logs(log_dir)

        expected_std_log = os.path.join(
            log_dir, "32487_2024-06-26T141608Z_carbontracker.log"
        )
        expected_output_log = os.path.join(
            log_dir, "32487_2024-06-26T141608Z_carbontracker_output.log"
        )

        self.assertEqual(std_log, expected_std_log)
        self.assertEqual(output_log, expected_output_log)

    def test_get_time(self):
        time_str = "0:02:22"

        duration = parser.get_time(time_str)

        expected_duration = 142.0

        self.assertEqual(duration, expected_duration)

    def test_get_early_stop(self):
        std_log_data = "2022-11-14 15:44:48 - CarbonTracker: Training was interrupted"

        early_stop = parser.get_early_stop(std_log_data)

        self.assertTrue(early_stop)

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    def test_get_consumption(self, mock_open):
        output_log_data = (
            "2022-11-14 15:44:48 - CarbonTracker: Actual consumption for 1 epoch(s):\n"
            "	Time:	0:02:22\n"
            "	Energy:	0.009417 kWh\n"
            "	CO2eq:	0.960490 g\n"
            "	This is equivalent to:\n"
            "	0.007977 km travelled by car\n"
        )

        mock_open.return_value.read.return_value = output_log_data

        actual, pred = parser.get_consumption(output_log_data)

        expected_actual = {
            "epochs": 1,
            "duration (s)": 142.0,
            "energy (kWh)": 0.009417,
            "co2eq (g)": 0.96049,
            "equivalents": {"km travelled by car": 0.007977},
        }
        expected_pred = None

        self.assertEqual(actual, expected_actual)
        self.assertEqual(pred, expected_pred)

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    def test_parse_all_logs(self, mock_isfile, mock_listdir, mock_open):
        log_dir = "/path/to/logs"

        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents="output_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents="std_log1 content",
        )

        mock_listdir.return_value = [
            "10151_2024-03-26T105926Z_carbontracker_output.log",
            "10151_2024-03-26T105926Z_carbontracker.log",
        ]
        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_open.return_value.read.return_value = "content"

        logs = parser.parse_all_logs(log_dir)

        self.assertEqual(len(logs), 1)
        self.assertEqual(
            logs[0]["output_filename"],
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
        )
        self.assertEqual(
            logs[0]["standard_filename"],
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
        )

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    @mock.patch("carbontracker.parser.get_devices")
    def test_parse_logs(self, mock_get_devices, mock_isfile, mock_listdir, mock_open):
        log_dir = "/path/to/logs"

        std_log_data = (
            "2022-11-14 15:44:48 - Average power usage (W) for gpu: [136.86084615]\n"
            "2022-11-14 15:44:48 - Average power usage (W) for cpu: [13.389104]\n"
            "2022-11-14 15:44:48 - Epoch 1:\nDuration: 0:02:21.90"
        )

        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents="output_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents=std_log_data,
        )

        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_open.return_value.read.return_value = std_log_data
        mock_get_devices.return_value = {
            "gpu": ["NVIDIA GeForce RTX 3060"],
            "cpu": ["cpu:0"],
        }

        components = parser.parse_logs(
            log_dir,
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
        )

        self.assertIn("gpu", components)
        self.assertIn("cpu", components)

    def test_get_avg_power_usages_none_power(self):
        std_log_data = "2022-11-14 15:44:48 - Average power usage (W) for gpu: None"

        avg_power_usages = parser.get_avg_power_usages(std_log_data)

        expected_avg_power_usages = {"gpu": [[0.0]]}

        self.assertEqual(avg_power_usages, expected_avg_power_usages)

    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    @mock.patch("os.path.getsize")
    def test_get_all_logs_mismatched_files(
        self, mock_getsize, mock_isfile, mock_listdir
    ):
        log_dir = "/path/to/logs"

        # Create three matching pairs of log files
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents="output_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents="std_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker_output.log"),
            contents="output_log2 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker.log"),
            contents="std_log2 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "40793_2024-03-26T131535Z_carbontracker_output.log"),
            contents="output_log3 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "40793_2024-03-26T131535Z_carbontracker.log"),
            contents="std_log3 content",
        )

        # Add extra unmatched output log file
        self.fs.create_file(
            os.path.join(log_dir, "9803_2024-03-26T105836Z_carbontracker_output.log"),
            contents="output_log4 content",
        )

        mock_listdir.return_value = [
            "10151_2024-03-26T105926Z_carbontracker_output.log",
            "32487_2024-06-26T141608Z_carbontracker_output.log",
            "40793_2024-03-26T131535Z_carbontracker_output.log",
            "9803_2024-03-26T105836Z_carbontracker_output.log",
            "10151_2024-03-26T105926Z_carbontracker.log",
            "32487_2024-06-26T141608Z_carbontracker.log",
            "40793_2024-03-26T131535Z_carbontracker.log",
        ]

        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_getsize.return_value = 100

        expected = [os.path.join(log_dir, f) for f in mock_listdir.return_value]
        self.assertTupleEqual(
            parser.get_all_logs(log_dir),
            (expected[:3], expected[4:]),
        )

    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    @mock.patch("os.path.getsize")
    def test_get_all_logs_mismatched_files_extra_std_log(
        self, mock_getsize, mock_isfile, mock_listdir
    ):
        log_dir = "/path/to/logs"

        # Create three matching pairs of log files
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents="output_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents="std_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker_output.log"),
            contents="output_log2 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "32487_2024-06-26T141608Z_carbontracker.log"),
            contents="std_log2 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "40793_2024-03-26T131535Z_carbontracker_output.log"),
            contents="output_log3 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "40793_2024-03-26T131535Z_carbontracker.log"),
            contents="std_log3 content",
        )

        # Add extra unmatched std log file
        self.fs.create_file(
            os.path.join(log_dir, "9803_2024-03-26T105836Z_carbontracker.log"),
            contents="std_log4 content",
        )

        mock_listdir.return_value = [
            "10151_2024-03-26T105926Z_carbontracker_output.log",
            "32487_2024-06-26T141608Z_carbontracker_output.log",
            "40793_2024-03-26T131535Z_carbontracker_output.log",
            "10151_2024-03-26T105926Z_carbontracker.log",
            "32487_2024-06-26T141608Z_carbontracker.log",
            "40793_2024-03-26T131535Z_carbontracker.log",
            "9803_2024-03-26T105836Z_carbontracker.log",
        ]

        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_getsize.return_value = 100

        expected = [os.path.join(log_dir, f) for f in mock_listdir.return_value]
        self.assertTupleEqual(
            parser.get_all_logs(log_dir), (expected[:3], expected[3:6])
        )

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    def test_get_consumption_no_equivalents(self, mock_open):
        output_log_data = (
            "2022-11-14 15:44:48 - CarbonTracker: "
            "Actual consumption for 1 epoch(s):\n"
            "   Time:  0:02:22\n"
            "   Energy:    0.009417 kWh\n"
            "   CO2eq: 0.960490 g\n"
            "   This is equivalent to:\n"
        )

        mock_open.return_value.read.return_value = output_log_data

        actual, pred = parser.get_consumption(output_log_data)

        expected_actual = {
            "epochs": 1,
            "duration (s)": 142.0,
            "energy (kWh)": 0.009417,
            "co2eq (g)": 0.96049,
            "equivalents": {},
        }
        expected_pred = None

        self.assertEqual(actual, expected_actual)
        self.assertEqual(pred, expected_pred)

    def test_parse_logs_no_files(self):
        log_dir = "/logs"
        self.fs.create_file(log_dir + "/test_carbontracker.log")
        self.fs.create_file(log_dir + "/test_carbontracker_output.log")

        # No assertion - we are testing that no errors are raised
        parse_logs(log_dir)

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("carbontracker.parser.get_avg_power_usages", return_value={})
    @mock.patch("carbontracker.parser.get_devices")
    def test_parse_logs_consumption_no_power_usages(
        self, mock_get_devices, mock_power_usages, mock_open
    ):
        log_dir = "/logs"
        std_log_file = log_dir + "/test_carbontracker.log"
        output_log_file = log_dir + "/test_carbontracker_output.log"

        std_log_data = (
            "2022-11-14 15:42:43 - carbontracker version 1.1.6\n"
            "2022-11-14 15:42:43 - Only predicted and actual consumptions are multiplied by a PUE coefficient of 1.59 (Rhonda Ascierto, 2019, Uptime Institute Global Data Center Survey).\n"
            "2022-11-14 15:42:43 - The following components were found: GPU with device(s) NVIDIA GeForce RTX 3060. CPU with device(s) cpu:0.\n"
            "2022-11-14 15:42:43 - Monitoring thread started.\n"
            "2022-11-14 15:43:37 - Epoch 1:\n"
            "2022-11-14 15:43:37 - Duration: 0:00:53.25\n"
            "2022-11-14 15:43:37 - Average power usage (W) for gpu: [None]\n"
            "2022-11-14 15:43:37 - Average power usage (W) for cpu: [None]\n"
            "2022-11-14 15:43:37 - Carbon intensities (gCO2/kWh) fetched every 900 s at detected location Copenhagen, Capital Region, DK: [102.0]\n"
            "2022-11-14 15:43:37 - Average carbon intensity during training was 102.00 gCO2/kWh at detected location: Copenhagen, Capital Region, DK.\n"
            "2022-11-14 15:43:37 - Carbon intensity for the next 0:03:33 is predicted to be 102.00 gCO2/kWh at detected location: Copenhagen, Capital Region, DK.\n"
            "2022-11-14 15:43:37 - Monitoring thread ended.\n"
        )

        output_log_data = "No power usage data"

        self.fs.create_dir(log_dir)
        self.fs.create_file(std_log_file, contents=std_log_data)
        self.fs.create_file(output_log_file, contents=output_log_data)

        mock_open.return_value.read.return_value = std_log_data

        mock_get_devices.return_value = {
            "gpu": ["NVIDIA GeForce RTX 3060"],
            "cpu": ["cpu:0"],
        }

        components = parser.parse_logs(log_dir, std_log_file, output_log_file)

        expected_components = {
            "gpu": {
                "avg_power_usages (W)": None,
                "avg_energy_usages (J)": None,
                "epoch_durations (s)": [53.25],
                "devices": ["NVIDIA GeForce RTX 3060"],
            },
            "cpu": {
                "avg_power_usages (W)": None,
                "avg_energy_usages (J)": None,
                "epoch_durations (s)": [53.25],
                "devices": ["cpu:0"],
            },
        }

        self.assertEqual(components, expected_components)

    @mock.patch("re.search")
    def test_extract_measurements_no_match(self, mock_search):
        mock_search.return_value = None

        measurements = extract_measurements(None)

        self.assertIsNone(measurements)

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_print_aggregate(self, mock_stdout):
        log_dir = "/logs"
        self.fs.create_file(log_dir + "/test_carbontracker.log")
        self.fs.create_file(log_dir + "/test_carbontracker_output.log")

        print_aggregate(log_dir)

        self.assertIn("Measured by carbontracker", mock_stdout.getvalue())

    @mock.patch("carbontracker.parser.get_all_logs")
    def test_aggregate_consumption_all_logs_none(self, mock_get_all_logs):
        log_dir = "/path/to/logs"
        mock_get_all_logs.return_value = ([], [])

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        self.assertEqual(total_energy, 0)
        self.assertEqual(total_co2eq, 0)
        self.assertEqual(total_equivalents, {})

    @mock.patch("carbontracker.parser.get_all_logs")
    @mock.patch("carbontracker.parser.get_consumption")
    @mock.patch("carbontracker.parser.get_early_stop")
    def test_aggregate_consumption(
        self, mock_get_early_stop, mock_get_consumption, mock_get_all_logs
    ):
        log_dir = "/path/to/logs"
        output_log_path = "/path/to/logs/output_log1"
        std_log_path = "/path/to/logs/std_log1"

        self.fs.create_file(output_log_path, contents="output_log_content")
        self.fs.create_file(std_log_path, contents="std_log_content")

        mock_get_all_logs.return_value = ([output_log_path], [std_log_path])
        mock_get_consumption.return_value = (None, None)
        mock_get_early_stop.return_value = False

        with mock.patch(
            "builtins.open", mock.mock_open(read_data="mock_data")
        ) as mock_open:
            total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
                log_dir
            )

        expected_total_energy = 0
        expected_total_co2eq = 0
        expected_total_equivalents = {}

        self.assertEqual(total_energy, expected_total_energy)
        self.assertEqual(total_co2eq, expected_total_co2eq)
        self.assertEqual(total_equivalents, expected_total_equivalents)

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    def test_aggregate_consumption_actual(self, mock_isfile, mock_listdir, mock_open):
        log_dir = "/path/to/logs"

        output_log_content = (
            "2022-11-14 15:44:48 - CarbonTracker: Actual consumption for 1 epoch(s):\n"
            "	Time:	0:02:22\n"
            "	Energy:	0.009417 kWh\n"
            "	CO2eq:	0.960490 g\n"
            "	This is equivalent to:\n"
            "	0.007977 km travelled by car\n"
        )

        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents=output_log_content,
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents="std_log1 content",
        )

        mock_listdir.return_value = [
            "10151_2024-03-26T105926Z_carbontracker_output.log",
            "10151_2024-03-26T105926Z_carbontracker.log",
        ]
        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_open.return_value.read.return_value = output_log_content

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        self.assertEqual(total_energy, 0.009417)
        self.assertEqual(total_co2eq, 0.96049)
        self.assertEqual(total_equivalents, {"km travelled by car": 0.007977})

    @mock.patch("carbontracker.parser.get_all_logs")
    @mock.patch("carbontracker.parser.get_consumption")
    @mock.patch("carbontracker.parser.get_early_stop")
    def test_aggregate_consumption_both_none(
        self, mock_get_early_stop, mock_get_consumption, mock_get_all_logs
    ):
        log_dir = "/path/to/logs"
        output_log_path = "/path/to/logs/output_log1"
        std_log_path = "/path/to/logs/std_log1"

        self.fs.create_file(output_log_path, contents="output_log_content")
        self.fs.create_file(std_log_path, contents="std_log_content")

        mock_get_all_logs.return_value = ([output_log_path], [std_log_path])
        mock_get_consumption.return_value = (None, None)
        mock_get_early_stop.return_value = False

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        expected_total_energy = 0
        expected_total_co2eq = 0
        expected_total_equivalents = {}

        self.assertEqual(total_energy, expected_total_energy)
        self.assertEqual(total_co2eq, expected_total_co2eq)
        self.assertEqual(total_equivalents, expected_total_equivalents)

    @mock.patch("carbontracker.parser.get_all_logs")
    @mock.patch("carbontracker.parser.get_consumption")
    @mock.patch("carbontracker.parser.get_early_stop")
    def test_aggregate_consumption_actual_none(
        self, mock_get_early_stop, mock_get_consumption, mock_get_all_logs
    ):
        log_dir = "/path/to/logs"
        output_log_path = "/path/to/logs/output_log1"
        std_log_path = "/path/to/logs/std_log1"

        self.fs.create_file(output_log_path, contents="output_log_content")
        self.fs.create_file(std_log_path, contents="std_log_content")

        mock_get_all_logs.return_value = ([output_log_path], [std_log_path])
        mock_get_consumption.return_value = (
            None,
            {"energy (kWh)": 1, "co2eq (g)": 2, "equivalents": {"km": 3}},
        )
        mock_get_early_stop.return_value = False

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        expected_total_energy = 1
        expected_total_co2eq = 2
        expected_total_equivalents = {"km": 3}

        self.assertEqual(total_energy, expected_total_energy)
        self.assertEqual(total_co2eq, expected_total_co2eq)
        self.assertEqual(total_equivalents, expected_total_equivalents)

    @mock.patch("carbontracker.parser.get_all_logs")
    @mock.patch("carbontracker.parser.get_consumption")
    @mock.patch("carbontracker.parser.get_early_stop")
    def test_aggregate_consumption_pred_none(
        self, mock_get_early_stop, mock_get_consumption, mock_get_all_logs
    ):
        log_dir = "/path/to/logs"
        output_log_path = "/path/to/logs/output_log1"
        std_log_path = "/path/to/logs/std_log1"

        self.fs.create_file(output_log_path, contents="output_log_content")
        self.fs.create_file(std_log_path, contents="std_log_content")

        mock_get_all_logs.return_value = ([output_log_path], [std_log_path])
        mock_get_consumption.return_value = (
            {"energy (kWh)": 1, "co2eq (g)": 2, "equivalents": {"km": 3}},
            None,
        )
        mock_get_early_stop.return_value = False

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        expected_total_energy = 1
        expected_total_co2eq = 2
        expected_total_equivalents = {"km": 3}

        self.assertEqual(total_energy, expected_total_energy)
        self.assertEqual(total_co2eq, expected_total_co2eq)
        self.assertEqual(total_equivalents, expected_total_equivalents)

    @mock.patch("carbontracker.parser.get_all_logs")
    @mock.patch("carbontracker.parser.get_consumption")
    @mock.patch("carbontracker.parser.get_early_stop")
    def test_aggregate_consumption_both_available(
        self, mock_get_early_stop, mock_get_consumption, mock_get_all_logs
    ):
        log_dir = "/path/to/logs"
        output_log_path = "/path/to/logs/output_log1"
        std_log_path = "/path/to/logs/std_log1"

        output_log_content = (
            "2022-11-14 15:42:43 - CarbonTracker: The following components were found: GPU with device(s) NVIDIA GeForce RTX 3060. CPU with device(s) cpu:0.\n"
            "2022-11-14 15:43:37 - CarbonTracker: \n"
            "Actual consumption for 1 epoch(s):\n"
            "    Time:    0:00:53\n"
            "    Energy:    0.003504 kWh\n"
            "    CO2eq:    0.357451 g\n"
            "    This is equivalent to:\n"
            "    0.002969 km travelled by car\n"
            "2022-11-14 15:43:37 - CarbonTracker: \n"
            "Predicted consumption for 4 epoch(s):\n"
            "    Time:    0:03:33\n"
            "    Energy:    0.014018 kWh\n"
            "    CO2eq:    1.429803 g\n"
            "    This is equivalent to:\n"
            "    0.011875 km travelled by car\n"
            "2022-11-14 15:43:37 - CarbonTracker: Finished monitoring."
        )
        std_log_content = "std_log_content"

        self.fs.create_file(output_log_path, contents=output_log_content)
        self.fs.create_file(std_log_path, contents=std_log_content)

        mock_get_all_logs.return_value = ([output_log_path], [std_log_path])
        mock_get_consumption.return_value = (
            {
                "epochs": 1,
                "duration (s)": 53,
                "energy (kWh)": None,
                "co2eq (g)": None,
                "equivalents": None,
            },
            {
                "epochs": 4,
                "duration (s)": 213,
                "energy (kWh)": 0.014018,
                "co2eq (g)": 1.429803,
                "equivalents": {"km travelled by car": 0.011875},
            },
        )
        mock_get_early_stop.return_value = False

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        expected_total_energy = 0.014018
        expected_total_co2eq = 1.429803
        expected_total_equivalents = {"km travelled by car": 0.011875}

        self.assertEqual(total_energy, expected_total_energy)
        self.assertEqual(total_co2eq, expected_total_co2eq)
        self.assertEqual(total_equivalents, expected_total_equivalents)

    @mock.patch("carbontracker.parser.get_all_logs")
    @mock.patch("carbontracker.parser.get_consumption")
    @mock.patch("carbontracker.parser.get_early_stop")
    def test_aggregate_consumption_multiple_files(
        self, mock_get_early_stop, mock_get_consumption, mock_get_all_logs
    ):
        log_dir = "/path/to/logs"
        output_log_path1 = "/path/to/logs/output_log1"
        std_log_path1 = "/path/to/logs/std_log1"
        output_log_path2 = "/path/to/logs/output_log2"
        std_log_path2 = "/path/to/logs/std_log2"

        output_log_content1 = (
            "2022-11-14 15:42:43 - CarbonTracker: The following components were found: GPU with device(s) NVIDIA GeForce RTX 3060. CPU with device(s) cpu:0.\n"
            "2022-11-14 15:43:37 - CarbonTracker: \n"
            "Actual consumption for 1 epoch(s):\n"
            "    Time:    0:00:53\n"
            "    Energy:    0.003504 kWh\n"
            "    CO2eq:    0.357451 g\n"
            "    This is equivalent to:\n"
            "    0.002969 km travelled by car\n"
        )
        std_log_content1 = "std_log_content1"

        output_log_content2 = (
            "2022-11-14 15:44:48 - CarbonTracker: \n"
            "Actual consumption for 2 epoch(s):\n"
            "    Time:    0:01:45\n"
            "    Energy:    0.007008 kWh\n"
            "    CO2eq:    0.714902 g\n"
            "    This is equivalent to:\n"
            "    0.005937 km travelled by car\n"
        )
        std_log_content2 = "std_log_content2"

        self.fs.create_file(output_log_path1, contents=output_log_content1)
        self.fs.create_file(std_log_path1, contents=std_log_content1)
        self.fs.create_file(output_log_path2, contents=output_log_content2)
        self.fs.create_file(std_log_path2, contents=std_log_content2)

        mock_get_all_logs.return_value = (
            [output_log_path1, output_log_path2],
            [std_log_path1, std_log_path2],
        )
        mock_get_consumption.side_effect = [
            (
                {
                    "epochs": 1,
                    "duration (s)": 53,
                    "energy (kWh)": 0.003504,
                    "co2eq (g)": 0.357451,
                    "equivalents": {"km travelled by car": 0.002969},
                },
                None,
            ),
            (
                {
                    "epochs": 2,
                    "duration (s)": 105,
                    "energy (kWh)": 0.007008,
                    "co2eq (g)": 0.714902,
                    "equivalents": {"km travelled by car": 0.005937},
                },
                None,
            ),
        ]
        mock_get_early_stop.return_value = False

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        expected_total_energy = 0.010512  # Sum of energy from both logs
        expected_total_co2eq = 1.072353
        expected_total_equivalents = {"km travelled by car": 0.008906}

        self.assertAlmostEqual(total_energy, expected_total_energy, places=6)
        self.assertAlmostEqual(total_co2eq, expected_total_co2eq, places=6)
        self.assertAlmostEqual(
            total_equivalents["km travelled by car"],
            expected_total_equivalents["km travelled by car"],
            places=6,
        )

    @mock.patch("carbontracker.parser.get_all_logs")
    @mock.patch("carbontracker.parser.get_consumption")
    @mock.patch("carbontracker.parser.get_early_stop")
    def test_aggregate_consumption_early_stop(
        self, mock_get_early_stop, mock_get_consumption, mock_get_all_logs
    ):
        log_dir = "/path/to/logs"
        output_log_path = "/path/to/logs/output_log1"
        std_log_path = "/path/to/logs/std_log1"

        output_log_content = (
            "2022-11-14 15:43:37 - CarbonTracker: \n"
            "Actual consumption for 1 epoch(s):\n"
            "    Time:    0:00:53\n"
            "    Energy:    0.003504 kWh\n"
            "    CO2eq:    0.357451 g\n"
            "    This is equivalent to:\n"
            "    0.002969 km travelled by car\n"
            "2022-11-14 15:43:37 - CarbonTracker: \n"
            "Predicted consumption for 1 epoch(s):\n"
            "    Time:    0:00:53\n"
            "    Energy:    0.003000 kWh\n"
            "    CO2eq:    0.305000 g\n"
            "    This is equivalent to:\n"
            "    0.002500 km travelled by car\n"
        )
        std_log_content = "std_log_content"

        self.fs.create_file(output_log_path, contents=output_log_content)
        self.fs.create_file(std_log_path, contents=std_log_content)

        mock_get_all_logs.return_value = ([output_log_path], [std_log_path])
        mock_get_consumption.return_value = (
            {
                "epochs": 1,
                "duration (s)": 53,
                "energy (kWh)": 0.003504,
                "co2eq (g)": 0.357451,
                "equivalents": {"km travelled by car": 0.002969},
            },
            {
                "epochs": 1,
                "duration (s)": 53,
                "energy (kWh)": 0.003000,
                "co2eq (g)": 0.305000,
                "equivalents": {"km travelled by car": 0.002500},
            },
        )
        mock_get_early_stop.return_value = True

        total_energy, total_co2eq, total_equivalents = parser.aggregate_consumption(
            log_dir
        )

        expected_total_energy = 0.003504  # Energy from actual
        expected_total_co2eq = 0.357451
        expected_total_equivalents = {"km travelled by car": 0.002969}

        self.assertAlmostEqual(total_energy, expected_total_energy, places=6)
        self.assertAlmostEqual(total_co2eq, expected_total_co2eq, places=6)
        self.assertAlmostEqual(
            total_equivalents["km travelled by car"],
            expected_total_equivalents["km travelled by car"],
            places=6,
        )

    def test_get_time_no_match(self):
        time_str = "Invalid time string"
        result = parser.get_time(time_str)
        assert result is None

    @mock.patch("builtins.print")
    @mock.patch(
        "carbontracker.parser.aggregate_consumption", return_value=(100.0, 50000.0, {})
    )
    def test_print_aggregate_empty_equivalents(
        self, mock_aggregate_consumption, mock_print
    ):
        log_dir = "/logs"
        print_aggregate(log_dir)
        mock_print.assert_called_once_with(
            "The training of models in this work is estimated to use 100.0000000000000000 kWh of electricity contributing to 50.0000000000000000 kg of CO2eq. Measured by carbontracker (https://github.com/lfwa/carbontracker)."
        )

    @mock.patch("builtins.print")
    @mock.patch(
        "carbontracker.parser.aggregate_consumption",
        return_value=(100.0, 5000.0, {"km travelled": 200.0}),
    )
    def test_print_aggregate_non_empty_equivalents(
        self, mock_aggregate_consumption, mock_print
    ):
        log_dir = "/logs"
        print_aggregate(log_dir)
        mock_print.assert_called_once_with(
            "The training of models in this work is estimated to use 100.0000000000000000 kWh of electricity contributing to 5.0000000000000000 kg of CO2eq. "
            "This is equivalent to 200.0000000000000000 km travelled. "
            "Measured by carbontracker (https://github.com/lfwa/carbontracker)."
        )

    def test_get_stats_no_equivalents(self):
        groups = ["group1", "group2", "10.5", "20.5"]
        energy, co2eq, equivalents = get_stats(groups)
        self.assertEqual(energy, 10.5)
        self.assertEqual(co2eq, 20.5)
        self.assertIsNone(equivalents)

    def test_parse_equivalents_value_error(self):
        lines = "not_a_float equivalent1\n10.5 equivalent2"
        equivalents = parse_equivalents(lines)
        self.assertEqual({"equivalent2": 10.5}, equivalents)

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("os.listdir")
    @mock.patch("os.path.isfile")
    @mock.patch("carbontracker.parser.get_devices")
    def test_parse_epoch_mismatch(
        self, mock_get_devices, mock_isfile, mock_listdir, mock_open
    ):
        log_dir = "/path/to/logs"

        std_log_data = (
            "2022-11-14 15:44:48 - Average power usage (W) for gpu: [136.86084615]\n"
            "2022-11-14 15:44:48 - Average power usage (W) for cpu: [13.389104]\n"
            "2022-11-14 15:44:48 - Average power usage (W) for gpu: [136.86084615]\n"
            "2022-11-14 15:44:48 - Average power usage (W) for cpu: [13.389104]\n"
            "2022-11-14 15:44:48 - Epoch 1:\nDuration: 0:02:21.90"
        )

        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"),
            contents="output_log1 content",
        )
        self.fs.create_file(
            os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
            contents=std_log_data,
        )

        mock_isfile.side_effect = lambda path: path.endswith(".log")
        mock_open.return_value.read.return_value = std_log_data
        mock_get_devices.return_value = {
            "gpu": ["NVIDIA GeForce RTX 3060"],
            "cpu": ["cpu:0"],
        }

        with self.assertRaises(exceptions.MismatchedEpochsError):
            components = parser.parse_logs(
                log_dir,
                os.path.join(log_dir, "10151_2024-03-26T105926Z_carbontracker.log"),
                os.path.join(
                    log_dir, "10151_2024-03-26T105926Z_carbontracker_output.log"
                ),
            )

    def test_parse_logs_mismatch(self):
        results = parser.get_avg_power_usages("2024-03-26 10:51:53 - Epoch 1:\n2024-03-26 10:51:53 - Duration: 0:00:00.00\n2024-03-26 10:51:53 - Average power usage (W) for cpu: None\n2024-03-26 10:51:53 - Average power usage (W) for gpu: None")
        self.assertEqual(results, {"cpu": [[0.0]], "gpu": [[0.0]]})