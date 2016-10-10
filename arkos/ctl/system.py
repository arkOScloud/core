# -*- coding: utf-8 -*-
import click

from arkos import config, logger, version
from arkos.system import stats as statistics, sysconfig
from arkos.utilities import shell, detect_architecture
from arkos.ctl.utilities import CLIException


@click.group(name='sys')
def system():
    """System commands"""
    arch = detect_architecture()
    config.set("enviro", "version", version)
    config.set("enviro", "arch", arch[0])
    config.set("enviro", "board", arch[1])


@system.command()
def shutdown():
    """Shutdown the system now"""
    sysconfig.shutdown()
    logger.success('ctl:system:shutdown', 'Shutdown initiated')


@system.command()
def reboot():
    """Reboot the system now"""
    sysconfig.reboot()
    logger.success('ctl:system:reboot', 'Reboot initiated')


@system.command(name='stat')
def stats():
    """Show system statistics"""
    try:
        data = statistics.get_all()
        for x in list(data.keys()):
            click.echo("{0}: {1}".format(x, data[x]))
    except Exception as e:
        raise CLIException(str(e))


@system.command(name='version')
def show_version():
    """Show version and diagnostic details"""
    click.echo(shell("uname -a")["stdout"].decode().rstrip("\n"))
    click.echo(
        click.style(" * arkOS server version: ", fg="yellow") +
        config.get("enviro", "version", "Unknown")
    )
    click.echo(
        click.style(" * Arch / Board: ", fg="yellow") +
        config.get("enviro", "arch", "Unknown") + " / " +
        config.get("enviro", "board", "Unknown")
    )
