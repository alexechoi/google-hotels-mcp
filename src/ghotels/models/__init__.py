"""Typed domain models for Google Hotels searches and results.

The models here are pure domain objects: they know nothing about Google's
wire format. Translating them to and from the ``batchexecute`` RPC lives in
:mod:`ghotels.protocol` and :mod:`ghotels.parsing`.
"""

from ghotels.models.detail import (
    Cancellation,
    CancellationKind,
    HotelDetail,
    Rate,
    Review,
    Room,
)
from ghotels.models.enums import (
    Amenity,
    Brand,
    Currency,
    MinRating,
    PropertyType,
    SortBy,
)
from ghotels.models.filters import Guests, Location, SearchFilters, StayDates
from ghotels.models.hotel import (
    CategoryScore,
    Hotel,
    NearbyPlace,
    PriceSnapshot,
    RatingSummary,
)

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
]
