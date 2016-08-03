"""
Associated error classes used in arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

class ConfigurationError(Exception):
    """Configuration error."""
    
    def __init__(self, text):
        """Initialize class."""
        self.text = id

    def __str__(self):
        """String format."""
        return self.text

class ConnectionError(Exception):
    """Connection error."""
    
    def __init__(self, id):
        """Initialize class."""
        self.id = id

    def __str__(self):
        """String format."""
        
        return "Failed to connect to {0} service".format(self.id)


class SoftFail(Exception):
    """Soft failure exception."""
    
    def __init__(self, msg):
        """Initialize class."""
        self.msg = msg

    def __str__(self):
        """String format."""
        return self.msg


class RequestError(Exception):
    """Request error made."""
    
    def __init__(self, msg):
        """Initialize class."""
        self.msg = msg

    def __str__(self):
        """String format."""
        return self.msg


class DefaultException(Exception):
    """Default exception class."""
    
    def __init__(self, msg):
        """Initialize class."""
        self.msg = msg

    def __str__(self):
        """String format."""
        return self.msg
