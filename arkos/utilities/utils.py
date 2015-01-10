import base64
import crypt
import git
import hashlib
import json
import os
import random
import shlex
import string
import subprocess
import urllib2

from passlib.hash import sha512_crypt


def version():
    release = '0.7'
    try:
        g = git.repo.Repo("./")
        return g.git.describe(tags=True)
    except (git.exc.InvalidGitRepositoryError, git.exc.GitCommandError):
        return "0.7"

def dictfilter(inp, kwargs):
    results = []
    for x in inp:
        for y in kwargs:
            if y in x and x[y] == kwargs[y]:
                results.append(x)
    return results

def cidr_to_netmask(cidr):
    mask = [0, 0, 0, 0]
    for i in range(cidr):
        mask[i/8] = mask[i/8] + (1 << (7 - i % 8))
    return ".".join(map(str, mask))

def netmask_to_cidr(mask):
    mask = mask.split('.')
    binary_str = ''
    for octet in mask:
        binary_str += bin(int(octet))[2:].zfill(8)
    return len(binary_str.rstrip('0'))

def download(url, file=None, crit=False):
    try:
        data = urllib2.urlopen(url).read()
        if file:
            with open(file, 'w') as f:
                f.write(data)
        else:
            return data
    except Exception, e:
        if crit:
            raise

def get_current_entropy():
    with open("/proc/sys/kernel/random/entropy_avail", "r") as f:
        return int(f.readline())

def random_string():
    return hashlib.sha1(str(random.random())).hexdigest()

def api(url, post=None, method="", returns="json", headers=[], crit=False):
    try:
        req = urllib2.Request(url)
        req.add_header('Content-type', 'application/json')
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
            raise Exception('%s to %s failed - HTTP Error %s' % (req.get_method(), url, str(e.code)))
    except urllib2.URLError, e:
        if crit:
            raise Exception('%s to %s failed - Server not found or URL malformed. Please check your Internet settings.' % (req.get_method(), url))
    except Exception, e:
        if crit:
            raise Exception('%s to %s failed - %s' % (req.get_method(), url, str(e)))

def shell(c, stdin=None, env={"LC_ALL": "C"}):
    p = subprocess.Popen(shlex.split(c),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            env=env)
    data = p.communicate(stdin)
    data = {"code": p.returncode, "stdout": data[0], 
        "stderr": data[1]}
    return data

def hashpw(passw, scheme='sha512_crypt'):
    if scheme == 'sha512_crypt':
        return sha512_crypt.encrypt(passw)
    elif scheme == 'crypt':
        salt = "$1$" + "".join(random.sample(string.ascii_uppercase+string.digits, 8)) + "$"
        return "{CRYPT}" + crypt.crypt(passw, salt)
    elif scheme == 'ssha':
        salt = os.urandom(32)
        return '{SSHA}' + base64.b64encode(hashlib.sha1(passw + salt).digest() + salt)
    return sha512_crypt.encrypt(passw)

def can_be_int(data):
    try: 
        int(data)
        return True
    except ValueError:
        return False

def str_fsize(sz):
    if sz < 1024:
        return '%.1f bytes' % sz
    sz /= 1024.0
    if sz < 1024:
        return '%.1f Kb' % sz
    sz /= 1024.0
    if sz < 1024:
        return '%.1f Mb' % sz
    sz /= 1024.0
    return '%.1f Gb' % sz
