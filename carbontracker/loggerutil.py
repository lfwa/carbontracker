import logging
import os
import sys
import pathlib
import datetime


def convert_to_timestring(seconds):
    return str(datetime.timedelta(seconds=seconds))


class Logger:
    def __init__(self, log_dir=None, verbose=0):
        self.logger, self.logger_output = self._setup(log_dir=log_dir)
        self._log_initial_info()
        self.verbose = verbose
        self.msg_prepend = "CarbonTracker: "

    def _setup(self, log_dir=None):
        logger = None
        logger_output = logging.getLogger("carbontracker.output")
        # Disable output logging from propagating to parent loggers.
        logger_output.propagate = False
        logger_output.setLevel(logging.DEBUG)

        # Add output logging to console.
        ch = logging.StreamHandler(stream=sys.stdout)
        c_formatter = logging.Formatter("{message}", style="{")
        ch.setLevel(logging.INFO)
        ch.setFormatter(c_formatter)
        logger_output.addHandler(ch)

        if log_dir is not None:
            # Create logging directory if it does not exist.
            pathlib.Path(log_dir).mkdir(parents=True, exist_ok=True)

            # ISO8601 format YYYY-MM-DDThh:mmZ.
            date_format = "%Y-%m-%dT%H:%MZ"
            date = datetime.datetime.now().strftime(date_format)

            logger = logging.getLogger("carbontracker")
            logger.setLevel(logging.DEBUG)
            f_formatter = logging.Formatter(
                "{asctime} - {threadName} - {levelname} - {message}",
                style="{")

            # Add output logging to file.
            fh = logging.FileHandler(
                f"{log_dir}/{date}_carbontracker_output.log")
            fh.setLevel(logging.INFO)
            fh.setFormatter(f_formatter)
            logger_output.addHandler(fh)

            # Add standard logging to file.
            f = logging.FileHandler(f"{log_dir}/{date}_carbontracker.log")
            f.setLevel(logging.DEBUG)
            f.setFormatter(f_formatter)
            logger.addHandler(f)

        return logger, logger_output

    def _log_initial_info(self):
        here = os.path.abspath(os.path.dirname(__file__))
        about = {}
        with open(os.path.join(here, "__version__.py")) as f:
            exec(f.read(), about)
        self.info(f"{about['__title__']} version {about['__version__']}")

    def output(self, msg, verbose_level=0):
        if self.verbose >= verbose_level:
            self.logger_output.info(self.msg_prepend + msg)

    def debug(self, msg):
        if self.logger is None:
            return
        self.logger.debug(msg)

    def info(self, msg):
        if self.logger is None:
            return
        self.logger.info(msg)

    def warn(self, msg):
        if self.logger is None:
            return
        self.logger.warn(msg)

    def critical(self, msg):
        if self.logger is None:
            return
        self.logger.critical(msg)
