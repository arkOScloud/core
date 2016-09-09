"""
Associated error classes used in arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from .logs import LoggingControl


class Error(Exception):
    """Base class for exceptions."""

    def __init__(self, msg):
        """Initialize class."""
        self.msg = msg

    def __str__(self):
        """String format."""
        return self.msg


class ConfigurationError(Error):
    """Raised when a value cannot be found in an arkOS configuration file."""


class ConnectionError(Error):
    """Raised in chain when a system API connection fails."""

    def __init__(self, service, info=""):
        self.service = service
        self.info = info

    def __str__(self):
        return "Failed to connect to {0} service{1}".format(
            self.service, self.info)


class OperationFailedError(Error):
    """Raised in chain when an operation fails due to an exception."""

    def __init__(self, info="", nthread=None, title=None):
        self.dmsg = info or "General failure"
        msg = "Operation failed: {0} {1}"\
            .format(info, str(self.__cause__ or ""))
        if nthread:
            nthread.complete(nthread.new("error", "", msg, title=title))
        else:
            LoggingControl().error("", msg)

    def __str__(self):
        return str(self.__cause__ or self.dmsg)


class InvalidConfigError(Error):
    """Raised in chain when an operation fails due to user choices."""

    def __init__(self, info="", nthread=None, title=None):
        self.dmsg = info or "Invalid value passed"
        msg = "Invalid value: {0} {1}"\
            .format(info, str(self.__cause__ or ""))
        if nthread:
            nthread.complete(nthread.new("error", "", msg, title=title))
        else:
            LoggingControl().error("", msg)

    def __str__(self):
        return str(self.__cause__ or self.dmsg)
