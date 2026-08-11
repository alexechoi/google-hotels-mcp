"""``ghotels search`` — fast list-view search (one RPC)."""

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
from ghotels.cli.options import OutputFormat, build_filters
from ghotels.cli.render import emit_json, emit_jsonl, render_search_table, search_results_json
from ghotels.errors import GHotelsError
from ghotels.models import Amenity, Brand, Currency, MinRating, PropertyType, SortBy


def search(
    query: Annotated[str, typer.Argument(help='Search text, e.g. "tokyo hotels".')],
    check_in: CheckInOption = None,
    check_out: CheckOutOption = None,
    adults: AdultsOption = 2,
    child_age: ChildAgeOption = None,
    currency: Annotated[
        Currency, typer.Option("--currency", case_sensitive=False, help="ISO 4217 currency.")
    ] = Currency.USD,
    property_type: Annotated[
        PropertyType, typer.Option("--property-type", case_sensitive=False)
    ] = PropertyType.HOTELS,
    sort_by: Annotated[SortBy, typer.Option("--sort-by", case_sensitive=False)] = SortBy.RELEVANCE,
    stars: Annotated[
        list[int] | None,
        typer.Option("--stars", min=1, max=5, help="Star class; repeat for several."),
    ] = None,
    min_rating: Annotated[
        MinRating | None, typer.Option("--min-rating", case_sensitive=False)
    ] = None,
    amenity: Annotated[
        list[Amenity] | None,
        typer.Option("--amenity", case_sensitive=False, help="Repeat for several."),
    ] = None,
    brand: Annotated[
        list[Brand] | None,
        typer.Option("--brand", case_sensitive=False, help="Repeat for several."),
    ] = None,
    price_min: Annotated[int | None, typer.Option("--price-min", min=0)] = None,
    price_max: Annotated[int | None, typer.Option("--price-max", min=0)] = None,
    free_cancellation: Annotated[bool, typer.Option("--free-cancellation")] = False,
    eco_certified: Annotated[bool, typer.Option("--eco-certified")] = False,
    special_offers: Annotated[bool, typer.Option("--special-offers")] = False,
    max_results: Annotated[
        int | None, typer.Option("--max-results", min=1, max=25, help="Cap the result list.")
    ] = None,
    output: FormatOption = OutputFormat.TEXT,
) -> None:
    """Search hotels: filters in, a ranked list with prices and ratings out."""
    filters = build_filters(
        query,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        child_ages=child_age or [],
        currency=currency,
        property_type=property_type,
        sort_by=sort_by,
        stars=stars or [],
        min_rating=min_rating,
        amenities=amenity or [],
        brands=brand or [],
        price_min=price_min,
        price_max=price_max,
        free_cancellation=free_cancellation,
        eco_certified=eco_certified,
        special_offers=special_offers,
    )
    try:
        with runtime.make_client() as client:
            hotels = client.search(filters)
    except GHotelsError as exc:
        fail("search", exc, output)

    if max_results is not None:
        hotels = hotels[:max_results]
    records = search_results_json(hotels)
    if output is OutputFormat.JSON:
        emit_json("search", filters.model_dump(mode="json"), records)
    elif output is OutputFormat.JSONL:
        emit_jsonl(records)
    else:
        render_search_table(hotels, title=query)
