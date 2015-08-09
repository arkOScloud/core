import bz2
import base64
import crypt
import glob
import gzip
import hashlib
import json
import os
import random
import shlex
import string
import subprocess
import tarfile
import tempfile
import urllib2
import zipfile

from passlib.hash import sha512_crypt


def dictfilter(inp, kwargs):
    results = []
    for x in inp:
        for y in kwargs:
            if y in x and x[y] == kwargs[y]:
                results.append(x)
    return results

def cidr_to_netmask(cidr):
    # Converts a CIDR prefix to an IP subnet mask.
    mask = [0, 0, 0, 0]
    for i in range(cidr):
        mask[i/8] = mask[i/8] + (1 << (7 - i % 8))
    return ".".join(map(str, mask))

def netmask_to_cidr(mask):
    # Converts an IP subnet mask to CIDR prefix.
    mask = mask.split(".")
    binary_str = ""
    for octet in mask:
        binary_str += bin(int(octet))[2:].zfill(8)
    return len(binary_str.rstrip("0"))

def download(url, file=None, crit=False):
    # Downloads a file from the specified address, optionally saving to file.
    try:
        data = urllib2.urlopen(url).read()
        if file:
            with open(file, "w") as f:
                f.write(data)
        else:
            return data
    except Exception, e:
        if crit:
            raise

def get_current_entropy():
    # Get the current amount of available entropy from the kernel.
    with open("/proc/sys/kernel/random/entropy_avail", "r") as f:
        return int(f.readline())

def random_string():
    # Create a random alphanumeric string.
    return hashlib.sha1(str(random.random())).hexdigest()

def api(url, post=None, method="", returns="json", headers=[], crit=False):
    # Multipurpose function to send/receive data from an Internet address.
    # Default use returns a dictionary from a JSON API.
    try:
        req = urllib2.Request(url)
        req.add_header("Content-type", "application/json")
        if method:
            req.get_method = lambda: method
        for x in headers:
            req.add_header(x[0], x[1])
        resp = urllib2.urlopen(req, json.dumps(post) if post else None)
        if returns == "json":
            return json.loads(resp.read())
        else:
            return resp.read()
    except urllib2.HTTPError, e:
        if crit:
            raise Exception("%s to %s failed - HTTP Error %s" % (req.get_method(), url, str(e.code)))
    except urllib2.URLError, e:
        if crit:
            raise Exception("%s to %s failed - Server not found or URL malformed. Please check your Internet settings." % (req.get_method(), url))
    except Exception, e:
        if crit:
            raise Exception("%s to %s failed - %s" % (req.get_method(), url, str(e)))

def shell(c, stdin=None, env={}):
    # Simplified wrapper for shell calls to subprocess.Popen()
    environ = os.environ
    environ["LC_ALL"] = "C"
    for x in env:
        environ[x] = env[x]
    if not "HOME" in environ:
        environ["HOME"] = "/root"
    p = subprocess.Popen(shlex.split(c),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            env=environ)
    data = p.communicate(stdin)
    return {"code": p.returncode, "stdout": data[0],
        "stderr": data[1]}

def hashpw(passw, scheme="sha512_crypt"):
    if scheme == "sha512_crypt":
        return sha512_crypt.encrypt(passw)
    elif scheme == "crypt":
        salt = "$1$" + "".join(random.sample(string.ascii_uppercase+string.digits, 8)) + "$"
        return "{CRYPT}" + crypt.crypt(passw, salt)
    elif scheme == "ssha":
        salt = os.urandom(32)
        return "{SSHA}" + base64.b64encode(hashlib.sha1(passw + salt).digest() + salt)
    return sha512_crypt.encrypt(passw)

def can_be_int(data):
    try:
        int(data)
        return True
    except ValueError:
        return False

def str_fsize(sz):
    # Format a size int/float to the most appropriate string.
    if sz < 1024:
        return "%.1f bytes" % sz
    sz /= 1024.0
    if sz < 1024:
        return "%.1f Kb" % sz
    sz /= 1024.0
    if sz < 1024:
        return "%.1f Mb" % sz
    sz /= 1024.0
    return "%.1f Gb" % sz

def str_fperms(mode):
    # Produce a Unix-style permissions string (rwxrwxrwx).
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
    # Convert a filesystem path to a safe base64-encoded string.
    path = path.replace("//","/")
    return base64.b64encode(path, altchars="+-").replace("=", "*")

def b64_to_path(b64):
    # Convert a base64-encoded string to regular one (filesystem path).
    return base64.b64decode(str(b64).replace("*", "="), altchars="+-")

def compress(pin, pout="", format="tgz"):
    # Recursively compress a provided directory.
    if format == "tgz":
        pout = tempfile.mkstemp(".tar.gz")[1] if not pout else pout
        a = tarfile.open(pout, "w:gz")
        if os.path.isdir(pin):
            for r, d, f in os.walk(pin):
                for x in f:
                    a.add(os.path.join(r, x), os.path.join(r, x).split(os.path.split(pin)[0]+"/")[1])
        else:
            a.add(x)
        a.close()
    elif format == "zip":
        pout = tempfile.mkstemp(".zip")[1] if not pout else pout
        a = zipfile.ZipFile(pout, "w")
        if os.path.isdir(pin):
            for r, d, f in os.walk(pin):
                for x in f:
                    a.write(os.path.join(r, x), os.path.join(r, x).split(os.path.split(pin)[0]+"/")[1])
        else:
            a.write(x)
        a.close()
    return pout

def extract(pin, pout, delete=False):
    # Extract an archive.
    name = os.path.basename(pin)
    if name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(pin, "r:gz") as t:
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
