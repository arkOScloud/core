import click
import os

from arkos import config, configs, secrets, policies, logger
from arkos.ctl import apikeys, applications, backups, certificates, databases
from arkos.ctl import files, filesystems, initialize, networks, packages
from arkos.ctl import roles, security, services, system, websites
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
    "--configfile", envvar="ARKOSCTL_CONFIG",
    default="/etc/arkos/settings.json", help="Path to arkOS settings.json file"
)
@click.option(
    "--secretsfile", envvar="ARKOSCTL_SECRETS",
    default="/etc/arkos/secrets.json", help="Path to arkOS secrets.json file"
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
    config.load(configfile, default=configs.DEFAULT_CONFIG)
    secrets.load(secretsfile, default={})
    policies.load(policiesfile, default={})
    logger.add_stream_logger(st="[{levelname}] {comp}: {message}", debug=v)

for x in modgroups:
    cli.add_command(x)


if __name__ == '__main__':
    cli()
