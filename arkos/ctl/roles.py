# -*- coding: utf-8 -*-
import click

from arkos import conns, logger
from arkos.system import users, groups, domains
from arkos.ctl.utilities import abort_if_false, CLIException


@click.group()
def user():
    """User commands (LDAP)"""
    conns.connect()


@click.group()
def group():
    """Group commands (LDAP)"""
    conns.connect()


@click.group()
def domain():
    """Domain commands (LDAP)"""
    conns.connect()


@user.command(name='list')
def list_users():
    """List users"""
    try:
        data = [x.serialized for x in users.get()]
        for x in data:
            click.echo(
                click.style(x["name"], fg="white", bold=True) +
                click.style(" ({0})".format(x["id"]), fg="green")
            )
            click.echo(
                click.style(" * Name: ", fg="yellow") +
                x["first_name"] +
                (" " + x["last_name"] if x["last_name"] else "")
            )
            click.echo(
                click.style(" * Mail Addresses: ", fg="yellow") +
                ", ".join(x["mail_addresses"])
            )
            click.echo(
                click.style(" * Types: ", fg="yellow") +
                ", ".join([
                    y for y in [
                        "sudo" if x["sudo"] else None,
                        "admin" if x["admin"] else None
                    ] if y
                ])
            )
    except Exception as e:
        raise CLIException(str(e))


@user.command(name='add')
@click.argument("name")
@click.option("--password", prompt=True, hide_input=True,
              confirmation_prompt=True, help="Password for new user")
@click.option("--domain", prompt=True,
              help="Domain name to assign the new user to")
@click.option("--first-name", prompt="First name or pseudonym",
              help="First name or pseudonym")
@click.option("--last-name", prompt="Last name (optional)",
              help="Last name (optional)")
@click.option("--admin", is_flag=True,
              prompt="Give the user admin privileges?",
              help="Give the user admin privileges?")
@click.option("--sudo", is_flag=True,
              prompt="Give the user command-line sudo privileges?",
              help="Give the user command-line sudo privileges?")
def add_user(name, password, domain, first_name, last_name, admin, sudo):
    """Add a user to arkOS LDAP"""
    try:
        u = users.User(
            name=name, first_name=first_name, last_name=last_name,
            domain=domain, admin=admin, sudo=sudo
        )
        u.add(password)
        logger.success('ctl:usr:add', 'Added {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@user.command(name='mod')
@click.argument("name")
@click.option("--domain", default=None,
              help="Domain name to assign the new user to")
@click.option("--first-name", default=None, help="First name or pseudonym")
@click.option("--last-name", default=None, help="Last name (optional)")
@click.option("--admin", is_flag=True, default=None,
              help="Give the user admin privileges?")
@click.option("--sudo", is_flag=True, default=None,
              help="Give the user command-line sudo privileges?")
def mod_user(name, domain, first_name, last_name, admin, sudo):
    """Edit an arkOS LDAP user"""
    try:
        u = users.get(name=name)
        u.domain = domain or u.domain
        u.first_name = first_name or u.first_name
        u.last_name = last_name if last_name is not None else u.last_name
        u.admin = admin if admin is not None else u.admin
        u.sudo = sudo if sudo is not None else u.sudo
        u.update()
        logger.success('ctl:usr:mod', 'Modified {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@user.command()
@click.argument("name")
@click.option("--password", prompt=True, hide_input=True,
              confirmation_prompt=True, help="Password for new user")
def passwd(name, password):
    """Change an arkOS LDAP user password"""
    try:
        u = users.get(name=name)
        u.update(password)
        logger.success(
            'ctl:usr:passwd', 'Password changed for {0}'.format(name)
        )
    except Exception as e:
        raise CLIException(str(e))


@user.command(name='delete')
@click.argument("name")
@click.option("--yes", is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to remove this user?')
def delete_user(name):
    """Delete an arkOS LDAP user"""
    try:
        u = users.get(name=name)
        u.delete()
        logger.success('ctl:usr:delete', 'Deleted {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@group.command(name='list')
def list_groups():
    """List groups"""
    try:
        data = [x.serialized for x in groups.get()]
        for x in data:
            click.echo(
                click.style(x["name"], fg="white", bold=True) +
                click.style(" ({0})".format(x["id"]), fg="green")
            )
            click.echo(
                click.style(" * Members: ", fg="yellow") +
                ", ".join(x["users"])
            )
    except Exception as e:
        raise CLIException(str(e))


@group.command(name='add')
@click.argument("name")
@click.option("--users", multiple=True)
def add_group(name, users):
    """Add a group to arkOS LDAP"""
    try:
        g = groups.Group(name=name, users=users)
        g.add()
        logger.success('ctl:grp:add', 'Added {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@group.command(name='mod')
@click.argument("name")
@click.argument("operation", type=click.Choice(["add", "remove"]))
@click.argument("username")
def mod_group(name, operation, username):
    """Add/remove users from an arkOS LDAP group"""
    try:
        g = groups.get(name=name)
        if operation == "add":
            g.users.append(username)
        else:
            g.users.remove(username)
        g.update()
        logger.success('ctl:grp:mod', 'Modified {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@group.command(name='delete')
@click.argument("name")
@click.option("--yes", is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to remove this group?')
def delete_group(name):
    """Delete an arkOS LDAP group"""
    try:
        g = groups.get(name=name)
        g.delete()
        logger.success('ctl:grp:delete', 'Deleted {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@domain.command(name='list')
def list_domains():
    """List domains"""
    try:
        data = domains.get()
        for x in data:
            click.echo(x.id)
    except Exception as e:
        raise CLIException(str(e))


@domain.command(name='add')
@click.argument("name")
def add_domain(name):
    """Add a domain to arkOS LDAP"""
    try:
        d = domains.Domain(name=name)
        d.add()
        logger.success('ctl:dom:add', 'Added {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@domain.command(name='delete')
@click.argument("name")
@click.option("--yes", is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to remove this domain?')
def delete_domain(name):
    """Delete an arkOS LDAP domain"""
    try:
        d = domains.get(name)
        d.remove()
        logger.success('ctl:dom:delete', 'Deleted {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))
