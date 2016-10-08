# -*- coding: utf-8 -*-
"""Relates to commands for management of backups."""
import click

from arkos import backup, logger
from arkos.ctl.utilities import CLIException


@click.group(name='backup')
def bak():
    """Backup commands."""
    pass


def _list_backups(bkps):
    if not bkps:
        logger.info('ctl:bak:list', 'No backups found')
    for x in sorted(bkps, key=lambda x: x["time"]):
        imsg = click.style(" (" + x["type"].capitalize() + ")", fg="yellow")
        click.echo(click.style(x["pid"], fg="green", bold=True) + imsg)
        click.echo(
            click.style(" * Backed up on: ", fg="yellow") + x["time"]
        )


@bak.command(name='list')
def list_backups():
    """List all backups."""
    try:
        data = backup.get()
        _list_backups(data)
    except Exception as e:
        raise CLIException(str(e))


@bak.command(name='types')
def backup_types():
    """List types of apps/sites that can create backups."""
    try:
        data = backup.get_able()
        for x in data:
            imsg = click.style("(" + x["type"].capitalize() + ")", fg="yellow")
            click.echo(
                click.style(x["id"], fg="green", bold=True) + " " + imsg
            )
    except Exception as e:
        raise CLIException(str(e))


@bak.command()
@click.argument("appid")
def create(appid):
    """Create a backup."""
    try:
        backup.create(appid)
    except Exception as e:
        raise CLIException(str(e))


@bak.command()
@click.argument("id")
def restore(id):
    """Restore a backup by ID."""
    if "/" not in id:
        raise CLIException("Requires full backup ID with app ID and timestamp")
    id, tsp = id.split("/")
    try:
        b = [x for x in backup.get() if x["id"] == (id + "/" + tsp)][0]
        backup.restore(b)
    except Exception as e:
        raise CLIException(str(e))


@bak.command()
@click.argument("id")
def delete(id):
    """Delete a backup."""
    if "/" not in id:
        excmsg = "Requires full backup ID with app ID and timestamp"
        raise click.ClickException(excmsg)
    id, tsp = id.split("/")
    try:
        backup.remove(id, tsp)
    except Exception as e:
        raise CLIException(str(e))
