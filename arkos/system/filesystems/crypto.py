#
# crypto.py
#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Dave Lehman <dlehman@redhat.com>
#            Martin Sivak <msivak@redhat.com>
#

# Modified for use in arkOS by Jacob Cook <jacob@citizenweb.io>

import random
import time
from pycryptsetup import CryptSetup

from arkos.utilities import get_current_entropy

MIN_CREATE_ENTROPY = 256 # bits

# Keep the character set size a power of two to make sure all characters are
# equally likely
GENERATED_PASSPHRASE_CHARSET = ("0123456789"
                                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                "abcdefghijklmnopqrstuvwxyz"
                                "./")
# 20 chars * 6 bits per char = 120 "bits of security"
GENERATED_PASSPHRASE_LENGTH = 20

def generateBackupPassphrase():
    raw = [random.choice(GENERATED_PASSPHRASE_CHARSET) for _ in range(GENERATED_PASSPHRASE_LENGTH)]

    # Insert a '-' after every five char chunk for easier reading
    parts = []
    for i in range(0, GENERATED_PASSPHRASE_LENGTH, 5):
        parts.append(''.join(raw[i : i + 5]))
    return "-".join(parts)

yesDialog = lambda q: True
logFunc = lambda p, t: None
passwordDialog = lambda t: None

def is_luks(device):
    cs = CryptSetup(device=device, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    return cs.isLuks()

def luks_uuid(device):
    cs = CryptSetup(device=device, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    return cs.luksUUID()

def luks_status(name):
    cs = CryptSetup(name=name, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    return cs.status()

def luks_format(device, passphrase, cipher=None, key_size=None, 
                key_file=None, min_entropy=0):
    cs = CryptSetup(device=device, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    kwargs = {}

    cipherType, cipherMode = None, None
    if cipher:
        cparts = cipher.split("-")
        cipherType = "".join(cparts[0:1])
        cipherMode = "-".join(cparts[1:])

    if cipherType: kwargs["cipher"]  = cipherType
    if cipherMode: kwargs["cipherMode"]  = cipherMode
    if   key_size: kwargs["keysize"]  = key_size

    if min_entropy > 0:
        while get_current_entropy() < min_entropy:
            time.sleep(1)

    rc = cs.luksFormat(**kwargs)
    if rc: return rc
    rc = cs.addKeyByVolumeKey(newPassphrase=passphrase)
    return rc if rc else 0

def luks_open(device, name, passphrase, key_file=None):
    cs = CryptSetup(device=device, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    return cs.activate(passphrase=passphrase, name=name)

def luks_close(name):
    cs = CryptSetup(name=name, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    return cs.deactivate()

def luks_add_key(device, new_passphrase, passphrase, key_file=None):
    cs = CryptSetup(device=device, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    return cs.addKeyByPassphrase(passphrase=passphrase, newPassphrase=new_passphrase)

def luks_remove_key(device, del_passphrase, passphrase, key_file=None):
    cs = CryptSetup(device=device, yesDialog=yesDialog, logFunc=logFunc, passwordDialog=passwordDialog)
    return cs.removePassphrase(passphrase=passphrase)
