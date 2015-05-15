import datetime
import logging
import sys

from errors import DefaultException


class DefaultMessage:
    PRINT = False

    def __init__(self, cls="", msg=""):
        if cls == "error" and msg:
            raise DefaultException(str(msg))
        elif self.PRINT and cls == "warning" and msg:
            print "\033[33m%s\033[0m" % msg
        elif self.PRINT and msg:
            print "\033[32m%s\033[0m" % msg

    def update(self, cls, msg):
        if cls == "error":
            raise DefaultException(str(msg))
        elif self.PRINT and cls == "warning":
            print "\033[33m%s\033[0m" % msg
        elif self.PRINT:
            print "\033[32m%s\033[0m" % msg

    def complete(self, cls, msg):
        if cls == "error":
            raise DefaultException(str(msg))
        elif self.PRINT and cls == "warning":
            print "\033[33m%s\033[0m" % msg
        elif self.PRINT:
            print "\033[32m%s\033[0m" % msg


class LoggingControl:
    def __init__(self, logger=None):
        self.logger = logger

    def info(self, msg):
        self.logger.info(msg)

    def warn(self, msg):
        self.logger.warn(msg)

    def error(self, msg):
        self.logger.error(msg)

    def debug(self, msg):
        self.logger.debug(msg)


class ConsoleHandler(logging.StreamHandler):
    def __init__(self, stream, debug, tstamp=True):
        self.tstamp = tstamp
        self.debug = debug
        logging.StreamHandler.__init__(self, stream)

    def handle(self, record):
        if not self.stream.isatty():
            return logging.StreamHandler.handle(self, record)

        s = ""
        if self.tstamp:
            d = datetime.datetime.fromtimestamp(record.created)
            s += d.strftime("\033[37m%d.%m.%Y %H:%M \033[0m")
        if self.debug:
            s += ("%s:%s"%(record.filename,record.lineno)).ljust(30)
        l = ""
        if record.levelname == "DEBUG":
            l = "\033[37mDEBUG\033[0m "
        if record.levelname == "INFO":
            l = "\033[32mINFO\033[0m  "
        if record.levelname == "WARNING":
            l = "\033[33mWARN\033[0m  "
        if record.levelname == "ERROR":
            l = "\033[31mERROR\033[0m "
        s += l.ljust(9)
        s += record.msg
        s += "\n"
        self.stream.write(s)


def new_logger(log_level=logging.INFO, debug=False):
    logger = logging.getLogger("arkos")
    stdout = ConsoleHandler(sys.stdout, debug, False)
    stdout.setLevel(logging.DEBUG if debug else log_level)
    dformatter = logging.Formatter("%(asctime)s [%(levelname)s] %(module)s: %(message)s")
    stdout.setFormatter(dformatter)
    logger.addHandler(stdout)
    return logger
