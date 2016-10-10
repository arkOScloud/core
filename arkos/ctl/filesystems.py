# -*- coding: utf-8 -*-
"""Relates to the management of filesystems."""
import click

from arkos import logger
from arkos.system import filesystems
from arkos.utilities import str_fsize
from arkos.ctl.utilities import CLIException


@click.group()
def fs():
    """Filesystem commands."""
    pass


@fs.command(name='list')
def list_filesystems():
    """List filesystems"""
    try:
        data = filesystems.get()
        for x in data:
            click.echo(
                click.style(x.id, fg="white", bold=True) +
                click.style(" (" + x.path + ")", fg="green")
            )
            click.echo(
                click.style(" * Type: ", fg="yellow") +
                "{0} {1}".format(
                    "Physical" if isinstance(filesystems.DiskPartition)
                    else "Virtual",
                    x.fstype
                )
            )
            click.echo(
                click.style(" * Size: ", fg="yellow") +
                str_fsize(x.size)
            )
            click.echo(
                click.style(" * Encrypted: ", fg="white") +
                ("Yes" if x.crypt else "No")
            )
            click.echo(
                click.style(" * Mounted: ", fg="yellow") +
                ("At " + x.mountpoint if x.mountpoint else "No")
            )
    except Exception as e:
        raise CLIException(str(e))


@fs.command()
@click.argument("name")
@click.option("--size", required=True, type=int,
              prompt="Size of the new disk (in MB)",
              help="Size of the new disk (in MB)")
@click.option("--encrypt", is_flag=True, prompt="Encrypt this filesystem?",
              help="Encrypt this filesystem?")
@click.option("--password", help="Password (if encrypted filesystem)")
def create(name, size, encrypt, password):
    """Create a virtual disk."""
    try:
        if encrypt and not password:
            password = click.prompt(
                "Please choose a password for encryption",
                hide_input=True, confirmation_prompt=True)
        fs = filesystems.VirtualDisk(id=name, size=size * 1048576)
        fs.create()
        if encrypt:
            fs.encrypt(password)
    except Exception as e:
        raise CLIException(str(e))


@fs.command()
@click.argument("id")
@click.option("--password", help="Password (if encrypted filesystem)")
def mount(id, password):
    """Mount a filesystem"""
    try:
        fs = filesystems.get(id)
        if fs.crypt and not password:
            password = click.prompt(
                "Please enter your password to mount this filesystem",
                hide_input=True)
        fs.mount(password)
        logger.success('ctl:fs:mount', 'Mounted {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@fs.command()
@click.argument("id")
def umount(id):
    """Unmount a filesystem"""
    try:
        fs = filesystems.get(id)
        fs.umount()
        logger.success('ctl:fs:umount', 'Unmounted {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@fs.command()
@click.argument("id")
def enable(id):
    """Mount a filesystem on boot"""
    try:
        fs = filesystems.get(id)
        fs.enable()
        logger.success('ctl:fs:enable', 'Enabled {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@fs.command()
@click.argument("id")
def disable(id):
    """Disable mounting a filesystem on boot"""
    try:
        fs = filesystems.get(id)
        fs.disable()
        logger.success('ctl:fs:disable', 'Disabled {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@fs.command()
@click.argument("id")
def delete(id):
    """Delete a virtual disk"""
    try:
        fs = filesystems.get(id)
        fs.remove()
        logger.success('ctl:fs:delete', 'Deleted {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))
