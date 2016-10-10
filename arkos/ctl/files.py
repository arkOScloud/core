# -*- coding: utf-8 -*-
"""Relates to the management of files."""
import click

from arkos import shared_files, logger
from arkos.utilities import random_string
from arkos.ctl.utilities import CLIException


@click.group(name='link')
def links():
    """Shared file commands."""
    pass


@click.group(name='file')
def files():
    """File commands."""
    pass


@links.command(name='list')
def list_shares():
    """List all fileshare links."""
    try:
        data = shared_files.get()
        for x in data:
            smsg = click.style(x.path, fg="white", bold=True)
            click.echo(smsg + " ({0})".format(x.id))
            s = "Never" if not x.expires else x.expires_at.strftime("%c")
            click.echo(click.style(" * Expires: ", fg="yellow") + s)
    except Exception as e:
        raise CLIException(str(e))


@links.command(name='create')
@click.argument("path")
@click.option("--expires", default=0, help="Unix timestamp for when the share "
              "link should expire, or 0 to last forever")
def create_share(path, expires):
    """Create a fileshare link."""
    try:
        share = shared_files.Share(random_string(), path, expires)
        share.add()
        logger.success('ctl:links:create', 'Created link')
        smsg = "Link is your external server address, plus: /shared/{0}"
        logger.info('ctl:links:create', smsg.format(share.id))
    except Exception as e:
        raise CLIException(str(e))


@links.command(name='update')
@click.argument("id")
@click.option("--expires", default=0, help="Unix timestamp for when the share "
              "link should expire, or 0 to last forever")
def update_share(id, expires):
    """Update a fileshare link's expiration."""
    try:
        share = shared_files.get(id)
        share.update_expiry(expires)
        logger.success('ctl:links:update', 'Updated share {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@links.command(name='delete')
@click.argument("id")
def remove_share(id):
    """Disable a fileshare link."""
    try:
        share = shared_files.get(id)
        share.delete()
        logger.success('ctl:links:delete', 'Deleted share {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@files.command()
@click.argument("path")
def edit(path):
    """Open a file in your default editor."""
    try:
        with open(path, "r") as f:
            out = click.edit(f.read())
        if out:
            with open(path, "w") as f:
                f.write(out)
            logger.info('ctl:files:edit', 'File saved to {0}'.format(path))
        else:
            logger.info('ctl:files:edit', 'File not saved')
    except Exception as e:
        raise CLIException(str(e))
