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
from cryptography.hazmat.primitives.asymmetric import dsa, rsa, ec
import datetime
from free_tls_certificates import client as leclient
import glob
import os
import shutil
import time

from arkos import config, signals, storage, websites, applications, logger
from arkos.messages import Notification, NotificationThread
from arkos.system import groups
from arkos.utilities import errors, shell


if not groups.get_system("ssl-cert"):
    groups.SystemGroup("ssl-cert").add()
gid = groups.get_system("ssl-cert").gid

LETSENCRYPT_LIVE = "https://acme-v01.api.letsencrypt.org/directory"
LETSENCRYPT_STAGING = "https://acme-staging.api.letsencrypt.org/directory"


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
            self, id="", domain="", cert_path="", key_path="", keytype="",
            keylength=0, assigns=[], expiry=None, sha1="", md5="",
            is_acme=False):
        """
        Initialize the Certificate object.

        :param str id: Certificate name
        :param str domain: Domain the certificate is associated to
        :param str cert_path: Path to the certificate file on disk
        :param str key_path: Path to the certificate's key file on disk
        :param str keytype: Key type (e.g. RSA or DSA)
        :param int keylength: Key bitlength (e.g. 2048, 4096, etc)
        :param list assigns: Assign objects of associated apps/sites
        :param str expiry: ISO-8601 timestamp of certificate expiry
        :param str sha1: SHA-1 hash
        :param str md5: MD5 hash
        :param bool is_acme: Is this a Let's Encrypt certificate?
        """
        self.id = id
        self.domain = domain
        self.cert_path = cert_path
        self.key_path = key_path
        self.keytype = keytype
        self.keylength = keylength
        self.assigns = assigns
        self.expiry = expiry
        self.sha1 = sha1
        self.md5 = md5
        self.is_acme = is_acme

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
        if self.is_acme:
            with open("/etc/cron.d/arkos-acme-renew", "r") as f:
                data = f.readlines()
            for i, x in enumerate(data):
                if "free_tls_certificate {0} /etc".format(self.domain) in x:
                    data.remove(x)
            with open("/etc/cron.d/arkos-acme-renew", "w") as f:
                f.writelines(data)
            for x in websites.get():
                if x.domain == self.domain:
                    break
            else:
                orig = os.path.join("/etc/nginx/sites-available", self.domain)
                targ = os.path.join("/etc/nginx/sites-enabled", self.domain)
                sd = config.get("websites", "site_dir")
                if os.path.exists(orig):
                    os.unlink(orig)
                if os.path.exists(targ):
                    os.unlink(targ)
                if os.path.exists(os.path.join(sd, self.domain)):
                    shutil.rmtree(os.path.join(sd, self.domain))
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
            "is_acme": self.is_acme,
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

    def __init__(self, id="", cert_path="", key_path="", expiry=None,
                 keytype="", keylength=0, sha1="", md5=""):
        """
        Initialize the certificate authority object.

        :param str id: Authority (and domain) name
        :param str cert_path: Path to the certificate file on disk
        :param str key_path: Path to the certificate's key file on disk
        :param str expiry: ISO-8601 timestamp of certificate expiry
        :param str keytype: Key type (e.g. RSA or DSA)
        :param int keylength: Key bitlength (e.g. 2048, 4096, etc)
        :param str sha1: SHA-1 hash
        :param str md5: MD5 hash
        """
        self.id = id
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


