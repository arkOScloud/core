# -*- coding: utf-8 -*-
import click

from arkos import conns, logger
from arkos.system import services
from arkos.utilities import shell
from arkos.ctl.utilities import CLIException


@click.group()
def svc():
    """Service commands"""
    conns.connect_services()


@svc.command(name='list')
def list_services():
    """List all services and statuses."""
    try:
        data = []
        svcs = services.get()
        llen = len(sorted(svcs, key=lambda x: len(x.name))[-1].name)
        for x in svcs:
            data.append(
                click.style(
                    '{name: <{fill}}'.format(name=x.name, fill=llen + 3),
                    fg="white", bold=True) +
                click.style(
                    x.state.capitalize(),
                    fg="green" if x.state == "running" else "red") + "   " +
                click.style(
                    "Enabled" if x.enabled else "Disabled",
                    fg="green" if x.enabled else "red")
            )
        click.echo_via_pager("\n".join(data))
    except Exception as e:
        raise CLIException(str(e))


@svc.command()
@click.argument("name")
def start(name):
    """Start a service"""
    try:
        service = services.get(name)
        service.start()
        if service.state == "running":
            logger.success('ctl:svc:start', 'Started {0}'.format(name))
        else:
            logger.error('ctl:svc:start', 'Failed to start {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@svc.command()
@click.argument("name")
def stop(name):
    """Stop a service"""
    try:
        service = services.get(name)
        service.stop()
        logger.success('ctl:svc:stop', 'Stopped {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@svc.command()
@click.argument("name")
def restart(name):
    """Restart a service"""
    try:
        service = services.get(name)
        service.restart()
        if service.state == "running":
            logger.success('ctl:svc:restart', 'Restarted {0}'.format(name))
        else:
            logger.error(
                'ctl:svc:restart', 'Failed to restart {0}'.format(name)
            )
    except Exception as e:
        raise CLIException(str(e))


@svc.command()
@click.argument("name")
def enable(name):
    """Enable a service on boot"""
    try:
        service = services.get(name)
        service.enable()
        logger.success('ctl:svc:enable', 'Enabled {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@svc.command()
@click.argument("name")
def disable(name):
    """Disable a service on boot"""
    try:
        service = services.get(name)
        service.disable()
        logger.success('ctl:svc:disable', 'Disabled {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@svc.command()
@click.argument("name")
def status(name):
    """Get service status"""
    try:
        service = services.get(name)
        if not service:
            raise CLIException("No service found")
        llen = len(service.name) if len(service.name) > 20 else 20
        click.echo(
            click.style(
                '{name: <{fill}}'.format(name=service.name, fill=llen + 3),
                fg="white", bold=True) +
            click.style(
                service.state.capitalize(),
                fg="green" if service.state == "running" else "red") + "   " +
            click.style(
                "Enabled" if service.enabled else "Disabled",
                fg="green" if service.enabled else "red")
        )
    except Exception as e:
        raise CLIException(str(e))


@svc.command()
@click.argument("name")
def log(name):
    """Get logs since last boot for a particular service"""
    try:
        service = services.get(name)
        if not service:
            raise CLIException("No service found")
        if service.stype == "system":
            data = shell("journalctl -x -b 0 -u {0}".format(service.name))
            click.echo_via_pager(
                data["stdout"].decode()
            )
        else:
            click.echo_via_pager(service.get_log())
    except Exception as e:
        raise CLIException(str(e))
