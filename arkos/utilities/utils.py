"""
Associated utility functions used in arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import bz2
import base64
import binascii
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
import crypt
import gzip
import os
import random
import requests
import shlex
import socket
import string
import subprocess
import tarfile
import tempfile
import time
import zipfile


def cidr_to_netmask(cidr):
    """Convert a CIDR prefix to an IP subnet mask."""
    mask = [0, 0, 0, 0]
    for i in range(cidr):
        mask[i/8] = mask[i/8] + (1 << (7 - i % 8))
    return ".".join(map(str, mask))


def netmask_to_cidr(mask):
    """Convert an IP subnet mask to CIDR prefix."""
    mask = mask.split(".")
    binary_str = ""
    for octet in mask:
        binary_str += bin(int(octet))[2:].zfill(8)
    return len(binary_str.rstrip("0"))


def test_dns(host):
    """
    Test DNS resolution.

    :param str host: hostname
    :returns: True if resolution was successful
    """
    try:
        test = socket.gethostbyname_ex("arkos.io")
    except:
        return False
    return True if test else False


def test_port(server, port, host=None):
    """
    Use an arkOS GRM server to test local port connectivity.

    :param str server: GRM server address
    :param int port: Port number
    :param str host: Host (if domain is to be tested instead of IP)
    :returns: True if port test was successful
    """
    timer = 5
    id = random_string(16)
    pfile = os.path.join(os.path.dirname(__file__), "test-port.py")
    p = subprocess.Popen(["python", pfile, str(port), id])
    data = {"id": id, "port": port, "host": host or ""}
    requests.post("https://" + server + "/api/v1/echo", data=data)
    while timer > 0:
        p.poll()
        if p.returncode is None:
            timer -= 1
            time.sleep(1)
        elif p.returncode is not None:
            break
    if p.returncode is None:
        p.kill()
    return True if p.returncode == 0 else False


def download(url, file=None, crit=False):
    """
    Download a file from the specified address, optionally saving to file.

    :param str url: URL to download
    :param str file: path of output file to save, or None to return contents
    :param bool crit: raise exceptions on all failures
    """
    try:
        data = requests.get(url)
        if file:
            with open(file, "w") as f:
                f.write(data.text)
        else:
            return data.text
    except Exception:
        if crit:
            raise


def get_current_entropy():
    """Get the current amount of available entropy from the kernel."""
    with open("/proc/sys/kernel/random/entropy_avail", "r") as f:
        return int(f.readline())


def random_string():
    """Create a random alphanumeric string."""
    digest = hashes.Hash(hashes.SHA1(), backend=default_backend())
    digest.update(str(random.random()).encode('utf-8'))
    return binascii.hexlify(digest.finalize())


def api(url, post=None, method="get", returns="json", headers=[], crit=False):
    """
    Multipurpose function to send/receive data from an Internet address.

    Default use returns a dictionary from a JSON API.

    :param str url: URL to contact
    :param str/dict post: data to POST
    :param method: HTTP method
    :param str returns: "JSON" or "raw"
    :param list headers: tuples of header name and values
    :param bool crit: raise exception on all errors
    :returns: data as specified
    """
    err_str = "{0} to {1} failed - "
    try:
        headers = {x[0]: x[1] for x in headers}
        headers["Content-type"] = "application/json"
        action = getattr(requests, method.lower())
        if post:
            req = action(url, headers=headers, json=post)
        else:
            req = action(url, headers=headers, json=post)
        if returns == "json":
            return req.json()
        else:
            return req.text
        req.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if crit:
            raise Exception((err_str + "HTTP Error {2}").format(
                method.upper(), url, req.code))
    except requests.exceptions.RequestException as e:
        if crit:
            raise Exception((err_str + "Server not found or URL malformed."
                            "Please check your Internet settings.").format(
                            method.upper(), url))
    except Exception as e:
        if crit:
            raise Exception((err_str + "{2}").format(method.upper(), url, e))


def shell(c, stdin=None, env={}):
    """
    Simplified wrapper for shell calls to subprocess.Popen().

    Returns a dict with ``code``, ``stdout`` and ``stderr`` keys.

    :param str c: command string
    :param str stdin: data to feed to stdin, or None
    :param dict env: dict of environment variables
    """
    environ = os.environ
    environ["LC_ALL"] = "C"
    for x in env:
        environ[x] = env[x]
    if "HOME" not in environ:
        environ["HOME"] = "/root"
    p = subprocess.Popen(shlex.split(c), stderr=subprocess.PIPE,
                         stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                         env=environ)
    data = p.communicate(stdin)
    return {"code": p.returncode, "stdout": data[0],
            "stderr": data[1]}


def hashpw(passw):
    """Create a password hash."""
    rnd = "".join(random.sample(string.ascii_uppercase + string.digits, 16))
    salt = "$6$" + rnd + "$"
    return "{CRYPT}" + crypt.crypt(passw, salt)


def can_be_int(data):
    """Return True if the input can be an integer."""
    try:
        int(data)
        return True
    except ValueError:
        return False


def str_fsize(sz):
    """Format a size int/float to the most appropriate string."""
    if sz < 1024:
        return "{:.1f} bytes".format(sz)
    sz /= 1024.0
    if sz < 1024:
        return "{:.1f} Kb".format(sz)
    sz /= 1024.0
    if sz < 1024:
        return "{:.1f} Mb".format(sz)
    sz /= 1024.0
    return "{:.1f} Gb".format(sz)


def str_fperms(mode):
    """Produce a Unix-style permissions string (rwxrwxrwx)."""
    return ("r" if mode & 256 else "-") + \
           ("w" if mode & 128 else "-") + \
           ("x" if mode & 64 else "-") + \
           ("r" if mode & 32 else "-") + \
           ("w" if mode & 16 else "-") + \
           ("x" if mode & 8 else "-") + \
           ("r" if mode & 4 else "-") + \
           ("w" if mode & 2 else "-") + \
           ("x" if mode & 1 else "-")


def path_to_b64(path):
    """Convert a filesystem path to a safe base64-encoded string."""
    path = path.replace("//", "/")
    return base64.b64encode(path, altchars="+-").replace("=", "*")


def b64_to_path(b64):
    """Convert a base64-encoded string to regular one (filesystem path)."""
    return base64.b64decode(str(b64).replace("*", "="), altchars="+-")


def compress(pin, pout="", format="tgz"):
    """
    Recursively compress a provided directory.

    :param str pin: path to directory to compress
    :param str pout: full path to save archive to
    :param str format: "tgz" or "zip"
    """
    if format == "tgz":
        pout = tempfile.mkstemp(".tar.gz")[1] if not pout else pout
        a = tarfile.open(pout, "w:gz")
        if os.path.isdir(pin):
            for r, d, f in os.walk(pin):
                for x in f:
                    a.add(os.path.join(r, x), os.path.join(r, x).split(
                        os.path.split(pin)[0]+"/")[1])
        else:
            a.add(x)
        a.close()
    elif format == "zip":
        pout = tempfile.mkstemp(".zip")[1] if not pout else pout
        a = zipfile.ZipFile(pout, "w")
        if os.path.isdir(pin):
            for r, d, f in os.walk(pin):
                for x in f:
                    a.write(os.path.join(r, x), os.path.join(r, x).split(
                        os.path.split(pin)[0]+"/")[1])
        else:
            a.write(x)
        a.close()
    return pout


def extract(pin, pout, delete=False):
    """
    Extract an archive.

    :param str pin: path to archive
    :param str pout: path to output
    :param bool delete: delete archive on completion
    """
    name = os.path.basename(pin)
    if name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(pin, "r:gz") as t:
            t.extractall(pout)
    elif name.endswith(".tar"):
        with tarfile.open(pin, "r") as t:
            t.extractall(pout)
    elif name.endswith(".gz"):
        f = gzip.open(pin, "rb")
        i = f.read()
        f.close()
        with open(os.path.join(pout, name.split(".gz")[0]), "wb") as f:
            f.write(i)
    elif name.endswith((".tar.bz2", ".tbz2")):
        with tarfile.open(pin, "r:bz2") as t:
            t.extractall(f[0])
    elif name.endswith(".bz2"):
        f = bz2.BZ2File(pin, "r")
        i = f.read()
        f.close()
        with open(os.path.join(pout, name.split(".bz2")[0]), "wb") as f:
            f.write(i)
    elif name.endswith(".zip"):
        with zipfile.ZipFile(pin, "r") as z:
            z.extractall(pout)
    else:
        raise Exception("Not an archive, or unknown archive type")
    if delete:
        os.unlink(pin)
