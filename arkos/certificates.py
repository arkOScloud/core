import datetime
import glob
import hashlib
import OpenSSL
import os

from arkos import config, storage
from system import systemtime, groups


if not groups.get_system("ssl-cert"):
    groups.SystemGroup("ssl-cert").add()
gid = groups.get_system("ssl-cert").gid


class Certificate:
    def __init__(
            self, id="", domain="", cert_path="", key_path="", keytype="", keylength=0,
            assign=[], expiry=None, sha1="", md5=""):
        self.id = id
        self.domain = domain
        self.cert_path = cert_path
        self.key_path = key_path
        self.keytype = keytype
        self.keylength = keylength
        self.assign = assign
        self.expiry = expiry
        self.sha1 = sha1
        self.md5 = md5
    
    def assign(self, atype, name=""):
        nginx_reload = False
        if atype == 'genesis':
            config.set('genesis', 'cert_file', self.cert_path)
            config.set('genesis', 'cert_key', self.key_path)
            config.set('genesis', 'ssl', True)
            config.save()
            self.assign.append({"type": "genesis"})
        elif atype == 'website':
            websites.get(name).ssl_enable(self)
            self.assign.append({"type": "website", "name": name})
            nginx_reload = True
        else:
            applications.get(name).ssl_enable(self)
            self.assign.append({"type": "app", "name": name})
        if nginx_reload:
            storage.sites.nginx_reload()
        return self
    
    def unassign(self, atype, name=""):
        nginx_reload = False
        if atype == "website":
            websites.get(name).ssl_disable()
            self.assign.remove({"type": atype, "name": name})
            nginx_reload = True
        elif atype == "genesis":
            config.set("genesis", "cert_file", "")
            config.set("genesis", "cert_key", "")
            config.set("genesis", "ssl", False)
            config.save()
            self.assign.remove({"type": "genesis"})
        else:
            applications.get(name).ssl_disable()
            self.assign.remove({"type": atype, "name": name})
        if nginx_reload:
            self.app.sites.nginx_reload()
        return None
    
    def remove(self):
        for x in self.assign:
            self.unassign(x["type"], x.get("name"))
        if os.path.exists(self.cert_path):
            os.unlink(self.cert_path)
        if os.path.exists(self.key_path):
            os.unlink(self.key_path)
        storage.certs.remove("certificates", self)
    
    def as_dict(self, ready=True):
        return {
            "id": self.id,
            "domain": self.domain,
            "keytype": self.keytype,
            "keylength": self.keylength,
            "assign": self.assign,
            "expiry": datetime.datetime.strptime(self.expiry, "%Y%m%d%H%M%SZ").isoformat(),
            "sha1": self.sha1,
            "md5": self.md5,
            "is_ready": ready
        }


class CertificateAuthority:
    def __init__(self, id="", cert_path="", key_path="", expiry=None):
        self.id = id
        self.cert_path = cert_path
        self.key_path = key_path
        self.expiry = expiry
    
    def remove(self):
        if os.path.exists(self.cert_path):
            os.unlink(self.cert_path)
        if os.path.exists(self.key_path):
            os.unlink(self.key_path)
        storage.certs.remove("authorities", self)
    
    def as_dict(self):
        return {
            "id": self.id,
            "expiry": datetime.datetime.strptime(self.expiry, "%Y%m%d%H%M%SZ").isoformat()
        }


def get(id=None):
    data = storage.certs.get("certificates")
    if not data:
        data = scan()
    if id:
        for x in data:
            if x.id == id:
                return x
        return None
    return data

def scan():
    certs, assigns = [], {}
    if config.get("genesis", "ssl"):
        ssl = os.path.splitext(os.path.basename(config.get('genesis', 'cert_file', '')))[0]
        if ssl and assigns.has_key(ssl):
            assigns[ssl].append({'type': 'genesis'})
        elif ssl:
            assigns[ssl] = [{'type': 'genesis'}]
    for x in glob.glob(os.path.join(config.get("certificates", "cert_dir"), '*.crt')):
        id = os.path.splitext(os.path.basename(x))[0]
        with open(x, 'r') as f:
            crt = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, f.read())
        with open(os.path.join(config.get("certificates", "key_dir"), id+'.key'), 'r') as f:
            key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, f.read())
        sha1, md5 = get_cert_hashes(crt)
        c = Certificate(id=id, cert_path=x, key_path=os.path.join(config.get("certificates", "key_dir"), id+'.key'),
            keytype="RSA" if key.type() == OpenSSL.crypto.TYPE_RSA else ("DSA" if key.type() == OpenSSL.crypto.TYPE_DSA else "Unknown"),
            keylength=int(key.bits()), domain=crt.get_subject().CN,
            assign=assigns.get(id) or [], expiry=crt.get_notAfter(),
            sha1=sha1, md5=md5)
        certs.append(c)
    storage.certs.set("certificates", certs)
    return certs

def get_authorities(id=None):
    data = storage.certs.get("authorities")
    if not data:
        data = scan_authorities()
    if id:
        for x in data:
            if x.id == id:
                return x
        return None
    return data

def scan_authorities():
    certs = []
    for x in glob.glob(os.path.join(config.get("certificates", "ca_cert_dir"), '*.pem')):
        id = os.path.splitext(os.path.split(x)[1])[0]
        with open(x, 'r') as f:
            cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, f.read())
        ca = CertificateAuthority(id=id, cert_path=x, expiry=cert.get_notAfter(),
            key_path=os.path.join(config.get("certificates", "ca_key_dir"), id+'.key'))
        certs.append(ca)
    storage.certs.set("authorities", certs)
    return certs

