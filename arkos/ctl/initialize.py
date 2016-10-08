import click
import grp
import os
import pwd
import shutil

from arkos import logger, secrets
from arkos.utilities import shell, random_string, hashpw
from arkos.ctl.utilities import abort_if_false, CLIException


@click.group()
def init():
    """
    arkOS distribution initialization commands.

    These commands will perform the initial steps required to get your
    arkOS installation working with certain important system-level packages,
    like LDAP and Redis. You should not use these unless you know what you are
    doing!
    """
    pass


@init.command()
@click.option(
    "--yes", is_flag=True, callback=abort_if_false, expose_value=False,
    prompt='Are you sure you want to initialize configs? Any existing data '
    'will be overwritten.'
)
def configs():
    """Initialize arkOS internal configuration files."""
    if not os.path.exists("/usr/share/arkos/arkos-core/settings.json"):
        raise CLIException(
            "Template files could not be found. Your installation may "
            "be corrupted. Please reinstall the `arkos-core` package."
        )

    logger.info('ctl:init:configs', 'Initializing configuration files')
    if not os.path.exists("/etc/arkos"):
        os.makedirs("/etc/arkos")
    shutil.copy(
        "/usr/share/arkos/arkos-core/settings.json", "/etc/arkos/settings.json"
    )
    with open("/etc/arkos/secrets.json", "w") as f:
        f.write("{}\n")
    with open("/etc/arkos/policies.json", "w") as f:
        f.write("{}\n")
    logger.success('ctl:init:configs', 'Completed')


@init.command()
@click.option(
    "--yes", is_flag=True, callback=abort_if_false, expose_value=False,
    prompt='Are you sure you want to initialize LDAP? Any existing data '
    'will be overwritten.'
)
def ldap():
    """Initialize distribution copy of OpenLDAP."""
    paths = ["slapd.conf", "ldap.conf", "base.ldif"]
    for x in paths:
        if not os.path.exists(os.path.join("/usr/share/arkos/openldap", x)):
            raise CLIException(
                "Template files could not be found. Your installation may "
                "be corrupted. Please reinstall the `arkos-configs` package."
            )

    logger.debug('ctl:init:ldap', 'Stopping daemon: slapd')
    s = shell("systemctl stop slapd")
    if s["code"] != 0:
        raise click.ClickException(s["stderr"].decode())

    logger.info('ctl:init:ldap', 'Cleaning up old LDAP database')
    if os.path.exists("/etc/openldap/slapd.ldif"):
        os.unlink("/etc/openldap/slapd.ldif")
    slapdir = "/etc/openldap/slapd.d"
    for x in os.listdir(slapdir):
        fpath = os.path.join(slapdir, x)
        if os.path.isdir(fpath):
            shutil.rmtree(fpath)
        else:
            os.unlink(fpath)

    logger.info('ctl:init:ldap', 'Installing initial configuration')
    shutil.copy(
        "/usr/share/arkos/openldap/slapd.conf", "/etc/openldap/slapd.conf"
    )
    shutil.copy(
        "/usr/share/arkos/openldap/ldap.conf", "/etc/openldap/ldap.conf"
    )

    if os.path.exists("/usr/share/doc/sudo/schema.OpenLDAP"):
        shutil.copy(
            "/usr/share/doc/sudo/schema.OpenLDAP",
            "/etc/openldap/schema/sudo.schema"
        )
    shutil.copy(
        "/usr/share/arkos/openldap/mailserver.schema",
        "/etc/openldap/schema/mailserver.schema"
    )
    shutil.copy(
        "/usr/share/arkos/openldap/samba.schema",
        "/etc/openldap/schema/samba.schema"
    )

    logger.info('ctl:init:ldap', 'Setting admin password')
    ldap_passwd = random_string(16)
    ldap_pwhash = hashpw(ldap_passwd)
    with open("/etc/openldap/slapd.conf", "r") as f:
        data = f.read()
    data = data.replace("%ROOTPW%", ldap_pwhash)
    with open("/etc/openldap/slapd.conf", "w") as f:
        f.write(data)
    secrets.load("/etc/arkos/secrets.json")
    secrets.set("ldap", ldap_passwd)
    secrets.save()

    logger.info('ctl:init:ldap', 'Generating new LDAP database')
    logger.debug('ctl:init:ldap', 'slapadd slapd.conf')
    shell(
        "slapadd -f /etc/openldap/slapd.conf -F /etc/openldap/slapd.d/",
        stdin=""
    )
    logger.debug('ctl:init:ldap', 'slaptest')
    shell("slaptest -f /etc/openldap/slapd.conf -F /etc/openldap/slapd.d/")
    luid, lgid = pwd.getpwnam("ldap").pw_uid, grp.getgrnam("ldap").gr_gid
    for r, d, f in os.walk("/etc/openldap/slapd.d"):
        for x in d:
            os.chown(os.path.join(r, x), luid, lgid)
        for x in f:
            os.chown(os.path.join(r, x), luid, lgid)
    logger.debug('ctl:init:ldap', 'slapindex')
    shell("slapindex")
    logger.debug('ctl:init:ldap', 'slapadd base.ldif')
    shell("slapadd -l /usr/share/arkos/openldap/base.ldif")
    for r, d, f in os.walk("/var/lib/openldap/openldap-data"):
        for x in d:
            os.chown(os.path.join(r, x), luid, lgid)
        for x in f:
            os.chown(os.path.join(r, x), luid, lgid)

    logger.debug('ctl:init:ldap', 'Restarting daemon: slapd')
    shell("systemctl enable slapd")
    shell("systemctl restart slapd")
    logger.success('ctl:init:ldap', 'Complete')


