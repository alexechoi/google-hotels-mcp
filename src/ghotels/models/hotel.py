"""List-view result models.

Everything here comes from a single search response — no follow-up fetch.
Result models are frozen: they are snapshots of what Google returned, not
mutable working state.
"""

from __future__ import annotations

from datetime import date  # noqa: TC003 - pydantic needs the runtime type

from pydantic import BaseModel, ConfigDict, Field

from ghotels.models.enums import Amenity  # noqa: TC001 - pydantic needs the runtime type


class PriceSnapshot(BaseModel):
    """The cheapest rate Google surfaced for a specific date window."""

    model_config = ConfigDict(frozen=True)

    amount: int
    currency: str
    check_in: date | None = None
    check_out: date | None = None


class CategoryScore(BaseModel):
    """One of Google's five per-category sub-scores."""

    model_config = ConfigDict(frozen=True)

    label: str
    score: float = Field(ge=0.0, le=5.0)


class RatingSummary(BaseModel):
    """Guest-review aggregate for a hotel."""

    model_config = ConfigDict(frozen=True)

    score: float | None = Field(default=None, ge=0.0, le=5.0)
    review_count: int | None = None
    histogram: dict[int, int] = Field(
        default_factory=dict,
        description="Review count per star bucket (1-5).",
    )
    categories: list[CategoryScore] = Field(default_factory=list)


class NearbyPlace(BaseModel):
    """A point of interest near the hotel, with travel-time metadata."""

    model_config = ConfigDict(frozen=True)

    name: str
    travel_mode: str | None = Field(
        default=None, description="'walk', 'drive', 'transit', or 'bike'."
    )
    duration_minutes: int | None = None
    distance_text: str | None = None


class Hotel(BaseModel):
    """One hotel from the search-list response."""

    model_config = ConfigDict(frozen=True)

    name: str
    entity_key: str | None = Field(
        default=None,
        description=(
            "Google's native hotel identifier (an opaque base64 token). Pass it "
            "verbatim to a detail lookup to fetch rooms, rates, and policies."
        ),
    )
    kgmid: str | None = None
    fid: str | None = None
    google_hotel_id: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    star_class: int | None = Field(default=None, ge=1, le=5)
    star_class_label: str | None = None

    price: PriceSnapshot | None = None
    rating: RatingSummary | None = None
    amenities: frozenset[Amenity] = Field(default_factory=frozenset)
    deal_percent: int | None = Field(
        default=None, description="Advertised discount vs typical rate, when Google flags a deal."
    )

    check_in_time: str | None = None
    check_out_time: str | None = None

    nearby: tuple[NearbyPlace, ...] = ()
    image_urls: tuple[str, ...] = ()
