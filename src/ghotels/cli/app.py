"""The ``ghotels`` command-line application."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from ghotels import __version__
from ghotels.cli.commands.details import details
from ghotels.cli.commands.enrich import enrich
from ghotels.cli.commands.search import search

app = typer.Typer(
    name="ghotels",
    help="Google Hotels from your terminal: search, rooms & rates, and an MCP server.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

app.command()(search)
app.command()(details)
app.command()(enrich)

_KNOWN_COMMANDS = frozenset({"search", "details", "enrich", "mcp", "mcp-http", "setup"})


def _version_callback(*, value: bool) -> None:
    if value:
        typer.echo(f"ghotels {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """Google Hotels from your terminal — no API key, no scraping."""


def reroute_bare_query(argv: list[str]) -> list[str]:
    """Make ``ghotels "tokyo hotels" ...`` behave as ``ghotels search ...``.

    A first argument that is neither a known command nor a flag is treated
    as a search query.
    """
    if len(argv) >= 2 and argv[1] not in _KNOWN_COMMANDS and not argv[1].startswith("-"):  # noqa: PLR2004
        return [argv[0], "search", *argv[1:]]
    return argv


def run() -> None:
    """Console-script entry point."""
    sys.argv = reroute_bare_query(sys.argv)
    app()


if __name__ == "__main__":
    run()