@init.command()
def nslcd():
    """Initialize distribution PAM integration of OpenLDAP."""
    patchfiles = [
        ("/etc/pam.d/system-auth", "001-add-ldap-to-system-auth.patch"),
        ("/etc/pam.d/su", "002-add-ldap-to-su.patch"),
        ("/etc/pam.d/su-l", "003-add-ldap-to-su-l.patch"),
        ("/etc/pam.d/passwd", "004-add-ldap-to-passwd.patch"),
        ("/etc/pam.d/system-login", "005-add-ldap-to-system-login.patch"),
        ("/etc/nsswitch.conf", "006-add-ldap-to-nsswitch.patch"),
        ("/etc/nslcd.conf", "007-add-ldap-to-nslcd.patch")
    ]
    for x in patchfiles:
        if not os.path.exists(os.path.join("/usr/share/arkos/nslcd", x[1])):
            raise CLIException(
                "Patch files could not be found. Your installation may "
                "be corrupted. Please reinstall the `arkos-configs` package."
            )

    logger.debug('ctl:init:nslcd', 'Stopping daemon: nslcd')
    s = shell("systemctl stop nslcd")
    if s["code"] != 0:
        raise click.ClickException(s["stderr"].decode())

    logger.info('ctl:init:nslcd', 'Patching system files')
    for x in patchfiles:
        shell("patch -N {0} {1}".format(
            x[0], os.path.join("/usr/share/arkos/nslcd", x[1]))
        )

    logger.debug('ctl:init:nslcd', 'Starting daemon: nslcd')
    shell("systemctl enable nslcd")
    shell("systemctl start nslcd")
    logger.success('ctl:init:nslcd', 'Complete')


@init.command()
def redis():
    """Initialize distribution Redis integration."""
    paths = ["arkos-redis.service", "arkos-redis.conf"]
    for x in paths:
        if not os.path.exists(os.path.join("/usr/share/arkos/redis", x)):
            raise CLIException(
                "Template files could not be found. Your installation may "
                "be corrupted. Please reinstall the `arkos-configs` package."
            )

    logger.debug('ctl:init:redis', 'Stopping daemon if exists: arkos-redis')
    shell("systemctl stop arkos-redis")

    logger.info('ctl:init:redis', 'Copying files')
    ruid, rgid = pwd.getpwnam("redis").pw_uid, grp.getgrnam("redis").gr_gid
    shutil.copy(
        "/usr/share/arkos/redis/arkos-redis.conf", "/etc/arkos-redis.conf"
    )
    os.chown("/etc/arkos-redis.conf", ruid, rgid)
    os.chmod("/etc/arkos-redis.conf", 0o660)
    shutil.copy(
        "/usr/share/arkos/redis/arkos-redis.service",
        "/usr/lib/systemd/system/arkos-redis.service"
    )
    os.chmod("/usr/lib/systemd/system/arkos-redis.service", 0o644)

    if not os.path.exists("/var/lib/arkos-redis"):
        os.makedirs("/var/lib/arkos-redis")
    os.chmod("/var/lib/arkos-redis", 0o700)
    os.chown("/var/lib/arkos-redis", ruid, rgid)

    logger.info('ctl:init:redis', 'Setting admin password')
    redis_passwd = random_string(16)
    with open("/etc/arkos-redis.conf", "r") as f:
        data = f.read()
    data = data.replace("%REDISPASS%", redis_passwd)
    with open("/etc/arkos-redis.conf", "w") as f:
        f.write(data)
    secrets.load("/etc/arkos/secrets.json")
    secrets.set("redis", redis_passwd)
    secrets.save()

    logger.debug('ctl:init:redis', 'Starting daemon: arkos-redis')
    shell("systemctl daemon-reload")
    shell("systemctl enable arkos-redis")
    shell("systemctl start arkos-redis")
    logger.success('ctl:init:redis', 'Complete')


@init.command()
def nginx():
    """Initialize default nginx configuration."""
    if not os.path.exists("/usr/share/arkos/nginx.conf"):
        raise CLIException(
            "Template files could not be found. Your installation may "
            "be corrupted. Please reinstall the `arkos-configs` package."
        )

    logger.info('ctl:init:nginx', 'Copying files')
    if not os.path.exists("/srv/http/webapps"):
        os.makedirs("/srv/http/webapps")
    if not os.path.exists("/etc/nginx/sites-available"):
        os.makedirs("/etc/nginx/sites-available")
    if not os.path.exists("/etc/nginx/sites-enabled"):
        os.makedirs("/etc/nginx/sites-enabled")

    shutil.copy(
        "/usr/share/arkos/nginx.conf", "/etc/nginx/nginx.conf"
    )

    logger.debug('ctl:init:nginx', 'Restarting daemon: nginx')
    shell("systemctl enable nginx")
    shell("systemctl restart nginx")
    logger.success('ctl:init:nginx', 'Completed')
