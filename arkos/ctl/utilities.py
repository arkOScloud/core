import click

from arkos import logger


class CLIException(click.ClickException):
    """Reimplement click.ClickException() to print bold & in red."""

    def show(self, file=None):
        """Reimplement."""
        if self.message:
            logger.error("ctl:exc", self.format_message())


def abort_if_false(ctx, param, value):
    """Abort the command if the value resolves to be false."""
    if not value:
        ctx.abort()
