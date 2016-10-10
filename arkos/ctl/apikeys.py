# -*- coding: utf-8 -*-
"""Relates to commands for management of API keys."""
import click

from arkos import secrets, logger
from arkos.utilities import genAPIKey
from arkos.ctl.utilities import CLIException


@click.group()
def keys():
    """API Keys commands."""
    pass


@keys.command(name='list')
def list_keys():
    """List all API keys."""
    try:
        keys = secrets.get_all("api-keys")
        if not keys:
            logger.info('ctl:keys:list', 'No keys found')
            return
        llen = len(sorted(keys, key=lambda x: len(x["user"]))[-1].name)
        for x in keys:
            click.echo(
                click.style(
                    '{name: <45}'.format(name=x["key"]),
                    fg="white", bold=True) +
                click.style(
                    '{name: <{fill}}'.format(name=x["user"], fill=llen + 3),
                    fg="green") + "   " +
                click.style(x["comment"], fg="yellow")
            )
    except Exception as e:
        raise CLIException(str(e))


@keys.command()
@click.option("--comment", default="arkOS-CLI",
              help="Comment for the API key to have")
@click.argument("user")
def create(user, comment):
    """Create a new API key."""
    try:
        key = genAPIKey()
        kdata = {"key": key, "user": user, "comment": comment}
        secrets.append("api-keys", kdata)
        secrets.save()
        smsg = "Added new API key for {} with comment {}".format(user, comment)
        logger.success('ctl:keys:create', smsg)
        logger.info('ctl:keys:create', key)
    except Exception as e:
        raise CLIException(str(e))


@keys.command()
@click.argument("key")
def revoke(key):
    """Revoke an API key."""
    try:
        data = secrets.get_all("api-keys")
        for x in data:
            if x["key"] == key:
                data.remove(x)
                secrets.save()
                break
        logger.info('ctl:keys:revoke', 'API key revoked')
    except Exception as e:
        raise CLIException(str(e))
