# -*- coding: utf-8 -*-
import click

from arkos import logger
from arkos.system import network
from arkos.utilities import str_fsize
from arkos.ctl.utilities import CLIException


@click.group()
def net():
    """Network commands"""
    pass


@net.command(name='list')
def list_networks():
    """List system networks"""
    try:
        data = [x.serialized for x in network.get_connections()]
        for x in data:
            click.echo(
                click.style(x["id"], fg="white", bold=True) +
                click.style(
                    " (" + x["config"]["connection"].capitalize() + ")",
                    fg="green"
                )
            )
            click.echo(
                click.style(" * Addressing: ", fg="yellow") +
                ("DHCP" if x["config"]["ip"] == "dhcp" else x["config"]["ip"])
            )
            click.echo(
                click.style(" * Interface: ", fg="yellow") +
                x["config"]["interface"]
            )
            click.echo(
                click.style(" * Enabled: ", fg="yellow") +
                ("Yes" if x["enabled"] else "No")
            )
            click.echo(
                click.style(" * Connected: ", fg="yellow") +
                ("Yes" if x["connected"] else "No")
            )
    except Exception as e:
        raise CLIException(str(e))


@net.command(name='ifaces')
def list_interfaces():
    """List system network interfaces"""
    try:
        data = network.get_interfaces()
        for x in data:
            click.echo(
                click.style(x.id, fg="white", bold=True) +
                click.style(" (" + x.itype.capitalize() + ")", fg="green")
            )
            click.echo(
                click.style(" * Rx/Tx: ", fg="yellow") +
                "{0} / {1}".format(str_fsize(x.rx), str_fsize(x.tx))
            )
            click.echo(
                click.style(" * Connected: ", fg="yellow") +
                ("Yes" if x.up else "No")
            )
            if x.ip:
                click.echo(
                    click.style(" * Address(es): ", fg="yellow") +
                    ", ".join([y["addr"]+"/"+y["netmask"] for y in x.ip])
                )
    except Exception as e:
        raise CLIException(str(e))


@net.command()
@click.argument("id")
def connect(id):
    """Connect to a network"""
    try:
        n = network.get(id)
        n.connect()
        logger.success('ctl:net:connect', 'Connected {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@net.command()
@click.argument("id")
def disconnect(id):
    """Disconnect from a network"""
    try:
        n = network.get(id)
        n.disconnect()
        logger.success('ctl:net:disconnect', 'Disconnected {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@net.command()
@click.argument("id")
def enable(id):
    """Enable connection to a network on boot"""
    try:
        n = network.get(id)
        n.enable()
        logger.success('ctl:net:enable', 'Enabled {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@net.command()
@click.argument("id")
def disable(id):
    """Disable connection to a network on boot"""
    try:
        n = network.get(id)
        n.disable()
        logger.success('ctl:net:disable', 'Disabled {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@net.command()
@click.argument("id")
def delete(id):
    """Delete a network connection"""
    try:
        n = network.get(id)
        n.remove()
        logger.success('ctl:net:delete', 'Deleted {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))
