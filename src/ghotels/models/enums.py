"""Semantic enums for search filters.

Every enum here uses a human-readable value so that CLI flags, MCP tool
arguments, and library callers all speak the same vocabulary. The numeric
wire identifiers Google expects live in :mod:`ghotels.protocol.ids` — the
domain layer never sees them.
"""

from __future__ import annotations

from enum import Enum


class Currency(str, Enum):
    """ISO 4217 currencies the Google Hotels endpoint accepts.

    The currency code is embedded in the request's filter record and echoed
    back in every price the response carries.
    """

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    AUD = "AUD"
    CAD = "CAD"
    CHF = "CHF"
    CNY = "CNY"
    HKD = "HKD"
    INR = "INR"
    KRW = "KRW"
    MXN = "MXN"
    NZD = "NZD"
    SEK = "SEK"
    SGD = "SGD"
    ZAR = "ZAR"


class PropertyType(str, Enum):
    """Kind of property to search for."""

    HOTELS = "HOTELS"
    VACATION_RENTALS = "VACATION_RENTALS"


class SortBy(str, Enum):
    """Result ordering.

    ``RELEVANCE`` is Google's default ("Recommended") and has no explicit
    wire value — the request simply omits a sort id.
    """

    RELEVANCE = "RELEVANCE"
    LOWEST_PRICE = "LOWEST_PRICE"
    HIGHEST_RATING = "HIGHEST_RATING"
    MOST_REVIEWED = "MOST_REVIEWED"


class MinRating(str, Enum):
    """Minimum guest-rating filter (Google offers exactly these three steps)."""

    THREE_FIVE_PLUS = "THREE_FIVE_PLUS"
    FOUR_ZERO_PLUS = "FOUR_ZERO_PLUS"
    FOUR_FIVE_PLUS = "FOUR_FIVE_PLUS"


class Amenity(str, Enum):
    """Amenity filters confirmed to work against the live endpoint."""

    PARKING = "PARKING"
    INDOOR_POOL = "INDOOR_POOL"
    OUTDOOR_POOL = "OUTDOOR_POOL"
    POOL = "POOL"
    GYM = "GYM"
    RESTAURANT = "RESTAURANT"
    BREAKFAST = "BREAKFAST"
    SPA = "SPA"
    BEACH_ACCESS = "BEACH_ACCESS"
    KID_FRIENDLY = "KID_FRIENDLY"
    BAR = "BAR"
    PET_FRIENDLY = "PET_FRIENDLY"
    ROOM_SERVICE = "ROOM_SERVICE"
    WIFI = "WIFI"
    AIR_CONDITIONED = "AIR_CONDITIONED"
    ALL_INCLUSIVE = "ALL_INCLUSIVE"
    WHEELCHAIR_ACCESSIBLE = "WHEELCHAIR_ACCESSIBLE"
    EV_CHARGER = "EV_CHARGER"


class Brand(str, Enum):
    """Hotel brand families with confirmed wire identifiers."""

    IHG = "IHG"
    BEST_WESTERN = "BEST_WESTERN"
    CHOICE = "CHOICE"
    HILTON = "HILTON"
    ACCOR = "ACCOR"
    HYATT = "HYATT"
    MARRIOTT = "MARRIOTT"
    WYNDHAM = "WYNDHAM"
    FOUR_SEASONS = "FOUR_SEASONS"
