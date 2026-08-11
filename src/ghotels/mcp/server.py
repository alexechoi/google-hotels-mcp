"""Google Hotels MCP server: three tools, two prompts, one resource.

All tools are read-only and idempotent, return the canonical envelopes from
:mod:`ghotels.envelope`, and answer bad input or upstream failures with an
error envelope rather than a protocol-level exception — an LLM can read the
message and correct itself.
"""

from __future__ import annotations

import json
import os
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from ghotels.envelope import (
    dump_enriched,
    dump_model,
    error_envelope,
    success_envelope,
)
from ghotels.errors import GHotelsError
from ghotels.mcp import runtime
from ghotels.mcp.config import ENVIRONMENT_DOC, HARD_MAX_HOTELS, SETTINGS
from ghotels.mcp.inputs import (
    ToolInputError,
    build_search_filters,
    parse_dates,
    parse_enum,
    parse_guests,
)
from ghotels.models import Currency

mcp: FastMCP = FastMCP("Google Hotels MCP")

_READ_ONLY = {"title": "", "readOnlyHint": True, "idempotentHint": True}


@mcp.tool(annotations={**_READ_ONLY, "title": "Search Hotels"})
async def search_hotels(
    query: Annotated[
        str, Field(description="City or property query, e.g. 'hotels in Paris' or 'Hilton Tokyo'.")
    ],
    check_in: Annotated[
        str | None, Field(description="Check-in date YYYY-MM-DD. Omit for flexible dates.")
    ] = None,
    check_out: Annotated[
        str | None, Field(description="Check-out date YYYY-MM-DD. Required when check_in is set.")
    ] = None,
    adults: Annotated[
        int, Field(ge=1, le=12, description="Adult guests.")
    ] = SETTINGS.default_adults,
    children: Annotated[
        int, Field(ge=0, le=8, description="Child count. Provide child_ages when > 0.")
    ] = 0,
    child_ages: Annotated[list[int] | None, Field(description="One age (0-17) per child.")] = None,
    currency: Annotated[
        str, Field(description="ISO 4217 code, e.g. 'USD', 'EUR'.")
    ] = SETTINGS.default_currency,
    sort_by: Annotated[
        str,
        Field(description="RELEVANCE (default), LOWEST_PRICE, HIGHEST_RATING, or MOST_REVIEWED."),
    ] = SETTINGS.default_sort_by,
    hotel_class: Annotated[
        list[int] | None, Field(description="Star classes to include, e.g. [4, 5].")
    ] = None,
    amenities: Annotated[
        list[str] | None,
        Field(
            description=(
                "Amenity filters, e.g. ['WIFI', 'POOL', 'GYM', 'SPA', 'PARKING', "
                "'BREAKFAST', 'PET_FRIENDLY', 'KID_FRIENDLY', 'WHEELCHAIR_ACCESSIBLE']."
            )
        ),
    ] = None,
    brands: Annotated[
        list[str] | None,
        Field(description="Brand families, e.g. ['HILTON', 'MARRIOTT', 'HYATT', 'IHG']."),
    ] = None,
    min_guest_rating: Annotated[
        float | None, Field(description="Guest-rating floor: 3.5, 4.0, or 4.5.")
    ] = None,
    free_cancellation: Annotated[
        bool,
        Field(
            description=(
                "Refundable stays only. Use for 'refundable', 'flexible booking', "
                "'cancel anytime', or 'free cancellation'."
            )
        ),
    ] = False,
    eco_certified: Annotated[bool, Field(description="Eco-certified properties only.")] = False,
    special_offers: Annotated[bool, Field(description="Current deals only.")] = False,
    price_min: Annotated[int | None, Field(ge=0, description="Min per-night price.")] = None,
    price_max: Annotated[int | None, Field(ge=0, description="Max per-night price.")] = None,
    property_type: Annotated[
        str, Field(description="HOTELS (default) or VACATION_RENTALS.")
    ] = "HOTELS",
    max_results: Annotated[
        int | None, Field(ge=1, le=25, description="Cap the result list.")
    ] = SETTINGS.max_results,
) -> dict[str, Any]:
    """Fast list-view hotel search. USE THIS FIRST to discover hotels.

    Returns name, price, rating, stars, amenities, and an entity_key per
    hotel (one RPC). entity_key values feed get_hotel_details. Prefer this
    over search_hotels_with_details unless the user explicitly needs
    room/rate/cancellation detail.

    Common phrasings: 'refundable' -> free_cancellation=True; 'budget' ->
    sort_by='LOWEST_PRICE' or price_max; 'luxury' -> hotel_class=[5];
    'pet-friendly' -> amenities=['PET_FRIENDLY']; 'eco' -> eco_certified=True.
    """
    try:
        filters = build_search_filters(
            query,
            check_in=check_in,
            check_out=check_out,
            adults=adults,
            children=children,
            child_ages=child_ages,
            currency=currency,
            sort_by=sort_by,
            hotel_class=hotel_class,
            amenities=amenities,
            brands=brands,
            min_guest_rating=min_guest_rating,
            free_cancellation=free_cancellation,
            eco_certified=eco_certified,
            special_offers=special_offers,
            price_min=price_min,
            price_max=price_max,
            property_type=property_type,
        )
        hotels = await runtime.get_api().search(filters)
    except (ToolInputError, GHotelsError) as exc:
        return error_envelope("search", exc)
    if max_results is not None:
        hotels = hotels[:max_results]
    return success_envelope(
        "search", filters.model_dump(mode="json"), [dump_model(h) for h in hotels]
    )


