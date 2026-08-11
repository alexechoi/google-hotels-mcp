"""Detail-page result models: rooms, per-provider rates, policies, reviews."""

from __future__ import annotations

from datetime import date  # noqa: TC003 - pydantic needs the runtime type
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ghotels.models.hotel import Hotel


class CancellationKind(str, Enum):
    """Cancellation policy categories Google surfaces on rate plans."""

    FREE = "free"
    FREE_UNTIL = "free_until"
    PARTIAL_REFUND = "partial_refund"
    NON_REFUNDABLE = "non_refundable"
    UNKNOWN = "unknown"


class Cancellation(BaseModel):
    """Cancellation terms attached to a single rate plan."""

    model_config = ConfigDict(frozen=True)

    kind: CancellationKind = CancellationKind.UNKNOWN
    free_until: date | None = Field(
        default=None,
        description="Last date on which cancellation is free (kind == FREE_UNTIL).",
    )
    description: str | None = Field(
        default=None, description="Raw label Google displayed, when captured."
    )


class Rate(BaseModel):
    """One bookable offer: a specific provider's price for a room."""

    model_config = ConfigDict(frozen=True)

    provider: str = Field(description="e.g. 'Booking.com', 'Expedia', 'Direct (Hilton)'.")
    price: int
    currency: str
    cancellation: Cancellation = Field(default_factory=Cancellation)
    breakfast_included: bool = False
    includes_taxes_and_fees: bool = False
    booking_url: str | None = None


class Room(BaseModel):
    """One bookable room configuration."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str | None = None
    bed_config: str | None = Field(default=None, description="e.g. '1 King Bed'.")
    max_occupancy: int | None = Field(default=None, ge=1)
    rates: tuple[Rate, ...] = Field(default=(), description="Sorted cheapest first.")


class Review(BaseModel):
    """One guest review sampled in the detail response."""

    model_config = ConfigDict(frozen=True)

    author: str | None = None
    rating: int = Field(ge=1, le=5)
    body: str
    review_date: date | None = None
    source: str | None = Field(default=None, description="e.g. 'Google', 'Booking.com'.")


class HotelDetail(Hotel):
    """Full per-property record from a detail lookup.

    Extends :class:`~ghotels.models.hotel.Hotel` with fields only the detail
    response exposes.
    """

    description: str | None = None
    address: str | None = None
    phone: str | None = None

    rooms: tuple[Room, ...] = ()
    amenity_labels: tuple[str, ...] = Field(
        default=(),
        description="Human-readable amenity labels beyond the filterable amenity set.",
    )
    nearby_attractions: tuple[str, ...] = ()
    reviews: tuple[Review, ...] = ()
