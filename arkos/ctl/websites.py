# -*- coding: utf-8 -*-
import click

from arkos import applications, certificates, conns, logger, websites
from arkos.ctl.utilities import abort_if_false, CLIException


@click.group()
def site():
    """Website commands"""
    conns.connect()
    applications.scan(cry=False)
    certificates.scan()
    websites.scan()


def _list_websites(sites):
    if not sites:
        logger.info('ctl:site:list', 'No websites found')
    for x in sorted(sites, key=lambda x: x["id"]):
        url = "https://" if x["certificate"] else "http://"
        url += x["domain"]
        url += (":{0}".format(x["port"])) if x["port"] not in [80, 443] else ""
        click.echo(click.style(x["id"], fg="green", bold=True))
        click.echo(click.style(" * URL: ", fg="yellow") + url)
        click.echo(click.style(" * Site Type: ", fg="yellow") + x["app_name"])
        click.echo(
            click.style(" * Uses SSL: ", fg="yellow") +
            ("Yes" if x["certificate"] else "No")
        )
        click.echo(
            click.style(" * Enabled: ", fg="yellow") +
            ("Yes" if x["enabled"] else "No")
        )
        if x.get("has_update"):
            click.secho(" * Update available!", fg="green")


@site.command(name='list')
def list_sites():
    """List all websites"""
    try:
        adata = [x.serialized for x in websites.get()]
        _list_websites(adata)
    except Exception as e:
        raise CLIException(str(e))


@site.command()
@click.argument("id")
@click.option("--site-type", prompt=True,
              help="Type identifier for website (see list of Apps)")
@click.option(
    "--address", prompt=True,
    help="The domain (with subdomain) to make this site available on. "
    "Must have added via Domains")
@click.option("--port", prompt=True, type=int,
              help="The port number to make the site available on (default 80)"
              )
@click.option("--extra-data", help="Any extra data your site might require")
def create(id, site_type, address, port, extra_data):
    """Create a website"""
    try:
        edata = {}
        if extra_data:
            for x in extra_data.split(","):
                edata[x.split("=")[0]] = x.split("=")[1]
        sapp = applications.get(site_type.lower())
        if hasattr(sapp, "website_options") and not extra_data:
            for x in sapp.website_options:
                if x == "messages":
                    continue
                for y in sapp.website_options[x]:
                    edata[y["id"]] = click.prompt(y["label"])
        site = sapp._website
        site = site(sapp, id, address, port)
        site.install(edata, True)
    except Exception as e:
        raise CLIException(str(e))


@site.command()
@click.argument("id")
@click.option(
    "--address", help="The domain (with subdomain) to make this "
    "site available on. Must have added via Domains")
@click.option(
    "--port", type=int,
    help="The port number to make the site available on (default 80)")
@click.option(
    "--new_name", default="", help="Any extra data your site might require")
def edit(id, address, port, new_name):
    """Edit a website"""
    try:
        site = websites.get(id)
        site.addr = address
        site.port = port
        site.edit(new_name or None)
        logger.success('ctl:site:edit', 'Edited {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@site.command()
@click.argument("id")
def enable(id):
    """Enable a website"""
    try:
        site = websites.get(id)
        site.nginx_enable()
        logger.success('ctl:site:enable', 'Enabled {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@site.command()
@click.argument("id")
def disable(id):
    """Disable a website"""
    try:
        site = websites.get(id)
        site.nginx_disable()
        logger.success('ctl:site:disable', 'Disabled {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@site.command()
@click.argument("id")
def update(id):
    """Update a website"""
    try:
        site = websites.get(id)
        site.update()
        logger.success('ctl:site:update', 'Updated {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))


@site.command()
@click.argument("id")
@click.option("--yes", is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to remove this site?')
def delete(id):
    """Remove a website"""
    try:
        site = websites.get(id)
        site.remove()
        logger.success('ctl:site:delete', 'Removed {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))
