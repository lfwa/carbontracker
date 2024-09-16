import unittest
from unittest import skipIf
from carbontracker import loggerutil
from carbontracker.loggerutil import Logger, convert_to_timestring
import unittest.mock
from unittest.mock import MagicMock, patch
import tempfile
import os
import logging
from datetime import datetime
import time


class TestLoggerUtil(unittest.TestCase):
    def test_convert_to_timestring_positive_value(self):
        time_s = 3666
        self.assertEqual(convert_to_timestring(time_s), "1:01:06")

    def test_convert_to_timestring_zero_value(self):
        time_s = 0
        self.assertEqual(convert_to_timestring(time_s), "0:00:00")

    def test_convert_to_timestring_floating_value(self):
        time_s = 3666.4
        self.assertEqual(convert_to_timestring(time_s), "1:01:06")

    def test_convert_to_timestring_negative_value(self):
        time_s = -3666
        self.assertEqual(convert_to_timestring(time_s), "-1:01:06")

    def test_convert_to_timestring_rounding_seconds(self):
        time_s = 3659.5  # This will round to 3660, which is 1 hour and 60 seconds
        self.assertEqual(convert_to_timestring(time_s), "1:01:00")

    def test_convert_to_timestring_rounding_float_seconds(self):
        time_s = 3659.9955  # Very close to 3660, and should round off to it
        self.assertEqual(
            convert_to_timestring(time_s, add_milliseconds=True), "1:01:00.00"
        )

    @skipIf(os.environ.get("CI") == "true", "Skipped due to CI")
    def test_formatTime_with_datefmt(self):
        formatter = loggerutil.TrackerFormatter()
        record = MagicMock()
        record.created = time.mktime(
            datetime(2023, 3, 15, 14, 20, 0).timetuple()
        )  # This is a sample timestamp for "2023-03-15 14:20:00" at UTC time

        # Specify a custom date format
        datefmt = "%Y-%m-%d %H-%M-%S"
        formatted_time = formatter.formatTime(record, datefmt)

        self.assertEqual(formatted_time, "2023-03-15 14-20-00")

    @skipIf(os.environ.get("CI") == "true", "Skipped due to CI")
    def test_formatTime_without_datefmt(self):
        formatter = loggerutil.TrackerFormatter()
        record = MagicMock()
        record.created = time.mktime(datetime(2023, 3, 15, 14, 20, 0).timetuple())

        formatted_time = formatter.formatTime(record)

        self.assertEqual(formatted_time, "2023-03-15 14:20:00")

    def test_logger_with_log_prefix(self):
        log_prefix_original = "test_prefix"
        logger = loggerutil.Logger(log_prefix=log_prefix_original)

        # Check if the logger's name starts with the updated log_prefix
        self.assertTrue(logger.logger.name.startswith(f"{log_prefix_original}_"))

    def test_logger_without_log_prefix(self):
        logger = loggerutil.Logger(log_prefix="")

        # Check if the logger's name does not contain any underscores (indicating no prefix was added)
        self.assertFalse("_" in logger.logger.name)

    def test_VerboseFilter_with_verbose(self):
        verbose_filter = loggerutil.VerboseFilter(verbose=1)
        record = MagicMock()

        # The filter should return True since verbose is set to 1
        self.assertTrue(verbose_filter.filter(record))

    def test_VerboseFilter_without_verbose(self):
        verbose_filter = loggerutil.VerboseFilter(verbose=0)
        record = MagicMock()

        # The filter should return False since verbose is set to 0
        self.assertFalse(verbose_filter.filter(record))

    def test_logger_setup(self):
        logger = Logger()
        self.assertIsInstance(logger, Logger)
        self.assertEqual(
            logger.logger_output.level, logging.DEBUG, "Logging level is not DEBUG."
        )

    def test_info_logging(self):
        logger = Logger()
        with unittest.mock.patch.object(logger.logger, "info") as mock_info:
            msg = "Test Info Message"
            logger.info(msg)
            mock_info.assert_called_once_with(msg)

    def test_err_debug_logging(self):
        logger = Logger()
        with unittest.mock.patch.object(logger.logger_err, "debug") as mock_debug:
            msg = "Test Debug Error Message"
            logger.err_debug(msg)
            mock_debug.assert_called_once_with(msg)

    def test_err_info_logging(self):
        logger = Logger()
        with unittest.mock.patch.object(logger.logger_err, "info") as mock_info:
            msg = "Test Info Error Message"
            logger.err_info(msg)
            mock_info.assert_called_once_with(msg)

    def test_err_warn_logging(self):
        logger = Logger()
        with unittest.mock.patch.object(logger.logger_err, "warning") as mock_warn:
            msg = "Test Warn Error Message"
            logger.err_warn(msg)
            mock_warn.assert_called_once_with(msg)

    def test_err_critical_logging(self):
        logger = Logger()
        with unittest.mock.patch.object(logger.logger_err, "critical") as mock_critical:
            msg = "Test Critical Error Message"
            logger.err_critical(msg)
            mock_critical.assert_called_once_with(msg)

    def test_log_initial_info(self):
        logger = Logger()
        with unittest.mock.patch.object(logger.logger, "info") as mock_info:
            logger._log_initial_info()  # Call it again for testing purposes
            self.assertEqual(
                mock_info.call_count, 2
            )  # Called twice: one during initialization and one during our test

    def test_logger_with_log_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = loggerutil.Logger(log_dir=tmp_dir)

            logger.err_info("Trigger error to create the log file")

            self.assertTrue(os.path.exists(tmp_dir))

            files = os.listdir(tmp_dir)
            self.assertTrue(any(["carbontracker_output.log" in file for file in files]))
            self.assertTrue(any(["carbontracker.log" in file for file in files]))
            self.assertTrue(any(["carbontracker_err.log" in file for file in files]))

    @unittest.mock.patch("logging.Logger.info")
    def test_output(self, mock_info):
        logger = loggerutil.Logger()
        test_message = "Test Message"

        # Reset the mock to ignore the initial calls to `info` during Logger initialization
        mock_info.reset_mock()

        logger.output(test_message)

        mock_info.assert_called_once_with(f"CarbonTracker: {test_message}")

    def test_multiple_loggers(self):
        logger1 = loggerutil.Logger(logger_id="1")
        logger2 = loggerutil.Logger(logger_id="2")
        self.assertNotEqual(logger1.logger, logger2.logger)
        self.assertNotEqual(logger1.logger_output, logger2.logger_output)
        self.assertNotEqual(logger1.logger_err, logger2.logger_err)


if __name__ == "__main__":
    unittest.main()