@mcp.tool(annotations={**_READ_ONLY, "title": "Get Hotel Details"})
async def get_hotel_details(
    entity_key: Annotated[str, Field(description="Hotel identifier from a search_hotels result.")],
    check_in: Annotated[str, Field(description="Check-in date YYYY-MM-DD.")],
    check_out: Annotated[str, Field(description="Check-out date YYYY-MM-DD.")],
    adults: Annotated[int, Field(ge=1, le=12)] = SETTINGS.default_adults,
    children: Annotated[int, Field(ge=0, le=8)] = 0,
    child_ages: Annotated[list[int] | None, Field(description="One age per child.")] = None,
    currency: Annotated[str, Field(description="ISO 4217 code.")] = SETTINGS.default_currency,
) -> dict[str, Any]:
    """Deep detail for ONE hotel: rooms, per-provider rates, cancellation.

    Requires an entity_key from search_hotels; dates are required because
    rate plans are computed for the stay window. One RPC. For multi-hotel
    comparison use search_hotels_with_details instead.
    """
    try:
        dates = parse_dates(check_in, check_out)
        if dates is None:
            msg = "check_in and check_out are required"
            raise ToolInputError(msg)  # noqa: TRY301 - single funnel to the error envelope
        guests = parse_guests(adults, children, child_ages)
        currency_code = parse_enum(Currency, currency, "currency")
        detail = await runtime.get_api().details(
            entity_key, dates=dates, guests=guests, currency=currency_code
        )
    except (ToolInputError, GHotelsError) as exc:
        return error_envelope("detail", exc)
    query = {
        "entity_key": entity_key,
        "dates": dates.model_dump(mode="json"),
        "guests": guests.model_dump(mode="json"),
        "currency": currency_code.value,
    }
    return success_envelope("detail", query, [dump_model(detail)])