def get(id=None, force=False):
    """
    Retrieve arkOS certificate data from the system.

    If the cache is up and populated, certificates are loaded from
    metadata stored there. If not (or ``force`` is set), the certificate
    directory is searched, certificates are loaded and verified.
    This is used on first boot.

    :param str id: If present, obtain one certificate that matches this ID
    :param bool force: Force a rescan (do not rely on cache)
    :return: Certificate(s)
    :rtype: Certificate or list thereof
    """
    data = storage.certs.get("certificates")
    if not data or force:
        data = scan()
    if id:
        for x in data:
            if x.id == id:
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
    for cert_path in glob.glob(cert_glob):
        id = os.path.splitext(os.path.basename(cert_path))[0]
        key_path = os.path.join(
            config.get("certificates", "key_dir"), "{0}.key".format(id))
        certs.append(_scan_a_cert(id, cert_path, key_path, assigns))

    acmedir = config.get(
        "certificates", "acme_dir", "/etc/arkos/ssl/acme/certs")
    if not os.path.exists(acmedir):
        os.makedirs(acmedir)

    le_cert_glob = os.path.join(acmedir, "*/cert.pem")
    for cert_path in glob.glob(le_cert_glob):
        basedir = os.path.dirname(cert_path)
        id = os.path.basename(basedir)
        key_path = os.path.join(basedir, "privkey.pem")
        certs.append(_scan_a_cert(id, cert_path, key_path, assigns, True))
    storage.certs.set("certificates", certs)
    return certs


def _scan_a_cert(id, cert_path, key_path, assigns, is_acme=False):
    with open(cert_path, "rb") as f:
        crt = x509.load_pem_x509_certificate(f.read(), default_backend())
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
    return Certificate(
        id=id, cert_path=cert_path, key_path=key_path, keytype=kt,
        keylength=key.key_size, domain=common_name[0].value,
        assigns=assigns.get(id, []), expiry=crt.not_valid_after, sha1=sha1,
        md5=md5, is_acme=is_acme)


