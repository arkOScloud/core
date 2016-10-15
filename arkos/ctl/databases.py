# -*- coding: utf-8 -*-
"""Relates to commands for management of databases."""
import click

from arkos import conns, databases, logger
from arkos.ctl.utilities import CLIException


@click.group()
def db():
    """Database commands."""
    conns.connect()
    databases.scan_managers()
    databases.scan()


@click.group(name='dbuser')
def db_users():
    """Database user commands."""
    databases.scan_managers()
    databases.scan_users()


@db.command(name='list')
def list_dbs():
    """List all databases."""
    try:
        dbs = databases.get()
        if not dbs:
            logger.info('ctl:db:list', 'No databases found')
        llen = len(sorted(dbs, key=lambda x: len(x.id))[-1].id)
        for x in sorted(dbs, key=lambda x: x.id):
            click.echo(
                click.style(
                    '{name: <{fill}}'.format(name=x.id, fill=llen + 3),
                    fg="white", bold=True) +
                click.style(x.manager.name, fg="yellow")
            )
    except Exception as e:
        raise CLIException(str(e))


@db_users.command(name='list')
def list_users():
    """List all database users."""
    try:
        dbs = databases.get_users()
        if not dbs:
            logger.info('ctl:dbusr:list', 'No database users found')
            return
        llen = len(sorted(dbs, key=lambda x: len(x.id))[-1].id)
        for x in sorted(dbs, key=lambda x: x.id):
            click.echo(
                click.style(
                    '{name: <{fill}}'.format(name=x.id, fill=llen + 3),
                    fg="white", bold=True) +
                click.style(x.manager.name, fg="yellow")
            )
    except Exception as e:
        raise CLIException(str(e))


@db.command(name='types')
def list_types():
    """List all database types and running status."""
    try:
        dbs = databases.get_managers()
        if not dbs:
            logger.info('ctl:db:types', 'No databases found')
            return
        llen = len(sorted(dbs, key=lambda x: len(x.name))[-1].name)
        for x in sorted(dbs, key=lambda x: x.id):
            click.echo(
                click.style(
                    '{name: <{fill}}'.format(name=x.name, fill=llen + 3),
                    fg="white", bold=True) +
                click.style(
                    "Running" if x.state else "Stopped",
                    fg="green" if x.state else "red")
            )
    except Exception as e:
        raise CLIException(str(e))


@db_users.command(name='types')
def _list_types_usrs():
    list_types()


@db.command(name='create')
@click.argument("name")
@click.argument("type_id")
def create_db(name, type_id):
    """Add a database."""
    try:
        manager = databases.get_managers("db-" + type_id)
        manager.add_db(name)
        logger.success('ctl:db:create', 'Added {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@db_users.command(name='add')
@click.argument("name")
@click.argument("type_id")
def add_user(name, type_id):
    """Add a database user."""
    try:
        manager = databases.get_managers("db-" + type_id)
        manager.add_user(name)
        logger.success('ctl:dbusr:add', 'Added user {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@db.command()
@click.argument("name")
@click.argument("path", type=click.File("wb"))
def dump(name, path):
    """Export database to SQL file."""
    try:
        db = databases.get(name)
        data = db.dump()
        path.write(data)
        logger.success('ctl:db:dump', 'Database dumped to {0}'.format(path))
    except Exception as e:
        raise CLIException(str(e))


@db_users.command()
@click.argument("user_name")
@click.argument("db_name")
@click.option("--grant/revoke", required=True,
              help="Grant or revoke all access to this DB with this user")
def chmod(user_name, db_name, grant):
    """Get or set database user permissions."""
    try:
        u = databases.get_user(user_name)
        u.chperm("grant" if grant else "revoke", databases.get(db_name))
        logger.success('ctl:dbusr:chmod', 'Permissions set')
    except Exception as e:
        raise CLIException(str(e))


@db.command()
@click.argument("name")
def drop(name):
    """Delete a database."""
    try:
        db = databases.get(name)
        db.remove()
        logger.success('ctl:db:drop', 'Dropped {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))


@db_users.command(name='drop')
@click.argument("name")
def drop_user(name):
    """Delete a database user."""
    try:
        u = databases.get_user(name)
        u.remove()
        logger.success('ctl:dbusr:drop', 'Dropped {0}'.format(name))
    except Exception as e:
        raise CLIException(str(e))
