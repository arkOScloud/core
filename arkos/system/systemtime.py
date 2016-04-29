"""
Helper functions for managing system time.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import ctypes
import ctypes.util
import datetime
import ntplib
import os
import time

from arkos import config, signals

ntp = ntplib.NTPClient()


class timespec(ctypes.Structure):
    """C struct for timespec."""

    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


def verify_time(update=True, crit=True):
    """
    Verify system time with NTP, set it if it is more than an hour off.

    :param bool update: Update system time if it is too far off.
    :param bool crit: Raise an exception if time cannot be retrieved.
    """
    try:
        os = get_offset()
    except Exception as e:
        if crit:
            raise Exception("System time could not be retrieved. "
                            "Error: {0}".format(e))
        else:
            return "UNKNOWN"
    if (os < -3600 or os > 3600) and update:
        set_datetime()
    return os


def get_offset():
    """
    Get the amount of seconds that system time is off from NTP.

    :returns: NTP offset
    :rtype: float
    """
    resp = ntp.request(config.get("general", "ntp_server"), version=3)
    return resp.offset


def get_date():
    """
    Get current date.

    :returns: Date in config's ``date_format``
    :rtype: str
    """
    return time.strftime(config.get("general", "date_format", "%d %b %Y"))


def get_time():
    """
    Get current time.

    :returns: Time in config's ``time_format``
    :rtype: str
    """
    return time.strftime(config.get("general", "time_format", "%H:%M"))


def get_unix_time(ts=None, fmt="%Y-%m-%dT%H:%M:%S"):
    """
    Get Unix time from provided timestamp (or current time if None).

    :param str ts: timestamp string
    :param str fmt: format to parse provided timestamp by
    :returns: Unix timestamp
    :rtype: int
    """
    if ts:
        return int(datetime.datetime.strptime(ts, fmt).strftime("%s"))
    else:
        return int(time.time())


def get_datetime():
    """
    Get current date and time in default formats.

    :returns: date and time
    :rtype: str
    """
    return get_date() + " " + get_time()


def set_datetime(ut=0):
    """
    Set system time from provided Unix timestamp (or current time via NTP).

    :param int ut: Unix timestamp
    """
    ut = int(ut) if ut else int(get_idatetime())
    librt = ctypes.CDLL(ctypes.util.find_library("rt"), use_errno=True)
    ts = timespec()
    ts.tv_sec, ts.tv_nsec = ut, 0
    res = librt.clock_settime(0, ctypes.byref(ts))
    if res == -1:
        raise Exception("Could not set time: {0}"
                        .format(os.strerror(ctypes.get_errno())))
    signals.emit("config", "time_changed", ut)


def get_idatetime():
    """
    Get date and time from NTP server.

    :returns: Unix timestamp
    :rtype: float
    """
    resp = ntp.request(config.get("general", "ntp_server"), version=3)
    return resp.tx_time


def get_serial_time():
    """
    Get current time in serial format (e.g. 20150420213000).

    :returns: time in serial format
    :rtype: str
    """
    return time.strftime("%Y%m%d%H%M%S")


def get_iso_time(ts=None, fmt="%Y%m%d%H%M%S"):
    """
    Get time in ISO-8601 format from provided timestamp (or current time).

    :param str ts: timestamp string. If None, time returned is current time.
    :param str fmt: format to parse provided timestamp by
    :returns: ISO-8601 timestamp
    :rtype: str
    """
    tz = time.strftime("%z")
    tz = "{0}:{1}".format(tz[:3], tz[3:])
    if ts and fmt == "unix":
        return datetime.datetime.fromtimestamp(ts).isoformat()+tz
    elif ts:
        return datetime.datetime.strptime(ts, fmt).isoformat()+tz
    else:
        return datetime.datetime.now().isoformat()+tz


def ts_to_datetime(ts, fmt="%Y%m%d%H%M%S"):
    """
    Get datetime object from provided timestamp (or current time).

    :param str ts: timestamp string
    :param str fmt: format to parse provided timestamp by
    :returns: datetime object
    :rtype: datetime.datetime
    """
    if fmt == "unix":
        return datetime.datetime.fromtimestamp(ts)
    else:
        return datetime.datetime.strptime(ts, fmt)
