"""
Classes for management of arkOS status message logging.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos import logger
from arkos.utilities import random_string


class MessageContext(object):
    """A context for asynchronous, updatable status messages."""

    def __init__(self, comp, title=None, cls="notify"):
        """
        Create a new notification context.

        :param str comp: Section of application to state as origin
        :param str title: Message title text
        :param str cls: Either 'runtime' (log) or 'notify' (notification)
        """
        self.id = random_string()[0:10]
        self.comp = comp
        self.title = title
        self.cls = cls

    def info(self, msg, title=None, complete=False):
        """
        Update the notification with an INFO message.

        :param str msg: Message text
        :param str title: Message title text
        :param bool complete: Is this the last message to be pushed?
        """
        logger.info(self.comp, msg, id=self.id, title=self.title,
                    cls=self.cls, persist=not complete)

    def success(self, msg, title=None, complete=False):
        """
        Update the notification with a SUCCESS message.

        :param str msg: Message text
        :param str title: Message title text
        :param bool complete: Is this the last message to be pushed?
        """
        logger.success(self.comp, msg, id=self.id, title=self.title,
                       cls=self.cls, persist=not complete)

    def warning(self, msg, title=None, complete=False):
        """
        Update the notification with a WARN message.

        :param str msg: Message text
        :param str title: Message title text
        :param bool complete: Is this the last message to be pushed?
        """
        logger.warning(self.comp, msg, id=self.id, title=self.title,
                       cls=self.cls, persist=not complete)

    def error(self, msg, title=None, complete=False):
        """
        Update the notification with an ERROR message.

        :param str msg: Message text
        :param str title: Message title text
        :param bool complete: Is this the last message to be pushed?
        """
        logger.error(self.comp, msg, id=self.id, title=self.title,
                     cls=self.cls, persist=not complete)

    def debug(self, msg, title=None, complete=False):
        """
        Update the notification with a DEBUG message.

        :param str msg: Message text
        :param str title: Message title text
        :param bool complete: Is this the last message to be pushed?
        """
        logger.debug(self.comp, msg, id=self.id, title=self.title,
                     cls=self.cls, persist=not complete)
