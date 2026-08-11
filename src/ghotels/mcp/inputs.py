"""Normalization of LLM-supplied tool arguments into domain models.

LLMs send strings with unpredictable casing; every helper here accepts that
reality and answers bad input with a message that lists the valid options.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TypeVar

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

E = TypeVar("E", bound=Enum)

_MIN_RATING_BY_FLOAT = {
    3.5: MinRating.THREE_FIVE_PLUS,
    4.0: MinRating.FOUR_ZERO_PLUS,
    4.5: MinRating.FOUR_FIVE_PLUS,
}


class ToolInputError(ValueError):
    """Raised when a tool argument cannot be interpreted."""


def parse_enum(kind: type[E], value: str, label: str) -> E:
    """Look up an enum member case-insensitively, with a helpful error."""
    try:
        return kind(value.strip().upper().replace("-", "_").replace(" ", "_"))
    except ValueError:
        options = ", ".join(member.value for member in kind)
        msg = f"unknown {label} {value!r} — valid options: {options}"
        raise ToolInputError(msg) from None


def parse_enum_list(kind: type[E], values: list[str] | None, label: str) -> list[E]:
    """Normalize an optional list of enum-valued strings."""
    return [parse_enum(kind, value, label) for value in values or []]


def parse_date_arg(value: str, label: str) -> date:
    """Parse a ``YYYY-MM-DD`` argument."""
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()  # noqa: DTZ007 - date-only
    except ValueError:
        msg = f"{label} must be YYYY-MM-DD, got {value!r}"
        raise ToolInputError(msg) from None


def parse_dates(check_in: str | None, check_out: str | None) -> StayDates | None:
    """Combine the two date arguments; both or neither."""
    if check_in is None and check_out is None:
        return None
    if check_in is None or check_out is None:
        msg = "check_in and check_out must be provided together"
        raise ToolInputError(msg)
    try:
        return StayDates(
            check_in=parse_date_arg(check_in, "check_in"),
            check_out=parse_date_arg(check_out, "check_out"),
        )
    except ValueError as exc:
        raise ToolInputError(str(exc)) from None


def parse_guests(adults: int, children: int, child_ages: list[int] | None) -> Guests:
    """Build a party, insisting the child count matches the ages given."""
    ages = child_ages or []
    if children != len(ages):
        msg = (
            f"children={children} but {len(ages)} child_ages given — "
            "provide one age (0-17) per child"
        )
        raise ToolInputError(msg)
    try:
        return Guests(adults=adults, child_ages=ages)
    except ValueError as exc:
        raise ToolInputError(str(exc)) from None


def parse_min_rating(value: float | None) -> MinRating | None:
    """Map the 3.5 / 4.0 / 4.5 rating floor onto its enum."""
    if value is None:
        return None
    rating = _MIN_RATING_BY_FLOAT.get(value)
    if rating is None:
        msg = f"min_guest_rating must be one of 3.5, 4.0, 4.5 — got {value}"
        raise ToolInputError(msg)
    return rating


def build_search_filters(  # noqa: PLR0913 - one keyword per tool argument
    query: str,
    *,
    check_in: str | None,
    check_out: str | None,
    adults: int,
    children: int,
    child_ages: list[int] | None,
    currency: str,
    sort_by: str,
    hotel_class: list[int] | None,
    amenities: list[str] | None,
    brands: list[str] | None,
    min_guest_rating: float | None,
    free_cancellation: bool,
    eco_certified: bool,
    special_offers: bool,
    price_min: int | None,
    price_max: int | None,
    property_type: str,
) -> SearchFilters:
    """Assemble validated :class:`SearchFilters` from raw tool arguments."""
    try:
        return SearchFilters(
            location=Location(query=query),
            dates=parse_dates(check_in, check_out),
            guests=parse_guests(adults, children, child_ages),
            currency=parse_enum(Currency, currency, "currency"),
            sort_by=parse_enum(SortBy, sort_by, "sort_by"),
            star_classes=hotel_class or [],
            amenities=parse_enum_list(Amenity, amenities, "amenity"),
            brands=parse_enum_list(Brand, brands, "brand"),
            min_rating=parse_min_rating(min_guest_rating),
            free_cancellation=free_cancellation,
            eco_certified=eco_certified,
            special_offers=special_offers,
            price_min=price_min,
            price_max=price_max,
            property_type=parse_enum(PropertyType, property_type, "property_type"),
        )
    except ToolInputError:
        raise
    except ValueError as exc:
        raise ToolInputError(str(exc)) from None
