import unittest
from unittest.mock import patch, mock_open
from carbontracker.components.cpu.intel import IntelCPU
from carbontracker.components.component import Component
from carbontracker import exceptions
import re

class TestIntelCPU(unittest.TestCase):
    @patch("os.path.exists")
    @patch("os.listdir")
    def test_available(self, mock_listdir, mock_exists):
        mock_exists.return_value = True
        mock_listdir.return_value = ["some_directory"]

        component = Component(name='cpu', pids=[], devices_by_pid={}, logger=None)
        self.assertTrue(component.available())

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open, read_data="some_name")
    def test_devices(self, mock_file, mock_listdir, mock_exists):
        mock_exists.return_value = True
        mock_listdir.side_effect = [["intel-rapl:0", "intel-rapl:1"], ["name"], ["name"]]
        mock_file.return_value.read.side_effect = ["package-0", "package-1"]

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu.init()

        self.assertEqual(cpu.devices(), ["cpu:0", "cpu:1"])

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch.object(Component, "available", return_value=False)
    def test_available_false(self, mock_available, mock_listdir, mock_exists):
        mock_exists.return_value = False
        mock_listdir.return_value = []

        cpu = Component(name='cpu', pids=[], devices_by_pid={}, logger=None)
        self.assertFalse(cpu.available())

    @patch("time.sleep")
    @patch("carbontracker.components.cpu.intel.IntelCPU._get_measurements")
    def test_power_usage_positive(self, mock_get_measurements, mock_sleep):
        mock_get_measurements.side_effect = [[10, 20], [20, 30]]
        mock_sleep.return_value = None

        cpu = IntelCPU(pids=[], devices_by_pid={})
        power_usages = cpu.power_usage()

        self.assertEqual(power_usages, [0.00001, 0.00001])

    @patch("time.sleep")
    @patch("carbontracker.components.cpu.intel.IntelCPU._get_measurements")
    def test_power_usage_negative(self, mock_get_measurements, mock_sleep):
        mock_get_measurements.side_effect = [[30, 20], [20, 30]]
        mock_sleep.return_value = None

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu._devices = ["cpu:0", "cpu:1"]
        power_usages = cpu.power_usage()

        self.assertEqual(power_usages, [0.00, 0.00])


    @patch("builtins.open", new_callable=mock_open, read_data="1000000")
    def test__read_energy(self, mock_file):
        cpu = IntelCPU(pids=[], devices_by_pid={})
        energy = cpu._read_energy("/some/path")
        self.assertEqual(energy, 1000000)

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    def test__get_measurements(self, mock_file, mock_listdir, mock_exists):
        mock_exists.return_value = True
        # Simulate true RAPL zone hierarchy
        mock_listdir.return_value = ["intel-rapl:0", "intel-rapl:0:0", "intel-rapl:0:1", "intel-rapl:0:2","intel-rapl:1"]
        #mock_file.return_value.read.return_value = "1000000"
        mock_file.return_value.read.side_effect = ["package-0", "cores", "uncores", "dram", "psys", "1000000", "99999", "88", "88", "88"]

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu.init()

        measurements = cpu._get_measurements()
        self.assertEqual(measurements, [1000000, 99999])
        self.assertEqual(cpu._rapl_devices, ["intel-rapl:0", "intel-rapl:0:2"]) # Only package and dram zones are considered, the rest are included in package
        self.assertEqual(cpu._devices, ["cpu:0", "dram:0"])

    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open, read_data="cpu")
    def test__convert_rapl_name(self, mock_file, mock_listdir):
        mock_listdir.return_value = ["intel-rapl:0", "intel-rapl:1"]

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu.init()

        self.assertEqual(cpu._convert_rapl_name("intel-rapl:0", "package-0", re.compile(r"intel-rapl:(\d)(:\d)?")), "cpu:0")

    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open, read_data="cpu")
    def test__convert_rapl_name_dram(self, mock_file, mock_listdir):
        mock_listdir.return_value = ["intel-rapl:0", "intel-rapl:1"]

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu.init()

        self.assertEqual(cpu._convert_rapl_name("intel-rapl:1", "dram", re.compile(r"intel-rapl:(\d)(:\d)?")), "dram:1")

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open, read_data="cpu")
    def test_init(self, mock_file, mock_listdir, mock_exists):
        mock_exists.return_value = True
        mock_listdir.return_value = ["intel-rapl:0", "intel-rapl:1"]
        mock_file.return_value.read.side_effect = ["package-0", "package-1"]

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu.init()

        self.assertEqual(cpu.devices(), ["cpu:0", "cpu:1"])

    @patch("os.path.join")
    @patch("os.listdir")
    @patch("carbontracker.components.cpu.intel.IntelCPU._read_energy")
    def test__get_measurements_permission_error(self, mock_read_energy, mock_listdir, mock_path_join):
        mock_path_join.return_value = "/some/path"
        mock_read_energy.side_effect = PermissionError()

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu._rapl_devices = ["device1"]
        with self.assertRaises(exceptions.IntelRaplPermissionError):
            cpu._get_measurements()

    @patch("os.path.join")
    @patch("os.listdir")
    @patch("carbontracker.components.cpu.intel.IntelCPU._read_energy")
    def test__get_measurements_file_not_found(self, mock_read_energy, mock_listdir, mock_path_join):
        mock_path_join.return_value = "/some/path"
        mock_read_energy.side_effect = [FileNotFoundError(), 1000000, 1000000, 1000000]
        mock_listdir.return_value = ["intel-rapl:0", "intel-rapl:1"]

        cpu = IntelCPU(pids=[], devices_by_pid={})
        cpu._rapl_devices = ["intel-rapl:0", "intel-rapl:1"]
        cpu.parts_pattern = re.compile(r"intel-rapl:.")
        measurements = cpu._get_measurements()

        self.assertEqual(measurements, [2000000, 1000000])


    def test_shutdown(self):
        cpu = IntelCPU(pids=[], devices_by_pid={})
        # As the shutdown method is currently a pass, there's nothing to assert here.
        # But we still call it for the sake of completeness and future modifications.
        cpu.shutdown()

if __name__ == "__main__":
    unittest.main()
