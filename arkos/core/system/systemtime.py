import ctypes, ctypes.util
import ntplib
import time


class SystemTime(object):
    class timespec(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]

    def __init__(self, dfmt="", tfmt="", ntpsrv="", log=None, config=None):
        if not all([dfmt, tfmt, ntpsrv]) and not config:
            raise Exception("No configuration values passed")
        self.dfmt = dfmt or self.Config.get("main", "date_format", "%d %b %Y")
        self.tfmt = tfmt or self.Config.get("main", "time_format", "%H:%M")
        self.ntpsrv = ntpsrv or self.Config.get("main", "ntp_server")
        self.ntp = ntplib.NTPClient()
        self.log = log

    def verify_time(self, update=True):
        try:
            os = self.get_offset()
        except Exception, e:
            raise Exception('System time could not be retrieved. Error: %s' % str(e))
        if (os < -3600 or os > 3600) and update:
            self.set_datetime()
        return os

    def get_datetime(self, display=''):
        return time.strftime(display) if display else time.localtime()

    def get_idatetime(self):
        resp = self.ntp.request(self.ntpsrv, version=3)
        return resp.tx_time

    def set_datetime(self, dt=0):
        dt = int(dt) if dt else int(get_idatetime())
        librt = ctypes.CDLL(ctypes.util.find_library("rt"))
        ts = self.timespec()
        ts.tv_sec, ts.tv_nsec = dt, dt * 1000000
        librt.clock_settime(0, ctypes.byref(ts))

    def convert(self, intime, infmt, outfmt):
        return time.strftime(outfmt, time.strptime(intime, infmt))

    def get_serial_time(self):
        return time.strftime('%Y%m%d%H%M%S')

    def get_date(self):
        return time.strftime(self.dfmt)

    def get_time(self):
        return time.strftime(self.tfmt)

    def get_offset(self):
        resp = self.ntp.request(self.ntpsrv, version=3)
        return resp.offset