def get_authorities(id=None, force=False):
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
    if id:
        for x in data:
            if x.id == id:
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
        id = os.path.splitext(os.path.split(x)[1])[0]
        with open(x, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        key_path = os.path.join(ca_key_dir, "{0}.key".format(id))
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
        id, cert, key, chain="", dhparams="/etc/arkos/ssl/dh_params.pem",
        nthread=NotificationThread()):
    """
    Create and save a new certificate from an external file.

    :param str id: Name to assign certificate
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
    signals.emit("certificates", "pre_add", id)

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
    c = Certificate(id=id,
                    cert_path=os.path.join(cert_dir, "{0}.crt".format(id)),
                    key_path=os.path.join(key_dir, "{0}.key".format(id)),
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


def request_acme_certificate(domain, webroot, nthread=NotificationThread()):
    """
    Request, validate and save a new ACME certificate from Let's Encrypt CA.

    :param str domain: Domain name to associate with (subject CN)
    :param str webroot: Path to root of web directory, to place .well-known
    :param NotificationThread nthread: notification thread to use
    """
    try:
        return _request_acme_certificate(domain, webroot, nthread)
    except Exception as e:
        nthread.complete(Notification("error", "Certificates", str(e)))
        raise


def _request_acme_certificate(domain, webroot, nthread):
    nthread.title = "Requesting ACME certificate"
    signals.emit("certificates", "pre_add", id)
    domains = [domain]

    acme_dir = config.get("certificates", "acme_dir", "/etc/arkos/ssl/acme")
    cert_dir = os.path.join(acme_dir, "certs", domain)
    cert_path = os.path.join(cert_dir, "cert.pem")
    key_path = os.path.join(cert_dir, "privkey.pem")

    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)

    smsg = "Requesting certificate from Let's Encrypt CA..."
    nthread.update(Notification("info", "Certificates", smsg))
    agree_to_tos = None
    has_written_files = False
    while True:
        try:
            leclient.issue_certificate(
                domains,
                acme_dir,
                acme_server=LETSENCRYPT_STAGING,
                certificate_file=cert_path,
                private_key_file=key_path,
                agree_to_tos_url=agree_to_tos)
            break
        except leclient.NeedToAgreeToTOS as e:
            agree_to_tos = e.url
            continue
        except leclient.NeedToTakeAction as e:
            if not has_written_files:
                if not os.path.exists(webroot):
                    os.makedirs(webroot)
                for x in e.actions:
                    fn = os.path.join(webroot, x.file_name)
                    with open(fn, 'w') as f:
                        f.write(x.contents)
                has_written_files = True
                continue
            else:
                raise errors.InvalidConfigError(
                    "Requesting a certificate failed - it doesn't appear your "
                    "requested domain's DNS is pointing to your server, or "
                    "there was a port problem. Please check these things and "
                    "try again.")
        except leclient.WaitABit as e:
            while e.until_when > datetime.datetime.now():
                until = e.until_when - datetime.datetime.now()
                until_secs = int(round(until.total_seconds()))
                if until_secs > 300:
                    raise errors.InvalidConfigError(
                        "Requesting a certificate failed - LE rate limiting "
                        "detected, for a period of more than five minutes. "
                        "Please try again later."
                    )
                nthread.update(
                    Notification(
                        "warning", "Certificates", "LE rate limiting detected."
                        " Will reattempt in {0} seconds".format(until_secs))
                    )
                time.sleep(until_secs)
            continue
        except leclient.InvalidDomainName:
            raise errors.InvalidConfigError(
                "Requesting a certificate failed - invalid domain name"
            )
        except leclient.RateLimited:
            raise errors.InvalidConfigError(
                "Requesting a certificate failed - LE is refusing to issue "
                "more certificates to you for this domain. Please choose "
                "another domain or try again another time."
            )

    os.chown(cert_path, -1, gid)
    os.chown(key_path, -1, gid)
    os.chmod(cert_path, 0o750)
    os.chmod(key_path, 0o750)

    with open(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with open(key_path, "rb") as f:
        key = serialization.load_pem_private_key(
            f.read(), password=None, backend=default_backend()
        )
    sha1 = binascii.hexlify(cert.fingerprint(hashes.SHA1())).decode()
    md5 = binascii.hexlify(cert.fingerprint(hashes.MD5())).decode()
    sha1 = ":".join([sha1[i:i+2].upper() for i in range(0, len(sha1), 2)])
    md5 = ":".join([md5[i:i+2].upper() for i in range(0, len(md5), 2)])
    if isinstance(key.public_key(), rsa.RSAPublicKey):
        ktype = "RSA"
    elif isinstance(key.public_key(), dsa.DSAPublicKey):
        ktype = "DSA"
    elif isinstance(key.public_key(), ec.EllipticCurvePublicKey):
        ktype = "EC"
    else:
        ktype = "Unknown"
    ksize = key.key_size
    c = Certificate(domain, domain, cert_path, key_path, ktype, ksize,
                    [], cert.not_valid_after, sha1, md5, is_acme=True)
    storage.certs.add("certificates", c)

    with open("/etc/cron.d/arkos-acme-renew", "a") as f:
        fln = ("30 3 * * * free_tls_certificate {0} {1} {2} {3} {4} "
               ">> /var/log/acme-renew.log\n")
        f.write(fln.format(
            " ".join(domains), key_path, cert_path, webroot, acme_dir
        ))

    signals.emit("certificates", "post_add", c)
    msg = "Certificate issued successfully"
    nthread.complete(Notification("success", "Certificates", msg))
    return c


def generate_certificate(
        id, domain, country, state="", locale="", email="", keytype="RSA",
        keylength=2048, dhparams="/etc/arkos/ssl/dh_params.pem",
        nthread=NotificationThread()):
    """
    Generate and save a new self-signed certificate.

    If this domain has no prior self-signed certificates, a new
    CertificateAuthority is also generated to sign this certificate.

    :param str id: Name to assign certificate
    :param str domain: Domain name to associate with (subject CN)
    :param str country: Two-letter country code (e.g. 'US' or 'CA')
    :param str state: State or province
    :param str locale: City, town or locale
    :param str email: Contact email for user
    :param str keytype: Key type. One of "RSA" or "DSA"
    :param int keylength: Key length. 2048, 4096, etc.
    :param str dhparams: Path to dh_params file on disk
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
                             "{0}.crt".format(id))
    key_path = os.path.join(config.get("certificates", "key_dir"),
                            "{0}.key".format(id))
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
    cert = cert.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
        critical=False
    )
    cert = cert.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
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
