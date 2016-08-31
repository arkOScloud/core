"""
Associated error classes used in arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""


class Error(Exception):
    """Base class for exceptions."""

    def __init__(self, msg):
        """Initialize class."""
        self.msg = msg

    def __str__(self):
        """String format."""
        return self.msg


class ConnectionError(Error):
    """Raised in chain when a system API connection fails."""

    def __str__(self):
        return "Failed to connect to {0} service".format(self.msg)


class OperationFailedError(Error):
    """Raised in chain when an operation fails due to an exception."""

    def __init__(self, info="", message=None, head=None):
        self.dmsg = info or "General failure"
        if message:
            msg = "Operation failed: {0} {1}"\
                .format(info, str(self.__cause__ or ""))
            message.complete("error", msg, head=head)

    def __str__(self):
        return str(self.__cause__ or self.dmsg)


class InvalidConfigError(Error):
    """Raised in chain when an operation fails due to user choices."""

    def __init__(self, info="", message=None, head=None):
        self.dmsg = info or "Invalid value passed"
        if message:
            msg = "Invalid value: {0} {1}"\
                .format(info, str(self.__cause__ or ""))
            message.complete("error", msg, head=head)

    def __str__(self):
        return str(self.__cause__ or self.dmsg)
