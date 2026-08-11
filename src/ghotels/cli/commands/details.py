"""``ghotels details`` — rooms, rates, and policies for one hotel."""

from __future__ import annotations

from typing import Annotated

import typer

from ghotels.cli import runtime
from ghotels.cli.commands._common import (
    AdultsOption,
    CheckInOption,
    CheckOutOption,
    ChildAgeOption,
    FormatOption,
    fail,
)
from ghotels.cli.options import OutputFormat, build_guests, build_stay_dates
from ghotels.cli.render import emit_json, emit_jsonl, render_detail
from ghotels.envelope import dump_model
from ghotels.errors import GHotelsError
from ghotels.models import Currency


def details(
    entity_key: Annotated[str, typer.Argument(help="Hotel identifier from a prior search result.")],
    check_in: CheckInOption = None,
    check_out: CheckOutOption = None,
    adults: AdultsOption = 2,
    child_age: ChildAgeOption = None,
    currency: Annotated[
        Currency, typer.Option("--currency", case_sensitive=False, help="ISO 4217 currency.")
    ] = Currency.USD,
    output: FormatOption = OutputFormat.TEXT,
) -> None:
    """Fetch one hotel's rooms, per-provider rates, and cancellation policies."""
    dates = build_stay_dates(check_in, check_out)
    if dates is None:
        msg = "--check-in and --check-out are required — rate plans are date-keyed"
        raise typer.BadParameter(msg)
    guests = build_guests(adults, child_age or [])

    try:
        with runtime.make_client() as client:
            detail = client.details(entity_key, dates=dates, guests=guests, currency=currency)
    except GHotelsError as exc:
        fail("detail", exc, output)

    record = dump_model(detail)
    if output is OutputFormat.JSON:
        query = {
            "entity_key": entity_key,
            "dates": dates.model_dump(mode="json"),
            "guests": guests.model_dump(mode="json"),
            "currency": currency.value,
        }
        emit_json("detail", query, [record])
    elif output is OutputFormat.JSONL:
        emit_jsonl([record])
    else:
        render_detail(detail)
