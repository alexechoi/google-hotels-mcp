"""Output rendering: rich tables for people, envelopes for machines."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from ghotels.envelope import dump_enriched, dump_model, success_envelope
from ghotels.models.detail import CancellationKind

if TYPE_CHECKING:
    from ghotels.api import EnrichedHotel
    from ghotels.models.detail import HotelDetail
    from ghotels.models.hotel import Hotel

console = Console()

_MAX_TEXT_AMENITIES = 4


def emit_json(kind: str, query: dict[str, Any], results: list[dict[str, Any]]) -> None:
    """Print one pretty envelope."""
    console.print_json(json.dumps(success_envelope(kind, query, results), ensure_ascii=False))


def emit_jsonl(results: list[dict[str, Any]]) -> None:
    """Print one compact JSON record per line."""
    for record in results:
        console.file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _fmt_price(hotel: Hotel) -> str:
    if hotel.price is None:
        return "—"
    return f"{hotel.price.amount:,} {hotel.price.currency}"


def _fmt_rating(hotel: Hotel) -> str:
    if hotel.rating is None or hotel.rating.score is None:
        return "—"
    reviews = f" ({hotel.rating.review_count:,})" if hotel.rating.review_count else ""
    return f"{hotel.rating.score}{reviews}"


def render_search_table(hotels: list[Hotel], title: str) -> None:
    """Print the list-view results as a table."""
    table = Table(title=title, show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Hotel", overflow="fold")
    table.add_column("Stars", justify="center")
    table.add_column("Price/night", justify="right")
    table.add_column("Rating", justify="right")
    table.add_column("Amenities", overflow="fold")
    for index, hotel in enumerate(hotels, start=1):
        amenities = ", ".join(sorted(a.value for a in hotel.amenities)[:_MAX_TEXT_AMENITIES])
        table.add_row(
            str(index),
            hotel.name,
            str(hotel.star_class) if hotel.star_class else "—",
            _fmt_price(hotel),
            _fmt_rating(hotel),
            amenities or "—",
        )
    console.print(table)
    keyed = sum(1 for h in hotels if h.entity_key)
    console.print(
        f"[dim]{len(hotels)} hotels · {keyed} with entity keys "
        f"(use `ghotels details <entity-key>` for rooms & rates)[/dim]"
    )


def _cancellation_text(kind: CancellationKind, free_until: str | None) -> str:
    if kind is CancellationKind.FREE_UNTIL and free_until:
        return f"free until {free_until}"
    return {
        CancellationKind.FREE: "free",
        CancellationKind.PARTIAL_REFUND: "partial refund",
        CancellationKind.NON_REFUNDABLE: "non-refundable",
        CancellationKind.UNKNOWN: "—",
    }.get(kind, "—")


def render_detail(detail: HotelDetail) -> None:
    """Print one hotel's full record: header lines, then a rate table."""
    console.print(f"[bold]{detail.name}[/bold]", highlight=False)
    for label, value in (
        ("Address", detail.address),
        ("Phone", detail.phone),
        ("About", detail.description),
    ):
        if value:
            console.print(f"  [dim]{label}:[/dim] {value}", highlight=False)
    if detail.rating and detail.rating.score is not None:
        reviews = f" · {detail.rating.review_count:,} reviews" if detail.rating.review_count else ""
        console.print(f"  [dim]Rating:[/dim] {detail.rating.score}{reviews}", highlight=False)

    for room in detail.rooms:
        table = Table(title=f"{room.name} — rates")
        table.add_column("Provider")
        table.add_column("Price/night", justify="right")
        table.add_column("Cancellation")
        for rate in room.rates:
            table.add_row(
                rate.provider,
                f"{rate.price:,} {rate.currency}",
                _cancellation_text(rate.cancellation.kind, str(rate.cancellation.free_until or "")),
            )
        console.print(table)
    if not detail.rooms:
        console.print("[dim]No rate plans returned for this date window.[/dim]")


def render_enriched(items: list[EnrichedHotel]) -> None:
    """Print enrichment outcomes: a detail block per success, a note per failure."""
    for item in items:
        if item.detail is not None:
            render_detail(item.detail)
        else:
            retry = " (retryable)" if item.retryable else ""
            console.print(
                f"[bold]{item.hotel.name}[/bold] — [red]skipped[/red]: {item.error}{retry}",
                highlight=False,
            )
        console.print()


def search_results_json(hotels: list[Hotel]) -> list[dict[str, Any]]:
    """JSON-safe records for search results."""
    return [dump_model(h) for h in hotels]


def enriched_results_json(items: list[EnrichedHotel]) -> list[dict[str, Any]]:
    """JSON-safe records for enrichment outcomes."""
    return [dump_enriched(item) for item in items]
