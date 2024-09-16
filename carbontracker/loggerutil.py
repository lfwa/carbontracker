import logging
from logging import LogRecord
import os
import sys
import pathlib
import datetime
import importlib_metadata as metadata
from carbontracker import constants
from typing import Union


def convert_to_timestring(seconds: int, add_milliseconds=False) -> str:
    negative = False
    if seconds < 0:
        negative = True
        seconds = abs(seconds)

    m, s = divmod(seconds, 60)
    if not add_milliseconds:
        s = int(round(s))
        if s == 60:
            m += 1
            s = 0
    else:
        if f"{s:05.2f}"[0:2] == "60":
            m += 1
            s = 0
    h, m = divmod(m, 60)
    h = int(h)
    m = int(m)
    if not add_milliseconds:
        return f"-{h:d}:{m:02d}:{s:02d}" if negative else f"{h:d}:{m:02d}:{s:02d}"
    else:
        return f"-{h:d}:{m:02d}:{s:05.2f}" if negative else f"{h:d}:{m:02d}:{s:05.2f}"


class TrackerFormatter(logging.Formatter):
    converter = datetime.datetime.fromtimestamp

    def formatTime(self, record: LogRecord, datefmt: Union[str, None] = None) -> str:
        if record.created:
            ct = self.converter(record.created)
            if datefmt:
                s = ct.strftime(datefmt)
            else:
                t = ct.strftime("%Y-%m-%d %H:%M:%S")
                s = "%s" % t
            return s


class VerboseFilter(logging.Filter):
    def __init__(self, verbose):
        super().__init__()
        self.verbose = verbose

    def filter(self, record):
        return self.verbose > 0


class Logger:
    def __init__(self, log_dir=None, verbose=0, log_prefix="", logger_id="root"):
        self.verbose = verbose
        self.logger, self.logger_output, self.logger_err = self._setup(
            log_dir=log_dir, log_prefix=log_prefix, logger_id=logger_id
        )
        self._log_initial_info()
        self.msg_prepend = "CarbonTracker: "

    def _setup(self, log_dir=None, log_prefix="", logger_id="root"):
        if log_prefix:
            log_prefix += "_"

        logger_name = f"{log_prefix}{os.getpid()}.{logger_id}"
        logger = logging.getLogger(logger_name)

        logger_err = logging.getLogger(f"carbontracker.{logger_id}.err")
        logger_output = logging.getLogger(f"carbontracker.{logger_id}.output")
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        logger_output.propagate = False
        logger_output.setLevel(logging.DEBUG)
        logger_err.propagate = False
        logger_err.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(stream=sys.stdout)
        c_formatter = logging.Formatter("{message}", style="{")
        ch.setLevel(logging.INFO)
        ch.setFormatter(c_formatter)
        ch.addFilter(VerboseFilter(self.verbose))
        logger_output.addHandler(ch)

        # Add error logging to console.
        ce = logging.StreamHandler(stream=sys.stdout)
        ce_formatter = logging.Formatter(
            "CarbonTracker: {levelname} - {message}", style="{"
        )
        ce.setLevel(logging.INFO)
        ce.setFormatter(ce_formatter)
        logger_err.addHandler(ce)

        if log_dir is not None:
            # Create logging directory if it does not exist.
            pathlib.Path(log_dir).mkdir(parents=True, exist_ok=True)

            # Modified ISO8601 format YYYY-MM-DDThhmmssZ.
            # : does not work in file naming on Windows.
            date_format = "%Y-%m-%dT%H%M%SZ"
            date = datetime.datetime.now().strftime(date_format)

            f_formatter = TrackerFormatter(fmt="%(asctime)s - %(message)s")

            # Add output logging to file.
            fh = logging.FileHandler(
                f"{log_dir}/{logger_name}_{date}_carbontracker_output.log"
            )
            fh.setLevel(logging.INFO)
            fh.setFormatter(f_formatter)
            logger_output.addHandler(fh)

            # Add standard logging to file.
            f = logging.FileHandler(f"{log_dir}/{logger_name}_{date}_carbontracker.log")
            f.setLevel(logging.DEBUG)
            f.setFormatter(f_formatter)
            logger.addHandler(f)

            # Add error logging to file.
            err_formatter = logging.Formatter(
                "{asctime} - {threadName} - {levelname} - {message}", style="{"
            )
            f_err = logging.FileHandler(
                f"{log_dir}/{logger_name}_{date}_carbontracker_err.log", delay=True
            )
            f_err.setLevel(logging.DEBUG)
            f_err.setFormatter(err_formatter)
            logger_err.addHandler(f_err)

        return logger, logger_output, logger_err

    def _log_initial_info(self):
        self.info(f"{__package__} version {metadata.version(__package__)}")
        self.info(
            "Only predicted and actual consumptions are multiplied by a PUE "
            f"coefficient of {constants.PUE_2023} (Daniel Bizo, 2023, Uptime "
            "Institute Global Data Center Survey)."
        )

    def output(self, msg, verbose_level=0):
        self.logger_output.info(self.msg_prepend + msg)

    def info(self, msg):
        self.logger.info(msg)

    def err_debug(self, msg):
        self.logger_err.debug(msg)

    def err_info(self, msg):
        self.logger_err.info(msg)

    def err_warn(self, msg):
        self.logger_err.warning(msg)

    def err_critical(self, msg):
        self.logger_err.critical(msg)
