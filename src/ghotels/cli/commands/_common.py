"""Helpers shared by the CLI commands."""

from __future__ import annotations

import json
from typing import Annotated, NoReturn

import typer

from ghotels.cli.options import OutputFormat
from ghotels.cli.render import console
from ghotels.envelope import error_envelope

FormatOption = Annotated[
    OutputFormat,
    typer.Option("--format", "-f", help="Output format.", case_sensitive=False),
]

CheckInOption = Annotated[
    str | None, typer.Option("--check-in", help="Check-in date (YYYY-MM-DD).")
]
CheckOutOption = Annotated[
    str | None, typer.Option("--check-out", help="Check-out date (YYYY-MM-DD).")
]
AdultsOption = Annotated[int, typer.Option("--adults", min=1, max=12, help="Adults travelling.")]
ChildAgeOption = Annotated[
    list[int] | None,
    typer.Option("--child-age", min=0, max=17, help="One flag per travelling child's age."),
]


def fail(kind: str, error: Exception, output: OutputFormat) -> NoReturn:
    """Print the failure in the requested format and exit non-zero."""
    envelope = error_envelope(kind, error)
    if output is OutputFormat.TEXT:
        message = envelope["error"]["message"]
        retry = " (retryable — try again shortly)" if envelope["error"]["retryable"] else ""
        console.print(f"[red]error:[/red] {message}{retry}", highlight=False)
    else:
        console.file.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    raise typer.Exit(1)
