"""Search input models: where, when, who, and how to filter."""

from __future__ import annotations

from datetime import date  # noqa: TC003 - pydantic needs the runtime type

from pydantic import BaseModel, Field, field_validator, model_validator

from ghotels.models.enums import (
    Amenity,
    Brand,
    Currency,
    MinRating,
    PropertyType,
    SortBy,
)

MAX_CHILD_AGE = 17
MAX_STAR_CLASS = 5


class Location(BaseModel):
    """Where to search.

    Plain free text is enough — Google resolves ``query`` to a place and
    scopes results to it. Disambiguate the same way you would in the search
    box (``"paris, texas hotels"`` vs ``"paris, france hotels"``).

    ``kgmid``/``fid`` pin the search to a place already resolved by a prior
    response. Google only honours the pin when the query text itself is
    neutral; a query naming a different city wins over the pin.
    """

    query: str = Field(description="Free-text search, sent verbatim to Google.")
    kgmid: str | None = Field(
        default=None,
        description="Knowledge Graph id such as '/m/05qtj' (Paris) — optional pin.",
    )
    fid: str | None = Field(
        default=None,
        description="Maps feature id such as '0x479f...:0x8c92...' — optional pin.",
    )
    display_name: str | None = Field(
        default=None,
        description="Human-readable place name; informational, echoed by Google.",
    )

    @field_validator("query")
    @classmethod
    def _strip_and_require(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "query must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("kgmid")
    @classmethod
    def _kgmid_shape(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("/m/", "/g/")):
            msg = "kgmid must start with '/m/' or '/g/'"
            raise ValueError(msg)
        return value

    @field_validator("fid")
    @classmethod
    def _fid_shape(cls, value: str | None) -> str | None:
        if value is not None and ("0x" not in value or ":" not in value):
            msg = "fid must look like '0x...:0x...'"
            raise ValueError(msg)
        return value

    @property
    def is_pinned(self) -> bool:
        """Whether a structural place pin should be sent alongside the query."""
        return bool(self.kgmid or self.fid or self.display_name)


class StayDates(BaseModel):
    """Check-in and check-out dates.

    Omit the whole object to get Google's "flexible dates" defaults. When
    provided, ``check_out`` must be after ``check_in``.
    """

    check_in: date
    check_out: date

    @model_validator(mode="after")
    def _ordered(self) -> StayDates:
        if self.check_out <= self.check_in:
            msg = "check_out must be after check_in"
            raise ValueError(msg)
        return self

    @property
    def nights(self) -> int:
        """Number of nights between check-in and check-out."""
        return (self.check_out - self.check_in).days


class Guests(BaseModel):
    """Who is travelling.

    Children are expressed purely as a list of ages — one entry per child —
    so a child count can never disagree with the ages provided.
    """

    adults: int = Field(default=2, ge=1, le=12)
    child_ages: list[int] = Field(
        default_factory=list,
        description="One age (0-17) per travelling child.",
        max_length=8,
    )

    @field_validator("child_ages")
    @classmethod
    def _ages_in_range(cls, value: list[int]) -> list[int]:
        for age in value:
            if not 0 <= age <= MAX_CHILD_AGE:
                msg = f"child ages must be 0-{MAX_CHILD_AGE}, got {age}"
                raise ValueError(msg)
        return value

    @property
    def children(self) -> int:
        """Number of travelling children."""
        return len(self.child_ages)

    @property
    def total(self) -> int:
        """Total occupants (adults + children)."""
        return self.adults + self.children


class SearchFilters(BaseModel):
    """Complete input for one hotel search.

    Only ``location`` is required. Everything else narrows or reorders the
    results; unset filters fall back to Google's defaults.
    """

    location: Location
    dates: StayDates | None = None
    guests: Guests = Field(default_factory=Guests)
    currency: Currency = Currency.USD

    property_type: PropertyType = PropertyType.HOTELS
    sort_by: SortBy = SortBy.RELEVANCE
    amenities: list[Amenity] = Field(default_factory=list)
    brands: list[Brand] = Field(default_factory=list)
    star_classes: list[int] = Field(
        default_factory=list,
        description="Star classes to include, e.g. [4, 5].",
    )
    min_rating: MinRating | None = None
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    free_cancellation: bool = False
    eco_certified: bool = False
    special_offers: bool = False

    @field_validator("star_classes")
    @classmethod
    def _stars_in_range(cls, value: list[int]) -> list[int]:
        for star in value:
            if not 1 <= star <= MAX_STAR_CLASS:
                msg = f"star classes must be 1-{MAX_STAR_CLASS}, got {star}"
                raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _price_band_ordered(self) -> SearchFilters:
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            msg = "price_min must not exceed price_max"
            raise ValueError(msg)
        return self
