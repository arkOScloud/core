"""
Classes for management of arkOS process logging.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import logging

from .utils import random_string


class StreamFormatter(logging.Formatter):
    def format(self, record):
        data = record.msg
        record.msg = data["message"]
        if record.levelname == "DEBUG":
            record.levelname = "\033[37mDEBUG\033[0m  "
        if record.levelname == "INFO":
            record.levelname = "\033[36mINFO\033[0m   "
        if record.levelname == "SUCCESS":
            record.levelname = "\033[32mSUCCESS\033[0m"
        if record.levelname == "WARNING":
            record.levelname = "\033[33mWARN\033[0m   "
        if record.levelname == "ERROR":
            record.levelname = "\033[31mERROR\033[0m  "
        for x in data:
            if x == "message":
                continue
            setattr(record, x, data[x])
        record.cls = data["class"][0].upper()
        result = logging.Formatter.format(self, record)
        return result


class RuntimeFilter(logging.Filter):
    def filter(self, record):
        if record.msg.cls.startswith("r"):
            return 1
        return 0


class NotificationFilter(logging.Filter):
    def filter(self, record):
        if record.msg.cls.startswith("n"):
            return 1
        return 0


class LoggingControl:
    """Control logging for runtime or notification events."""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("arkos")
        logging.addLevelName(25, "SUCCESS")

    def add_stream_logger(self, debug=False):
        """Create a new stream logger."""
        self.logger.handlers = []
        stdout = logging.StreamHandler()
        stdout.setLevel(logging.DEBUG if debug else logging.INFO)
        st = "%(asctime)s [%(cls)s] [%(levelname)s] %(component)s: %(message)s"
        dformatter = StreamFormatter(st)
        stdout.setFormatter(dformatter)
        self.logger.addHandler(stdout)

    def info(self, comp, msg, id=None, title=None,
             cls="runtime", persist=False):
        """Send a message with log level INFO."""
        self.logger.info(
            {"id": id or random_string()[0:10], "title": title, "message": msg,
             "component": comp, "class": cls, "persist": persist}
        )

    def success(self, comp, msg, id=None, title=None,
                cls="runtime", persist=False):
        """Send a message with log level SUCCESS."""
        self.logger.log(
            25,
            {"id": id or random_string()[0:10], "title": title, "message": msg,
             "component": comp, "class": cls, "persist": persist}
        )

    def warning(self, comp, msg, id=None, title=None,
                cls="runtime", persist=False):
        """Send a message with log level WARNING."""
        self.logger.warning(
            {"id": id or random_string()[0:10], "title": title, "message": msg,
             "component": comp, "class": cls, "persist": persist}
        )

    def error(self, comp, msg, id=None, title=None,
              cls="runtime", persist=False):
        """Send a message with log level ERROR."""
        self.logger.error(
            {"id": id or random_string()[0:10], "title": title, "message": msg,
             "component": comp, "class": cls, "persist": persist},
            exc_info=True
        )

    def debug(self, comp, msg, id=None, title=None,
              cls="runtime", persist=False):
        """Send a message with log level DEBUG."""
        self.logger.debug(
            {"id": id or random_string()[0:10], "title": title, "message": msg,
             "component": comp, "class": cls, "persist": persist}
        )
