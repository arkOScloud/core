# -*- coding: utf-8 -*-
"""Relates to commands for management of certificates."""
import click

from arkos import applications, certificates, conns, logger, websites
from arkos.ctl.utilities import abort_if_false, CLIException


@click.group()
def cert():
    """TLS Certificate commands."""
    conns.connect()
    applications.scan(cry=False)
    certificates.scan()
    certificates.scan_authorities()
    websites.scan()


@cert.command(name='list')
def list_certs():
    """List all certificates."""
    try:
        certs = certificates.get()
        if not certs:
            logger.info('ctl:cert:list', 'No certificates found')
        llen = len(sorted(certs, key=lambda x: len(x.id))[-1].id)
        for x in sorted(certs, key=lambda x: x.id):
            klkt = "{0}-bit {1}".format(x.keylength, x.keytype)
            click.echo(
                click.style(
                    '{name: <{fill}}'.format(name=x.id, fill=llen + 3),
                    fg="white", bold=True) +
                click.style(
                    '{name: <15}'.format(name=klkt),
                    fg="green") +
                click.style(x.domain, fg="yellow")
            )
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
@click.argument("name")
def info(name):
    """Show information about a particular certificate."""
    try:
        cert = certificates.get(name)
        if not cert:
            logger.info('ctl:cert:info', 'No certificates found')
            return
        click.echo(click.style(cert.id, fg="white", bold=True))
        click.echo(
            click.style(" * Domain: ", fg="yellow") + cert.domain
        )
        click.echo(
            click.style(" * Type: ", fg="yellow") +
            "{0}-bit {1}".format(cert.keylength, cert.keytype)
        )
        click.echo(
            click.style(" * SHA1: ", fg="yellow") + cert.sha1
        )
        click.echo(
            click.style(" * Expires: ", fg="yellow") +
            cert.expiry.strftime("%c")
        )
        if cert.assigns:
            imsg = ", ".join([y["name"] for y in cert.assigns])
            click.echo(click.style(" * Assigned to: ", fg="yellow") + imsg)
    except Exception as e:
        raise CLIException(str(e))


@cert.command(name='authorities')
def list_authorities():
    """List all certificate authorities (CAs)."""
    try:
        certs = certificates.get_authorities()
        if not certs:
            logger.info(
                'ctl:cert:authorities', 'No certificate authorities found'
            )
            return
        llen = len(sorted(certs, key=lambda x: len(x.id))[-1].id)
        for x in sorted(certs, key=lambda x: x.id):
            click.echo(
                click.style(
                    '{name: <{fill}}'.format(name=x.id, fill=llen + 3),
                    fg="white", bold=True) + "Expires " +
                click.style(x.expiry.strftime("%c"), fg="yellow")
            )
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
def assigns():
    """List all apps/sites that can use certificates."""
    click.echo("Apps/Sites that can use certificates:")
    try:
        assigns = []
        assigns.append({"type": "genesis", "id": "genesis",
                        "name": "arkOS Genesis/API"})
        for x in websites.get():
            assigns.append({"type": "website", "id": x.id,
                            "name": x.id if x.app else x.name})
        for x in applications.get(installed=True):
            if x.type == "app" and x.uses_ssl:
                for y in x.get_ssl_able():
                    assigns.append(y)
        for x in assigns:
            imsg = click.style("(" + x["type"].capitalize() + ")", fg="green")
            click.echo(
                click.style(x["name"], fg="white", bold=True) + " " + imsg
            )
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
@click.argument("name")
@click.option("--domain", help="Fully-qualified domain name of the cert."
              "Must match a domain present on the system")
@click.option("--country", help="Two-character country code (ex.: 'US', 'CA')")
@click.option("--state", help="State or province")
@click.option("--locale", help="City/town name")
@click.option("--email", default="", help="Contact email")
@click.option("--keytype", default="RSA",
              help="SSL key type (ex.: 'RSA' or 'DSA')")
@click.option("--keylength", type=int, default=2048,
              help="SSL key length in bits")
def generate(name, domain, country, state, locale, email, keytype, keylength):
    """Generate a self-signed SSL/TLS certificate."""
    if not domain:
        logger.error(
            "ctl:info:generate", "Choose a fully-qualified domain name of the "
            "certificate. Must match a domain present on the system"
        )
        domain = click.prompt("Domain name")
    if not country:
        logger.info(
            "ctl:cert:generate",
            "Two-character country code (ex.: 'US' or 'CA')"
        )
        country = click.prompt("Country code")
    if not state:
        state = click.prompt("State/Province")
    if not locale:
        locale = click.prompt("City/Town/Locale")
    if not email:
        email = click.prompt("Contact email [optional]")
    try:
        certificates.generate_certificate(
            name, domain, country, state, locale, email, keytype,
            keylength)
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
@click.option("--domain", help="Fully-qualified domain name of the cert."
              "Must match a domain present on the system")
def request(domain):
    """Request a free ACME certificate from Let's Encrypt."""
    if not domain:
        logger.error(
            "ctl:info:generate", "Choose a fully-qualified domain name of the "
            "certificate. Must match a domain present on the system"
        )
        domain = click.prompt("Domain name")
    try:
        certificates.request_acme_certificate(domain)
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
@click.argument("name")
@click.argument("certfile", type=click.File("r"))
@click.argument("keyfile", type=click.File("r"))
@click.option("--chainfile", default=None, type=click.File("r"),
              help="Optional file to include in cert chain")
def upload(name, certfile, keyfile, chainfile):
    """Upload an SSL/TLS certificate."""
    try:
        certificates.upload_certificate(
            name, certfile.read(), keyfile.read(),
            chainfile.read() if chainfile else None)
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
@click.argument("id")
@click.argument("type")
@click.argument("appid")
@click.argument("specialid", default=None)
def assign(id, type, appid, specialid):
    """Assign a certificate to an app or website."""
    try:
        cert = certificates.get(id)
        cert.assign({"type": type, "id": appid, "aid": appid,
                     "sid": specialid})
        logger.info(
            'ctl:cert:assign', 'Assigned {0} to {0}'.format(id, appid)
        )
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
@click.argument("id")
@click.argument("type")
@click.argument("appid")
@click.argument("specialid", default=None)
def unassign(id, type, appid, specialid):
    """Unassign a certificate from an app or website."""
    try:
        cert = certificates.get(id)
        cert.unassign({"type": type, "id": appid, "aid": appid,
                       "sid": specialid})
        logger.info(
            'ctl:cert:unassign', 'Unassigned {0} from {0}'.format(id, appid)
        )
    except Exception as e:
        raise CLIException(str(e))


@cert.command()
@click.argument("id")
@click.option("--yes", is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to remove this site?')
def delete(id):
    """Delete a certificate."""
    try:
        cert = certificates.get(id)
        cert.remove()
        logger.success('ctl:cert:delete', 'Deleted {0}'.format(id))
    except Exception as e:
        raise CLIException(str(e))
