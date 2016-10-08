import click
import os
import sys

from arkos import config, secrets, policies, logger, version
from arkos.ctl import apikeys, applications, backups, certificates, databases
from arkos.ctl import files, filesystems, initialize, networks, packages
from arkos.ctl import roles, security, services, system, websites
from arkos.utilities import detect_architecture
from arkos.ctl.utilities import CLIException


modgroups = [
    apikeys.keys,
    applications.app,
    backups.bak,
    certificates.cert,
    databases.db,
    databases.db_users,
    files.files,
    files.links,
    filesystems.fs,
    initialize.init,
    networks.net,
    packages.pkg,
    roles.user,
    roles.group,
    roles.domain,
    security.sec,
    services.svc,
    system.system,
    websites.site
]


@click.group()
@click.option(
    "--configfile", envvar="ARKOSCTL_CONFIG", default="/etc/arkos/settings.json",
    help="Path to arkOS settings.json file"
)
@click.option(
    "--secretsfile", envvar="ARKOSCTL_SECRETS", default="/etc/arkos/secrets.json",
    help="Path to arkOS secrets.json file"
)
@click.option(
    "--policiesfile", envvar="ARKOSCTL_POLICIES",
    default="/etc/arkos/policies.json", help="Path to arkOS policies.json file"
)
@click.option(
    "-v/--verbose", default=False, help="Verbose output"
)
def cli(configfile, secretsfile, policiesfile, v):
    if os.geteuid() != 0:
        raise CLIException(
            "You must run this script as root, or prefixed with `sudo`."
        )
    if len(sys.argv) > 1 and sys.argv[1] != "init":
        config.load(configfile)
        secrets.load(secretsfile)
        policies.load(policiesfile)
    arch = detect_architecture()
    config.set("enviro", "version", version)
    config.set("enviro", "arch", arch[0])
    config.set("enviro", "board", arch[1])
    logger.add_stream_logger(st="[{levelname}] {comp}: {message}", debug=v)

for x in modgroups:
    cli.add_command(x)


if __name__ == '__main__':
    cli()
