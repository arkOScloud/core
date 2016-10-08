# -*- coding: utf-8 -*-
import click

from arkos import conns, logger, tracked_services
from arkos.ctl.utilities import CLIException


@click.group()
def sec():
    """Security commands"""
    conns.connect()
    tracked_services.initialize()


@sec.command(name='list')
def list_policies():
    """List security policies"""
    try:
        data = [x.serialized for x in tracked_services.get()]
        for x in data:
            pol, fg = ("Allow All", "green") if x["policy"] == 2 else \
                (("Local Only", "yellow") if x["policy"] == 1 else
                    ("Restricted", "red"))
            click.echo(
                click.style(x["name"], fg="green", bold=True) +
                click.style(" (" + x["id"] + ")", fg="yellow")
            )
            click.echo(click.style(" * Type: ", fg="yellow") + x["type"])
            click.echo(
                click.style(" * Ports: ", fg="yellow") +
                ", ".join(
                    ["{0} {1}".format(y[1], y[0].upper()) for y in x["ports"]]
                )
            )
            click.echo(
                click.style(" * Policy: ", fg="yellow") +
                click.style(pol, fg=fg)
            )
    except Exception as e:
        raise CLIException(str(e))


@sec.command()
@click.argument("id")
def allow(id):
    """Allow all access to service"""
    try:
        svc = tracked_services.get(id)
        svc.policy = 2
        svc.save()
        logger.success('ctl:sec:allow', 'Access to {0} allowed'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@sec.command()
@click.argument("id")
def local(id):
    """Allow local network access only to service"""
    try:
        svc = tracked_services.get(id)
        svc.policy = 1
        svc.save()
        logger.success('ctl:sec:local', 'Access to {0} restricted'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@sec.command()
@click.argument("id")
def block(id):
    """Block all network access to service"""
    try:
        svc = tracked_services.get(id)
        svc.policy = 0
        svc.save()
        logger.success('ctl:sec:block', 'Access to {0} blocked'.format(id))
    except Exception as e:
        raise CLIException(str(e))
