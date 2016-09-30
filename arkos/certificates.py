"""
Classes and functions for management of TLS certificates in arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import binascii
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import dsa, rsa
import datetime
import glob
import os

from arkos import config, signals, storage, websites, applications, logger
from arkos.messages import Notification, NotificationThread
from arkos.system import groups
from arkos.utilities import errors, shell


if not groups.get_system("ssl-cert"):
    groups.SystemGroup("ssl-cert").add()
gid = groups.get_system("ssl-cert").gid


class Certificate:
    """
    Represents a TLS certificate managed by arkOS.

    Certificates can be generated (self-signed), generated from Let's Encrypt
    CA, or installed from external sources. When certificates are self-signed,
    they are accompanied by generated certificate authorities allowing client
    trust for the root domain in question.

    ``Assign`` objects that are sent to/from this class look like this:

    Websites:
        {"type": "website", "id": "mysite", "name": "mysite"}

    Apps:
        {"type": "app", "id": "xmpp_example.com", "aid": "xmpp",
         "sid": "example.com", "name": "Chat Server (example.com)"}
    """
    def __init__(
            self, id_="", domain="", cert_path="",
            key_path="", keytype="", keylength=0,
            assigns=[], expiry=None, sha1="", md5=""):
        """
        Initialize the Certificate object.

        :param str id_: Certificate name
        :param str domain: Domain the certificate is associated to
        :param str cert_path: Path to the certificate file on disk
        :param str key_path: Path to the certificate's key file on disk
        :param str keytype: Key type (e.g. RSA or DSA)
        :param int keylength: Key bitlength (e.g. 2048, 4096, etc)
        :param list assigns: Assign objects of associated apps/sites
        :param str expiry: ISO-8601 timestamp of certificate expiry
        :param str sha1: SHA-1 hash
        :param str md5: MD5 hash
        """
        self.id = id_
        self.domain = domain
        self.cert_path = cert_path
        self.key_path = key_path
        self.keytype = keytype
        self.keylength = keylength
        self.assigns = assigns
        self.expiry = expiry
        self.sha1 = sha1
        self.md5 = md5

    def assign(self, assign):
        """
        Assign a TLS certificate to a website or service.

        :param dict assign: ``Assign`` object to assign
        :returns: self
        """
        signals.emit("certificates", "pre_assign", (self, assign))
        nginx_reload = False
        if assign["type"] == "genesis":
            config.set("genesis", "cert_file", self.cert_path)
            config.set("genesis", "cert_key", self.key_path)
            config.set("genesis", "ssl", True)
            config.save()
            self.assigns.append(assign)
        elif assign["type"] == "website":
            w = websites.get(assign["id"])
            w.cert = self
            w.ssl_enable()
            self.assigns.append(assign)
            nginx_reload = True
        else:
            d = applications.get(assign["aid"]).ssl_enable(self, assign["sid"])
            self.assigns.append(d)
        if nginx_reload:
            websites.nginx_reload()
        signals.emit("certificates", "post_assign", (self, assign))
        return self

    def unassign(self, assign):
        """
        Unassign a TLS certificate from a website or service.

        :param dict assign: ``Assign`` object to unassign
        :returns: self
        """
        signals.emit("certificates", "pre_unassign", (self, assign))
        nginx_reload = False
        if assign["type"] == "website":
            websites.get(assign["id"]).ssl_disable()
            self.assigns.remove(assign)
            nginx_reload = True
        elif assign["type"] == "genesis":
            config.set("genesis", "cert_file", "")
            config.set("genesis", "cert_key", "")
            config.set("genesis", "ssl", False)
            config.save()
            self.assigns.remove(assign)
        else:
            applications.get(assign["aid"]).ssl_disable(assign["sid"])
            self.assigns.remove(assign)
        if nginx_reload:
            websites.nginx_reload()
        signals.emit("certificates", "post_unassign", (self, assign))
        return None

    def remove(self):
        """Remove a certificate from disk."""
        signals.emit("certificates", "pre_remove", self)
        for x in self.assigns:
            self.unassign(x)
        if os.path.exists(self.cert_path):
            os.unlink(self.cert_path)
        if os.path.exists(self.key_path):
            os.unlink(self.key_path)
        storage.certs.remove("certificates", self)
        signals.emit("certificates", "post_remove", self)

    @property
    def as_dict(self):
        """Return certificate metadata as dict."""
        return {
            "id": self.id,
            "domain": self.domain,
            "keytype": self.keytype,
            "keylength": self.keylength,
            "assigns": self.assigns,
            "expiry": self.expiry,
            "sha1": self.sha1,
            "md5": self.md5,
            "is_ready": True
        }

    @property
    def serialized(self):
        """Return serializable certificate metadata as dict."""
        data = self.as_dict
        data["expiry"] = data["expiry"].isoformat()
        return data


class CertificateAuthority:
    """
    Represents a TLS certificate authority managed by arkOS.

    Certificate authorities are created for self-signed certificates
    generated in arkOS, allowing client trust for the root domain in question.
    """
    def __init__(self, id_="", cert_path="", key_path="", expiry=None):
        """
        Initialize the certificate authority object.

        :param str id_: Authority (and domain) name
        :param str cert_path: Path to the certificate file on disk
        :param str key_path: Path to the certificate's key file on disk
        :param str expiry: ISO-8601 timestamp of certificate expiry
        """
        self.id = id_
        self.cert_path = cert_path
        self.key_path = key_path
        self.expiry = expiry
        self.keytype = keytype
        self.keylength = keylength
        self.sha1 = sha1
        self.md5 = md5

    def remove(self):
        """Remove a certificate from disk."""
        if os.path.exists(self.cert_path):
            os.unlink(self.cert_path)
        if os.path.exists(self.key_path):
            os.unlink(self.key_path)
        storage.certs.remove("authorities", self)

    @property
    def as_dict(self):
        """Return certificate metadata as dict."""
        return {
            "id": self.id,
            "keytype": self.keytype,
            "keylength": self.keylength,
            "expiry": self.expiry,
            "sha1": self.sha1,
            "md5": self.md5
        }

    @property
    def serialized(self):
        """Return serializable certificate metadata as dict."""
        data = self.as_dict
        data["expiry"] = data["expiry"].isoformat()
        return data


def get(id_=None, force=False):
    """
    Retrieve arkOS certificate data from the system.

    If the cache is up and populated, certificates are loaded from
    metadata stored there. If not (or ``force`` is set), the certificate
    directory is searched, certificates are loaded and verified.
    This is used on first boot.

    :param str id_: If present, obtain one certificate that matches this ID
    :param bool force: Force a rescan (do not rely on cache)
    :return: Certificate(s)
    :rtype: Certificate or list thereof
    """
    data = storage.certs.get("certificates")
    if not data or force:
        data = scan()
    if id_:
        for x in data:
            if x.id == id_:
                return x
        return None
    return data


def scan():
    """
    Search proper directory for certificates, load them and store metadata.

    :return: list of Certificate objects
    :rtype: list
    """
    certs, assigns = [], {}
    if config.get("genesis", "ssl"):
        gen_cert = config.get("genesis", "cert_file", "")
        ssl = os.path.splitext(os.path.basename(gen_cert))[0]
        if ssl and ssl in assigns:
            assigns[ssl].append({"type": "genesis", "id": "genesis",
                                 "name": "arkOS Genesis/API"})
        elif ssl:
            assigns[ssl] = [{"type": "genesis", "id": "genesis",
                             "name": "arkOS Genesis/API"}]
    for x in applications.get(installed=True):
        if hasattr(x, "ssl"):
            for ssl, data in x.ssl.get_ssl_assigned():
                if ssl in assigns:
                    assigns[ssl] += data
                else:
                    assigns[ssl] = []
                    assigns[ssl].append(data)
    if not os.path.exists(config.get("certificates", "cert_dir")):
        os.makedirs(config.get("certificates", "cert_dir"))
    if not os.path.exists(config.get("certificates", "key_dir")):
        os.makedirs(config.get("certificates", "key_dir"))
    cert_glob = os.path.join(config.get("certificates", "cert_dir"), "*.crt")
    for x in glob.glob(cert_glob):
        id_ = os.path.splitext(os.path.basename(x))[0]
        with open(x, "rb") as f:
            crt = x509.load_pem_x509_certificate(f.read(), default_backend())
        key_path = os.path.join(config.get("certificates", "key_dir"),
                                "{0}.key".format(id_))
        with open(key_path, "rb") as f:
            key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        sha1 = binascii.hexlify(crt.fingerprint(hashes.SHA1())).decode()
        md5 = binascii.hexlify(crt.fingerprint(hashes.MD5())).decode()
        sha1 = ":".join([sha1[i:i+2].upper() for i in range(0, len(sha1), 2)])
        md5 = ":".join([md5[i:i+2].upper() for i in range(0, len(md5), 2)])
        kt = "RSA" if isinstance(key.public_key(), rsa.RSAPublicKey) else "DSA"
        common_name = crt.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        c = Certificate(id_=id_, cert_path=x, key_path=key_path,
                        keytype=kt, keylength=key.key_size,
                        domain=common_name[0].value,
                        assigns=assigns.get(id_, []),
                        expiry=crt.not_valid_after,
                        sha1=sha1, md5=md5)
        certs.append(c)
    storage.certs.set("certificates", certs)
    return certs


def get_authorities(id_=None, force=False):
    """
    Retrieve arkOS certificate authority data from the system.

    If the cache is up and populated, certificates are loaded from
    metadata stored there. If not (or ``force`` is set), the certificate
    directory is searched, certificates are loaded and verified.
    This is used on first boot.

    :param str id: If present, obtain one certificate that matches this ID
    :param bool force: Force a rescan (do not rely on cache)
    :return: CertificateAuthority(s)
    :rtype: CertificateAuthority or list thereof
    """
    data = storage.certs.get("authorities")
    if not data or force:
        data = scan_authorities()
    if id_:
        for x in data:
            if x.id == id_:
                return x
        return None
    return data


def scan_authorities():
    """
    Search proper directory for certificates, load them and store metadata.

    :return: list of CertificateAuthority objects
    :rtype: list
    """
    certs = []
    ca_cert_dir = config.get("certificates", "ca_cert_dir")
    ca_key_dir = config.get("certificates", "ca_key_dir")
    if not os.path.exists(ca_cert_dir):
        os.makedirs(ca_cert_dir)
    if not os.path.exists(ca_key_dir):
        os.makedirs(ca_key_dir)
    for x in glob.glob(os.path.join(ca_cert_dir, "*.pem")):
        id_ = os.path.splitext(os.path.split(x)[1])[0]
        with open(x, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        key_path = os.path.join(ca_key_dir, "{0}.key".format(id_))
        with open(key_path, "rb") as f:
            with open(key_path, "rb") as f:
                key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
        sha1 = binascii.hexlify(cert.fingerprint(hashes.SHA1())).decode()
        md5 = binascii.hexlify(cert.fingerprint(hashes.MD5())).decode()
        kt = "RSA" if isinstance(key.public_key(), rsa.RSAPublicKey) else "DSA"
        ca = CertificateAuthority(id, x, key_path, cert.not_valid_after,
                                  kt, key.key_size, sha1, md5)
        certs.append(ca)
    storage.certs.set("authorities", certs)
    return certs


def generate_dh_params(path, size=2048):
    """
    Create and save Diffie-Hellman parameters.

    :param str path: File path to save to
    :param int size: Key size
    """
    s = shell("openssl dhparam {0} -out {1}".format(size, path))
    if s["code"] != 0:
        emsg = "Failed to generate Diffie-Hellman parameters"
        logger.error("Certificates", s["stderr"].decode())
        raise errors.OperationFailedError(emsg)
    os.chown(path, -1, gid)
    os.chmod(path, 0o750)


def upload_certificate(
        id_, cert, key, chain="", dhparams="/etc/arkos/ssl/dh_params.pem",
        nthread=NotificationThread()):
    """
    Create and save a new certificate from an external file.

    :param str id_: Name to assign certificate
    :param str cert: Certificate as string (PEM format)
    :param str key: Key as string (PEM format)
    :param str chain: Chain as string (PEM format)
    :param NotificationThread nthread: notification thread to use
    :returns: Certificate that was imported
    :rtype: Certificate
    """
    nthread.title = "Uploading TLS certificate"

    # Test the certificates are valid
    crt = x509.load_pem_x509_certificate(cert, default_backend())
    ky = serialization.load_pem_private_key(
        key,
        password=None,
        backend=default_backend()
    )
    signals.emit("certificates", "pre_add", id_)

    # Check to see that we have DH params, if not then do that too
    if not os.path.exists(dhparams):
        msg = "Generating Diffie-Hellman parameters..."
        nthread.update(Notification("info", "Certificates", msg))
        generate_dh_params(dhparams)

    # Create actual certificate object
    msg = "Importing certificate..."
    nthread.update(Notification("info", "Certificates", msg))
    cert_dir = config.get("certificates", "cert_dir")
    key_dir = config.get("certificates", "key_dir")
    sha1 = binascii.hexlify(crt.fingerprint(hashes.SHA1())).decode()
    md5 = binascii.hexlify(crt.fingerprint(hashes.MD5())).decode()
    kt = "RSA" if isinstance(ky.public_key(), rsa.RSAPublicKey) else "DSA"
    common_name = crt.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    c = Certificate(id_=id_,
                    cert_path=os.path.join(cert_dir, "{0}.crt".format(id_)),
                    key_path=os.path.join(key_dir, "{0}.key".format(id_)),
                    keytype=kt, keylength=ky.key_size,
                    domain=common_name, expiry=crt.not_valid_after,
                    sha1=sha1, md5=md5)

    # Save certificate, key and chainfile (if applicable) to files
    # and set perms
    with open(c.cert_path, "wb") as f:
        f.write(cert)
        if chain:
            f.write("\n") if not cert.endswith("\n") else None
            f.write(chain)
    with open(c.key_path, "wb") as f:
        f.write(key)
    os.chown(c.cert_path, -1, gid)
    os.chmod(c.cert_path, 0o660)
    os.chown(c.key_path, -1, gid)
    os.chmod(c.key_path, 0o660)
    storage.certs.add("certificates", c)
    signals.emit("certificates", "post_add", c)
    msg = "Certificate imported successfully"
    nthread.complete(Notification("success", "Certificates", msg))
    return c


def generate_certificate(
        id_, domain, country, state="", locale="", email="", keytype="RSA",
        keylength=2048, dhparams="/etc/arkos/ssl/dh_params.pem",
        nthread=NotificationThread()):
    """
    Generate and save a new self-signed certificate.

    If this domain has no prior self-signed certificates, a new
    CertificateAuthority is also generated to sign this certificate.

    :param str id_: Name to assign certificate
    :param str domain: Domain name to associate with (subject CN)
    :param str country: Two-letter country code (e.g. 'US' or 'CA')
    :param str state: State or province
    :param str locale: City, town or locale
    :param str email: Contact email for user
    :param str keytype: Key type. One of "RSA" or "DSA"
    :param int keylength: Key length. 2048, 4096, etc.
    :param NotificationThread nthread: notification thread to use
    :returns: Certificate that was generated
    :rtype: Certificate
    """
    try:
        return _generate_certificate(
            id, domain, country, state, locale, email, keytype, keylength,
            dhparams, nthread)
    except Exception as e:
        nthread.complete(Notification("error", "Certificates", str(e)))
        raise


def _generate_certificate(
        id, domain, country, state, locale, email, keytype, keylength,
        dhparams, nthread):
    nthread.title = "Generating TLS certificate"

    signals.emit("certificates", "pre_add", id)

    # Check to see that we have a CA ready; if not, generate one
    basehost = ".".join(domain.split(".")[-2:])
    ca = get_authorities(id=basehost)
    if not ca:
        msg = "Generating certificate authority..."
        nthread.update(Notification("info", "Certificates", msg))
        ca = generate_authority(basehost, nthread)
    with open(ca.cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with open(ca.key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )

    # Check to see that we have DH params, if not then do that too
    if not os.path.exists(dhparams):
        msg = ("Generating Diffie-Hellman parameters. "
               "This may take a few minutes...")
        nthread.update(Notification("info", "Certificates", msg))
        generate_dh_params(dhparams)

    # Generate private key and create X509 certificate, then set options
    msg = "Generating certificate..."
    nthread.update(Notification("info", "Certificates", msg))
    cert_path = os.path.join(config.get("certificates", "cert_dir"),
                             "{0}.crt".format(id_))
    key_path = os.path.join(config.get("certificates", "key_dir"),
                            "{0}.key".format(id_))
    kt = dsa if keytype == "DSA" else rsa

    key = kt.generate_private_key(
        public_exponent=65537,
        key_size=keylength,
        backend=default_backend()
    )
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state or ""),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locale or ""),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"arkOS Servers"),
        x509.NameAttribute(NameOID.COMMON_NAME, domain),
    ])
    cert = x509.CertificateBuilder()
    cert = cert.subject_name(subject)
    cert = cert.issuer_name(ca_cert.issuer)
    cert = cert.serial_number(int.from_bytes(os.urandom(20), "big") >> 1)
    cert = cert.public_key(key.public_key())
    cert = cert.not_valid_before(datetime.datetime.utcnow())
    cert = cert.not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=730)
    )
    cert = cert.sign(ca_key, hashes.SHA256(), default_backend())
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    os.chown(cert_path, -1, gid)
    os.chmod(cert_path, 0o660)
    os.chown(key_path, -1, gid)
    os.chmod(key_path, 0o660)

    # Create actual certificate object
    sha1 = binascii.hexlify(cert.fingerprint(hashes.SHA1())).decode()
    md5 = binascii.hexlify(cert.fingerprint(hashes.MD5())).decode()
    sha1 = ":".join([sha1[i:i+2].upper() for i in range(0, len(sha1), 2)])
    md5 = ":".join([md5[i:i+2].upper() for i in range(0, len(md5), 2)])
    c = Certificate(id, domain, cert_path, key_path, keytype, keylength,
                    [], cert.not_valid_after, sha1, md5)
    storage.certs.add("certificates", c)
    signals.emit("certificates", "post_add", c)
    msg = "Certificate generated successfully"
    nthread.complete(Notification("success", "Certificates", msg))
    return c


def generate_authority(domain, nthread=NotificationThread()):
    """
    Generate and save a new certificate authority for signing.

    :param str domain: Domain name to use for certificate authority
    :returns: Certificate authority
    :rtype: CertificateAuthority
    """
    try:
        return _generate_authority(domain)
    except Exception as e:
        nthread.complete(Notification("error", "Certificates", str(e)))
        raise


def _generate_authority(domain):
    ca_cert_dir = config.get("certificates", "ca_cert_dir")
    ca_key_dir = config.get("certificates", "ca_key_dir")
    cert_path = os.path.join(ca_cert_dir, "{0}.pem".format(domain))
    key_path = os.path.join(ca_key_dir, "{0}.key".format(domain))
    ca = CertificateAuthority(
        domain, cert_path, key_path, keytype="RSA", keylength=2048)

    # Generate private key and create X509 certificate, then set options
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"arkOS Servers"),
        x509.NameAttribute(NameOID.COMMON_NAME, domain)
    ])
    cert = x509.CertificateBuilder()
    cert = cert.subject_name(subject)
    cert = cert.issuer_name(issuer)
    cert = cert.serial_number(int.from_bytes(os.urandom(20), "big") >> 1)
    cert = cert.public_key(key.public_key())
    cert = cert.not_valid_before(datetime.datetime.utcnow())
    cert = cert.not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=1825)
    )
    cert = cert.add_extension(
        x509.BasicConstraints(ca=True, path_length=0),
        critical=True
    )
    cert = cert.add_extension(
        x509.KeyUsage(
            True, False, False, False, False, True, True, False, False),
        critical=True
    )
<<<<<<< HEAD
    cert.add_extension(
        x509.SubjectKeyIdentifier(cert.public_key()),
=======
    cert = cert.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
        critical=False
    )
    cert = cert.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
>>>>>>> c5b4278822af43eaec8fa17f8ec3b36b3f3ee976
        critical=False
    )
    cert = cert.sign(key, hashes.SHA256(), default_backend())
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    os.chmod(cert_path, 0o660)

    ca.expiry = cert.not_valid_after
    sha1 = binascii.hexlify(cert.fingerprint(hashes.SHA1())).decode()
    md5 = binascii.hexlify(cert.fingerprint(hashes.MD5())).decode()
    sha1 = ":".join([sha1[i:i+2].upper() for i in range(0, len(sha1), 2)])
    md5 = ":".join([md5[i:i+2].upper() for i in range(0, len(md5), 2)])
    ca.sha1 = sha1
    ca.md5 = md5
    storage.certs.add("authorities", ca)
    return ca