@mcp.tool(annotations={**_READ_ONLY, "title": "Search Hotels With Details"})
async def search_hotels_with_details(
    query: Annotated[str, Field(description="City or property query.")],
    check_in: Annotated[str, Field(description="Check-in date YYYY-MM-DD (required).")],
    check_out: Annotated[str, Field(description="Check-out date YYYY-MM-DD (required).")],
    max_hotels: Annotated[
        int,
        Field(
            ge=1, le=HARD_MAX_HOTELS, description=f"Top-N to enrich (hard cap {HARD_MAX_HOTELS})."
        ),
    ] = SETTINGS.default_max_hotels,
    adults: Annotated[int, Field(ge=1, le=12)] = SETTINGS.default_adults,
    children: Annotated[int, Field(ge=0, le=8)] = 0,
    child_ages: Annotated[list[int] | None, Field()] = None,
    currency: Annotated[str, Field()] = SETTINGS.default_currency,
    sort_by: Annotated[str, Field()] = SETTINGS.default_sort_by,
    hotel_class: Annotated[list[int] | None, Field()] = None,
    amenities: Annotated[list[str] | None, Field()] = None,
    brands: Annotated[list[str] | None, Field()] = None,
    min_guest_rating: Annotated[float | None, Field()] = None,
    free_cancellation: Annotated[bool, Field()] = False,
    eco_certified: Annotated[bool, Field()] = False,
    special_offers: Annotated[bool, Field()] = False,
    price_min: Annotated[int | None, Field(ge=0)] = None,
    price_max: Annotated[int | None, Field(ge=0)] = None,
    property_type: Annotated[str, Field()] = "HOTELS",
) -> dict[str, Any]:
    """Search plus parallel room/rate/cancellation detail for the top N hotels.

    Use ONLY when the user wants to COMPARE rooms, rates, or cancellation
    across several hotels at once — it costs 1 + N RPCs. Per-hotel failures
    come back inline ('ok': false items) instead of aborting the batch.
    """
    try:
        filters = build_search_filters(
            query,
            check_in=check_in,
            check_out=check_out,
            adults=adults,
            children=children,
            child_ages=child_ages,
            currency=currency,
            sort_by=sort_by,
            hotel_class=hotel_class,
            amenities=amenities,
            brands=brands,
            min_guest_rating=min_guest_rating,
            free_cancellation=free_cancellation,
            eco_certified=eco_certified,
            special_offers=special_offers,
            price_min=price_min,
            price_max=price_max,
            property_type=property_type,
        )
        items = await runtime.get_api().search_with_details(filters, max_hotels=max_hotels)
    except (ToolInputError, GHotelsError, ValueError) as exc:
        return error_envelope("enrich", exc)
    return success_envelope(
        "enrich", filters.model_dump(mode="json"), [dump_enriched(item) for item in items]
    )


@mcp.prompt(
    name="choosing-a-tool",
    description="How to pick between the three Google Hotels tools.",
)
def choosing_a_tool_prompt(user_intent: str = "") -> str:
    """Tool-selection guidance for the calling model."""
    return (
        "Choosing a Google Hotels tool:\n"
        "- `search_hotels` — browsing or filtering hotels in a CITY or area. Start here.\n"
        "- `get_hotel_details` — the user already picked ONE hotel and wants rooms, "
        "rates, or cancellation (needs an entity_key from a prior search).\n"
        "- `search_hotels_with_details` — ONLY to COMPARE rooms/rates/cancellation "
        f"across several hotels at once; keep max_hotels small (3-5; {HARD_MAX_HOTELS} max).\n"
        f"User intent: {user_intent or '(unspecified)'}"
    )


@mcp.prompt(
    name="compare-hotels-in-city",
    description="Workflow: compare rooms and rates for the top hotels in a city.",
)
def compare_hotels_in_city_prompt(
    city: str, check_in: str, check_out: str, max_hotels: int = 5
) -> str:
    """A ready-made comparison workflow."""
    capped = min(max_hotels, HARD_MAX_HOTELS)
    return (
        f"Call `search_hotels_with_details` with query='{city} hotels', "
        f"check_in='{check_in}', check_out='{check_out}', max_hotels={capped}. "
        "Present one row per hotel: name, stars, cheapest rate with provider, "
        "and its cancellation policy."
    )


@mcp.resource(
    "resource://google-hotels-mcp/configuration",
    name="Google Hotels MCP Configuration",
    description="Live defaults and environment variables for this server.",
    mime_type="application/json",
)
def configuration_resource() -> str:
    """The server's live configuration, JSON-encoded."""
    payload = {
        "defaults": SETTINGS.model_dump(),
        "hard_max_hotels": HARD_MAX_HOTELS,
        "environment": ENVIRONMENT_DOC,
    }
    return json.dumps(payload, indent=2)


def run() -> None:
    """Serve over stdio (what MCP clients spawn)."""
    mcp.run(transport="stdio")


def run_http(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve over streamable HTTP (dev / Docker). HOST/PORT env vars win."""
    mcp.run(
        transport="http",
        host=os.getenv("HOST") or host,
        port=int(os.getenv("PORT") or port),
    )


if __name__ == "__main__":
    run()
