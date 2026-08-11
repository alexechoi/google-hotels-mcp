"""Shared CLI option parsing: flags in, domain models out."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

import typer

from ghotels.models import (
    Amenity,
    Brand,
    Currency,
    Guests,
    Location,
    MinRating,
    PropertyType,
    SearchFilters,
    SortBy,
    StayDates,
)


class OutputFormat(str, Enum):
    """How a command prints its results."""

    TEXT = "text"
    JSON = "json"
    JSONL = "jsonl"


def parse_iso_date(value: str) -> date:
    """Parse ``YYYY-MM-DD``, raising a clean usage error otherwise."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()  # noqa: DTZ007 - date-only
    except ValueError as exc:
        msg = f"expected YYYY-MM-DD, got {value!r}"
        raise typer.BadParameter(msg) from exc


def build_stay_dates(check_in: str | None, check_out: str | None) -> StayDates | None:
    """Combine the two date flags; both or neither must be given."""
    if check_in is None and check_out is None:
        return None
    if check_in is None or check_out is None:
        msg = "--check-in and --check-out must be given together"
        raise typer.BadParameter(msg)
    try:
        return StayDates(check_in=parse_iso_date(check_in), check_out=parse_iso_date(check_out))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def build_guests(adults: int, child_ages: list[int]) -> Guests:
    """Validate party flags into a :class:`Guests`."""
    try:
        return Guests(adults=adults, child_ages=child_ages)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def build_filters(
    query: str,
    *,
    check_in: str | None,
    check_out: str | None,
    adults: int,
    child_ages: list[int],
    currency: Currency,
    property_type: PropertyType,
    sort_by: SortBy,
    stars: list[int],
    min_rating: MinRating | None,
    amenities: list[Amenity],
    brands: list[Brand],
    price_min: int | None,
    price_max: int | None,
    free_cancellation: bool,
    eco_certified: bool,
    special_offers: bool,
) -> SearchFilters:
    """Assemble a :class:`SearchFilters` from CLI flags."""
    try:
        return SearchFilters(
            location=Location(query=query),
            dates=build_stay_dates(check_in, check_out),
            guests=build_guests(adults, child_ages),
            currency=currency,
            property_type=property_type,
            sort_by=sort_by,
            star_classes=stars,
            min_rating=min_rating,
            amenities=amenities,
            brands=brands,
            price_min=price_min,
            price_max=price_max,
            free_cancellation=free_cancellation,
            eco_certified=eco_certified,
            special_offers=special_offers,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
