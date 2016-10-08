# -*- coding: utf-8 -*-
import click
import pacman

from arkos import logger
from arkos.ctl.utilities import abort_if_false, CLIException


@click.group()
def pkg():
    """System package commands"""
    pass


@pkg.command()
@click.argument("name", required=True, nargs=-1)
@click.option("--yes", is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to install these packages?')
def install(name):
    """Install system package(s)"""
    try:
        logger.info(
            'ctl:pkg:install', 'Installing packages and their dependencies:'
        )
        click.echo(", ".join(name))
        pacman.install(list(name))
        logger.success('ctl:pkg:install', 'Install complete')
    except Exception as e:
        raise CLIException(str(e))


@pkg.command()
@click.argument("name", required=True, nargs=-1)
@click.option("--purge", is_flag=True,
              help="Purge associated files and folders")
@click.option("--yes", is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to remove these packages?')
def remove(name, purge):
    """Removes system package(s)"""
    try:
        logger.info('ctl:pkg:remove', 'Removing packages:')
        click.echo(", ".join(name))
        pacman.remove(list(name), purge=purge)
        logger.success('ctl:pkg:remove', 'Removal complete')
    except Exception as e:
        raise CLIException(str(e))


@pkg.command()
def update():
    """Updates system package index"""
    try:
        pacman.refresh()
        logger.success('ctl:pkg:update', 'Index updated')
    except Exception as e:
        raise CLIException(str(e))


@pkg.command()
@click.option("--yes", is_flag=True)
def upgrade(yes):
    """Upgrades all system packages"""
    try:
        pacman.refresh()
        pkgs = pacman.get_installed()
        pkgs = [x["id"] for x in pkgs if x["upgradable"]]
        if not pkgs:
            logger.info('ctl:pkg:upgrade', 'System already up-to-date')
        else:
            logger.info(
                'ctl:pkg:upgrade', 'The following packages will be upgraded:'
            )
            click.echo(", ".join(pkgs))
            if yes or click.confirm("Are you sure you want to upgrade?"):
                logger.info('ctl:pkg:upgrade', 'Upgrading system...')
                pacman.upgrade()
                logger.success('ctl:pkg:upgrade', 'Upgrade complete')
    except Exception as e:
        raise CLIException(str(e))
