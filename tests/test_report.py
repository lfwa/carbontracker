
import os
import tempfile
import time
import unittest
import shutil

from carbontracker.tracker import CarbonTracker
from carbontracker.report import LogParser, format_duration


class TestFormatDuration(unittest.TestCase):
    """Tests for the format_duration helper function."""

    def test_format_duration_seconds_only(self):
        self.assertEqual(format_duration(30), "30s")

    def test_format_duration_minutes_and_seconds(self):
        self.assertEqual(format_duration(90), "1min 30s")

    def test_format_duration_hours_minutes_seconds(self):
        self.assertEqual(format_duration(3661), "1h 1min 1s")

    def test_format_duration_hours_only(self):
        self.assertEqual(format_duration(3600), "1h")

    def test_format_duration_zero(self):
        self.assertEqual(format_duration(0), "0s")


class TestLogParser(unittest.TestCase):
    """
    Tests for the LogParser class using dynamically generated logs.
    
    This test class generates real logs from CarbonTracker using simulation mode,
    ensuring the LogParser is always tested against the current log format.
    """

    @classmethod
    def setUpClass(cls):
        """Generate a log file using CarbonTracker's simulation mode."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.log_prefix = "test_report_parser"
        
        # Known simulation parameters - we use these to verify parsing
        cls.sim_cpu_name = "TestCPU"
        cls.sim_cpu_tdp = 50  # 50W TDP for CPU
        cls.sim_gpu_name = "TestGPU"
        cls.sim_gpu_watts = 100  # 100W for GPU
        cls.num_epochs = 3
        cls.epoch_duration = 0.3  # seconds of simulated work per epoch

        # Use simulation mode to generate deterministic logs
        tracker = CarbonTracker(
            epochs=cls.num_epochs,
            epochs_before_pred=-1,  # Skip prediction
            monitor_epochs=-1,  # Monitor all epochs
            update_interval=0.1,
            log_dir=cls.temp_dir,
            log_file_prefix=cls.log_prefix,
            verbose=0,  # Suppress output
            sim_cpu=cls.sim_cpu_name,
            sim_cpu_tdp=cls.sim_cpu_tdp,
            sim_gpu=cls.sim_gpu_name,
            sim_gpu_watts=cls.sim_gpu_watts,
        )

        # Run a simulated tracking session
        for epoch in range(cls.num_epochs):
            tracker.epoch_start()
            time.sleep(cls.epoch_duration)  # Simulate some work
            tracker.epoch_end()

        tracker.stop()

        # Find the generated log file (the standard log, not output log)
        cls.std_log_path = None
        for filename in os.listdir(cls.temp_dir):
            if (filename.startswith(cls.log_prefix) and 
                not filename.endswith("_output.log") and 
                not filename.endswith("_err.log") and 
                filename.endswith(".log")):
                cls.std_log_path = os.path.join(cls.temp_dir, filename)
                break

        if cls.std_log_path is None:
            raise RuntimeError(f"No standard log file found in {cls.temp_dir}")

        # Read the generated log content
        with open(cls.std_log_path, 'r') as f:
            cls.log_content = f.read()
        
        # Parse immediately to verify log content is valid
        cls.parser = LogParser(cls.log_content)

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary log files."""
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_parser_parses_version(self):
        """Test that LogParser correctly extracts the carbontracker version."""
        self.assertIsNotNone(self.parser.version)
        # Version should be a string like "X.Y.Z" or a dev version
        self.assertIsInstance(self.parser.version, str)
        # Version string should contain digits
        self.assertTrue(any(c.isdigit() for c in self.parser.version))

    def test_parser_parses_pue(self):
        """Test that LogParser correctly extracts the PUE coefficient."""
        self.assertIsNotNone(self.parser.pue)
        # PUE should be a positive float > 1.0 (industry standard)
        self.assertGreater(self.parser.pue, 1.0)
        self.assertLess(self.parser.pue, 3.0)  # Reasonable upper bound

    def test_parser_parses_components(self):
        """Test that LogParser correctly extracts component information."""
        self.assertIsNotNone(self.parser.components)
        # Should contain GPU and CPU references (simulated devices)
        self.assertIn("GPU", self.parser.components)
        self.assertIn("CPU", self.parser.components)
        # Should contain our simulated device names
        self.assertIn(self.sim_gpu_name, self.parser.components)
        self.assertIn(self.sim_cpu_name, self.parser.components)

    def test_parser_parses_correct_number_of_epochs(self):
        """Test that LogParser extracts the correct number of epochs."""
        self.assertEqual(len(self.parser.epochs), self.num_epochs)

    def test_parser_epochs_have_required_fields(self):
        """Test that each epoch has all required fields."""
        for i, epoch in enumerate(self.parser.epochs):
            with self.subTest(epoch=i + 1):
                self.assertIn('epoch', epoch)
                self.assertIn('duration', epoch)
                self.assertIn('gpu_power', epoch)
                self.assertIn('cpu_power', epoch)
                self.assertIn('total_power', epoch)

    def test_parser_epoch_numbers_sequential(self):
        """Test that epoch numbers are sequential starting from 1."""
        for i, epoch in enumerate(self.parser.epochs):
            self.assertEqual(epoch['epoch'], i + 1)

    def test_parser_epoch_durations_positive(self):
        """Test that epoch durations are positive and reasonable."""
        for epoch in self.parser.epochs:
            self.assertGreaterEqual(epoch['duration'], 0)
            # Duration should be less than 60 seconds for our test
            self.assertLess(epoch['duration'], 60)

    def test_parser_power_values_match_simulation(self):
        """Test that power values approximately match our simulation parameters."""
        for epoch in self.parser.epochs:
            # GPU power should be approximately sim_gpu_watts * 0.5 (50% utilization default)
            expected_gpu_power = self.sim_gpu_watts * 0.5
            self.assertAlmostEqual(epoch['gpu_power'], expected_gpu_power, delta=expected_gpu_power * 0.2)
            
            # CPU power should be approximately sim_cpu_tdp * 0.5 (50% utilization default)
            expected_cpu_power = self.sim_cpu_tdp * 0.5
            self.assertAlmostEqual(epoch['cpu_power'], expected_cpu_power, delta=expected_cpu_power * 0.2)

    def test_parser_total_power_is_sum(self):
        """Test that total_power equals gpu_power + cpu_power."""
        for epoch in self.parser.epochs:
            expected_total = epoch['gpu_power'] + epoch['cpu_power']
            self.assertAlmostEqual(epoch['total_power'], expected_total, places=5)

    def test_parser_parses_timestamps(self):
        """Test that LogParser correctly extracts timestamps."""
        self.assertIsNotNone(self.parser.start_time)
        self.assertIsNotNone(self.parser.end_time)
        # Timestamps should be in expected format (YYYY-MM-DD HH:MM:SS)
        self.assertRegex(self.parser.start_time, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
        self.assertRegex(self.parser.end_time, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

    def test_calculate_energy_metrics_structure(self):
        """Test that calculate_energy_metrics returns expected structure."""
        # Ensure carbon_intensity is set for energy metrics calculation
        if self.parser.carbon_intensity is None:
            self.parser.carbon_intensity = 150.0  # Mock value in gCO2eq/kWh

        metrics = self.parser.calculate_energy_metrics()

        # Check all expected keys are present
        expected_keys = ['total_duration', 'avg_gpu_power', 'avg_cpu_power', 
                         'total_power', 'energy_kwh', 'co2_kg']
        for key in expected_keys:
            self.assertIn(key, metrics)

    def test_calculate_energy_metrics_values_non_negative(self):
        """Test that all energy metrics are non-negative."""
        # Ensure carbon_intensity is set for energy metrics calculation
        if self.parser.carbon_intensity is None:
            self.parser.carbon_intensity = 150.0  # Mock value in gCO2eq/kWh

        metrics = self.parser.calculate_energy_metrics()

        self.assertGreaterEqual(metrics['total_duration'], 0)
        self.assertGreaterEqual(metrics['avg_gpu_power'], 0)
        self.assertGreaterEqual(metrics['avg_cpu_power'], 0)
        self.assertGreaterEqual(metrics['total_power'], 0)
        self.assertGreaterEqual(metrics['energy_kwh'], 0)
        self.assertGreaterEqual(metrics['co2_kg'], 0)

    def test_calculate_energy_metrics_duration_matches_epochs(self):
        """Test that total_duration matches sum of epoch durations."""
        # Ensure carbon_intensity is set for energy metrics calculation
        if self.parser.carbon_intensity is None:
            self.parser.carbon_intensity = 150.0  # Mock value in gCO2eq/kWh

        metrics = self.parser.calculate_energy_metrics()
        expected_duration = sum(epoch['duration'] for epoch in self.parser.epochs)
        self.assertAlmostEqual(metrics['total_duration'], expected_duration, places=5)

    def test_generate_plots_returns_buffer(self):
        """Test that generate_plots returns a readable buffer."""
        # Ensure carbon_intensity is set for CO2 calculations in plots
        if self.parser.carbon_intensity is None:
            self.parser.carbon_intensity = 150.0  # Mock value in gCO2eq/kWh

        plots = self.parser.generate_plots()

        self.assertIn('combined_plots', plots)
        # The plot should be a BytesIO buffer with read capability
        self.assertTrue(hasattr(plots['combined_plots'], 'read'))
        # Buffer should contain data (PNG header starts with specific bytes)
        data = plots['combined_plots'].read()
        self.assertGreater(len(data), 0)
        # PNG files start with specific bytes: \x89PNG
        self.assertTrue(data.startswith(b'\x89PNG'))


class TestLogParserDurationParsing(unittest.TestCase):
    """Tests for LogParser's _parse_duration method."""

    def setUp(self):
        """Create a LogParser instance for testing the duration parser."""
        self.parser = LogParser("")

    def test_parse_duration_hours_minutes_seconds(self):
        """Test parsing HH:MM:SS format."""
        self.assertEqual(self.parser._parse_duration("1:30:15"), 5415.0)

    def test_parse_duration_minutes_seconds(self):
        """Test parsing MM:SS format."""
        self.assertEqual(self.parser._parse_duration("5:30"), 330.0)

    def test_parse_duration_seconds_with_decimals(self):
        """Test parsing HH:MM:SS.ss format with decimals."""
        self.assertEqual(self.parser._parse_duration("0:00:01.50"), 1.5)

    def test_parse_duration_zero(self):
        """Test parsing zero duration."""
        self.assertEqual(self.parser._parse_duration("0:00:00.00"), 0.0)

    def test_parse_duration_large_hours(self):
        """Test parsing large hour values."""
        # 10 hours, 30 minutes, 45 seconds = 37845 seconds
        self.assertEqual(self.parser._parse_duration("10:30:45"), 37845.0)


class TestReportOptionalDependency(unittest.TestCase):
    """Tests for the optional reportlab dependency."""

    def test_generate_report_raises_import_error_without_reportlab(self):
        """Test that generate_report_from_log raises ImportError when reportlab is not installed."""
        import carbontracker.report as report_module
        from carbontracker.report import generate_report_from_log

        # Save original value
        original_value = report_module.REPORTLAB_AVAILABLE

        try:
            # Mock reportlab as not available
            report_module.REPORTLAB_AVAILABLE = False

            with self.assertRaises(ImportError) as context:
                generate_report_from_log("dummy_log.txt", "dummy_output.pdf")

            # Check the error message contains installation instructions
            self.assertIn("pip install 'carbontracker[pdfreport]'", str(context.exception))
            self.assertIn("reportlab", str(context.exception))
        finally:
            # Restore original value
            report_module.REPORTLAB_AVAILABLE = original_value


if __name__ == "__main__":
    unittest.main()
