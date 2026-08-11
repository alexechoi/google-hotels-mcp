"""ghotels — Google Hotels for AI agents and the terminal.

An MCP server, CLI, and typed Python library that talk directly to Google's
internal ``batchexecute`` RPC — no HTML scraping, no headless browser.
"""

from importlib.metadata import PackageNotFoundError, version

from ghotels.models import (
    Amenity,
    Brand,
    Cancellation,
    CancellationKind,
    CategoryScore,
    Currency,
    Guests,
    Hotel,
    HotelDetail,
    Location,
    MinRating,
    NearbyPlace,
    PriceSnapshot,
    PropertyType,
    Rate,
    RatingSummary,
    Review,
    Room,
    SearchFilters,
    SortBy,
    StayDates,
)

try:
    __version__ = version("ghotels")
except PackageNotFoundError:  # pragma: no cover - only when running from a raw checkout
    __version__ = "0.0.0.dev0"

__all__ = [
    "Amenity",
    "Brand",
    "Cancellation",
    "CancellationKind",
    "CategoryScore",
    "Currency",
    "Guests",
    "Hotel",
    "HotelDetail",
    "Location",
    "MinRating",
    "NearbyPlace",
    "PriceSnapshot",
    "PropertyType",
    "Rate",
    "RatingSummary",
    "Review",
    "Room",
    "SearchFilters",
    "SortBy",
    "StayDates",
    "__version__",
]
