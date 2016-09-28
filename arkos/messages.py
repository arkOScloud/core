"""
Classes for management of arkOS process logging.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos import logger
from arkos.utilities import random_string


class Notification(object):
    """A singular status message, broadcast to log and clients."""

    LEVELS = {
        "DEBUG": 10,
        "INFO": 20,
        "SUCCESS": 25,
        "WARN": 30,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }

    def __init__(self, level, comp, message, cls="notify",
                 id_=None, title=None):
        level = level.upper()
        if level not in self.LEVELS:
            raise Exception("Unrecognized log level specified")
        self.level = self.LEVELS[level]
        self.comp = comp
        self.message = message
        self.cls = cls
        self.id = id_
        self.title = title
        self.thread_id = None
        self.complete = True

    def send(self):
        data = {
            "id": self.id, "thread_id": self.thread_id, "cls": self.cls,
            "comp": self.comp, "title": self.title, "message": self.message,
            "complete": self.complete
        }
        logger._log(self.level, data)


class NotificationThread(object):
    """A thread of Notifications bound together, keeping the same context."""

    def __init__(self, id_=None, title=None, message=None):
        self.id = id_ or random_string(16)
        self.title = title
        if message:
            self._send(message, complete=False)

    def _send(self, message, complete=False):
        message.thread_id = self.id
        message.title = self.title or message.title
        message.complete = complete
        message.send()

    def new(self, level, comp, message, cls="notify",
            id_=None, title=None):
        return Notification(level, comp, message, cls,
                            id_ or random_string(16), title)

    def update(self, *messages):
        for message in messages:
            self._send(message)

    def complete(self, message):
        self._send(message, complete=True)
