import logging
import os
import sys
import pathlib

from datetime import datetime

class Logger:
    def __init__(self, log_dir=None, verbose=0):
        self.logger, self.logger_output = self._setup(log_dir=log_dir)
        self._log_initial_info()
        self.verbose = verbose
    
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
            date = datetime.now().strftime(date_format)

            logger = logging.getLogger("carbontracker")
            logger.setLevel(logging.DEBUG)
            f_formatter = logging.Formatter("{asctime} - {threadName} - {levelname} - {message}", style="{")

            # Add output logging to file.
            fh = logging.FileHandler(f"{log_dir}/carbontracker_output_{date}.log")
            fh.setLevel(logging.INFO)
            fh.setFormatter(f_formatter)
            logger_output.addHandler(fh)

            # Add standard logging to file.
            f = logging.FileHandler(f"{log_dir}/carbontracker_{date}.log")
            f.setLevel(logging.DEBUG)
            f.setFormatter(f_formatter)
            logger.addHandler(f)
        
        return logger, logger_output
    
    def _log_initial_info(self):
        here = os.path.abspath(os.path.dirname(__file__))
        about = {}
        with open(os.path.join(here, "__version__.py")) as f:
            exec(f.read(), about)
        self.logger.info(f"{about['__title__']} version {about['__version__']}")

    def output(self, msg, verbose_level=0):
        if verbose_level >= self.verbose:
            self.logger_output.info(msg)

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