def upload_certificate(id, cert, key, chain=''):
    try:
        crt = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
    except Exception, e:
        raise Exception("Could not read certificate file. Please make sure you've selected the proper file.", e)
    try:
        ky = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
    except Exception, e:
        raise Exception("Could not read private keyfile. Please make sure you've selected the proper file.", e)

    sha1, md5 = get_cert_hashes(crt)
    c = Certificate(id=id, cert_path=os.path.join(config.get("certificates", "cert_dir"), id+'.crt'),
        key_path=os.path.join(config.get("certificates", "key_dir"), id+'.key'),
        keytype="RSA" if ky.type() == OpenSSL.crypto.TYPE_RSA else ("DSA" if ky.type() == OpenSSL.crypto.TYPE_DSA else "Unknown"),
        keylength=int(ky.bits()), domain=crt.get_subject().CN, expiry=crt.get_notAfter(),
        sha1=sha1, md5=md5)

    with open(c.cert_path, 'w') as f:
        f.write(cert)
        if chain:
            f.write('\n') if not cert.endswith('\n') else None
            f.write(chain)
    with open(c.key_path, 'w') as f:
        f.write(key)

    os.chown(c.cert_path, -1, gid)
    os.chmod(c.cert_path, 0660)
    os.chown(c.key_path, -1, gid)
    os.chmod(c.key_path, 0660)
    storage.certs.add("certificates", c)
    return c

def generate_certificate(
        id, domain, country, state="", locale="", email="", keytype="RSA", 
        keylength=2048):
    # Check to see that we have a CA ready
    basehost = ".".join(domain.split(".")[-2:])
    ca = get_authorities(id=basehost)
    if not ca:
        ca = generate_authority(basehost)
    with open(ca.cert_path, "r") as f:
        ca_cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, f.read())
    with open(ca.key_path, "r") as f:
        ca_key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, f.read())

    # Generate a key, then use it to sign a new cert
    try:
        key = OpenSSL.crypto.PKey()
        key.generate_key(OpenSSL.crypto.TYPE_DSA if keytype == 'DSA' else OpenSSL.crypto.TYPE_RSA, keylength)
        crt = OpenSSL.crypto.X509()
        crt.set_version(3)
        crt.get_subject().C = country
        crt.get_subject().CN = domain
        if state:
            crt.get_subject().ST = state
        if locale:
            crt.get_subject().L = locale
        if email:
            crt.get_subject().emailAddress = email
        crt.get_subject().O = 'arkOS Servers'
        crt.set_serial_number(int(systemtime.get_serial_time()))
        crt.gmtime_adj_notBefore(0)
        crt.gmtime_adj_notAfter(2*365*24*60*60)
        crt.set_issuer(ca_cert.get_subject())
        crt.set_pubkey(key)
        crt.sign(ca_key, 'sha256')
    except Exception, e:
        raise Exception('Error generating self-signed certificate: '+str(e))
    
    cert_path = os.path.join(config.get("certificates", "cert_dir"), id+'.crt')
    key_path = os.path.join(config.get("certificates", "key_dir"), id+'.key')

    with open(cert_path, "wt") as f:
        f.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, crt))
    os.chown(cert_path, -1, gid)
    os.chmod(cert_path, 0660)

    with open(key_path, "wt") as f:
        f.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key))
    os.chown(key_path, -1, gid)
    os.chmod(key_path, 0660)
    
    sha1, md5 = get_cert_hashes(crt)
    c = Certificate(id=id, domain=domain, keytype=keytype, keylength=keylength,
        cert_path=cert_path, key_path=key_path,
        sha1=sha1, md5=md5, expiry=crt.get_notAfter(), assign=[])
    storage.certs.add("certificates", c)
    return c

def generate_authority(domain):
    ca = CertificateAuthority(id=domain, 
        cert_path=os.path.join(config.get("certificates", "ca_cert_dir"), domain+'.pem'),
        key_path=os.path.join(config.get("certificates", "ca_key_dir"), domain+'.key'))
    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)

    crt = OpenSSL.crypto.X509()
    crt.set_version(3)
    crt.set_serial_number(int(systemtime.get_serial_time()))
    crt.get_subject().O = 'arkOS Servers'
    crt.get_subject().CN = domain
    crt.gmtime_adj_notBefore(0)
    crt.gmtime_adj_notAfter(5*365*24*60*60)
    crt.set_issuer(crt.get_subject())
    crt.set_pubkey(key)
    crt.add_extensions([
        OpenSSL.crypto.X509Extension("basicConstraints", True, "CA:TRUE, pathlen:0"),
        OpenSSL.crypto.X509Extension("keyUsage", True, "keyCertSign, cRLSign"),
        OpenSSL.crypto.X509Extension("subjectKeyIdentifier", False, "hash", subject=crt),
    ])
    crt.sign(key, 'sha256')
    with open(ca.cert_path, "wt") as f:
        f.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, crt))
    os.chmod(ca.cert_path, 0660)
    with open(ca.key_path, "wt") as f:
        f.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key))
    ca.expiry = crt.get_notAfter()
    storage.certs.add("authorities", ca)
    return ca

def get_cert_hashes(cert):
    h, m = hashlib.sha1(), hashlib.md5()
    h.update(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert))
    m.update(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert))
    h, m = h.hexdigest(), m.hexdigest()
    return (":".join([h[i:i+2].upper() for i in range(0,len(h), 2)]), 
        ":".join([m[i:i+2].upper() for i in range(0,len(m), 2)]))
