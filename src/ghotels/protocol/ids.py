"""Wire identifiers for the Google Hotels ``batchexecute`` RPC.

This module is the single place where domain enums meet Google's numeric
IDs. Everything here was confirmed against the live endpoint — either by
intercepting the Google Hotels UI's own requests or by live probing (see
``docs/PROTOCOL.md`` for provenance and the full slot map).
"""

from __future__ import annotations

from typing import Final

from ghotels.models.enums import Amenity, Brand, MinRating, PropertyType, SortBy

AMENITY_IDS: Final[dict[Amenity, int]] = {
    Amenity.PARKING: 1,
    Amenity.INDOOR_POOL: 4,
    Amenity.OUTDOOR_POOL: 5,
    Amenity.POOL: 6,
    Amenity.GYM: 7,
    Amenity.RESTAURANT: 8,
    Amenity.BREAKFAST: 9,
    Amenity.SPA: 10,
    Amenity.BEACH_ACCESS: 11,
    Amenity.KID_FRIENDLY: 12,
    Amenity.BAR: 15,
    Amenity.PET_FRIENDLY: 19,
    Amenity.ROOM_SERVICE: 22,
    Amenity.WIFI: 35,
    Amenity.AIR_CONDITIONED: 40,
    Amenity.ALL_INCLUSIVE: 52,
    Amenity.WHEELCHAIR_ACCESSIBLE: 53,
    Amenity.EV_CHARGER: 61,
}

BRAND_IDS: Final[dict[Brand, int]] = {
    Brand.IHG: 17,
    Brand.BEST_WESTERN: 18,
    Brand.CHOICE: 20,
    Brand.HILTON: 28,
    Brand.ACCOR: 33,
    Brand.HYATT: 37,
    Brand.MARRIOTT: 46,
    Brand.WYNDHAM: 53,
    Brand.FOUR_SEASONS: 289,
}

# The brand filter is only honoured when the family's sub-brand IDs are
# enumerated alongside it — Google silently ignores a bare family ID with an
# empty sub-list (confirmed live: [[28, []]] returned non-Hilton results).
# Four Seasons is the exception: it has no sub-brands and is sent as a bare
# one-element pair.
BRAND_SUB_IDS: Final[dict[Brand, tuple[int, ...]]] = {
    Brand.IHG: (125, 52, 42, 282, 64, 56, 87, 2, 127, 298),
    Brand.BEST_WESTERN: (155, 104, 105, 254, 255, 107),
    Brand.CHOICE: (63, 112, 27, 113, 82, 78, 23, 293),
    Brand.HILTON: (114, 7, 151, 81, 88, 115, 71, 95, 54, 36, 77, 295, 285, 286, 41),
    Brand.ACCOR: (8, 84),
    Brand.HYATT: (116, 412, 288, 119, 120, 121, 122, 349, 118, 346, 262),
    Brand.MARRIOTT: (
        128,
        60,
        59,
        86,
        153,
        256,
        134,
        58,
        135,
        26,
        72,
        61,
        129,
        131,
        75,
        3,
        12,
        83,
        136,
        143,
        40,
        137,
        39,
    ),
    Brand.WYNDHAM: (30, 19, 38, 11, 49, 50, 93, 284, 16, 65, 68, 150, 141),
    Brand.FOUR_SEASONS: (),
}

# RELEVANCE is Google's default and has no wire value — the sort slot simply
# stays null.
SORT_IDS: Final[dict[SortBy, int | None]] = {
    SortBy.RELEVANCE: None,
    SortBy.LOWEST_PRICE: 3,
    SortBy.HIGHEST_RATING: 8,
    SortBy.MOST_REVIEWED: 13,
}

# Encoded as round(rating * 2): 3.5+ -> 7, 4.0+ -> 8, 4.5+ -> 9.
MIN_RATING_IDS: Final[dict[MinRating, int]] = {
    MinRating.THREE_FIVE_PLUS: 7,
    MinRating.FOUR_ZERO_PLUS: 8,
    MinRating.FOUR_FIVE_PLUS: 9,
}

PROPERTY_TYPE_IDS: Final[dict[PropertyType, int]] = {
    PropertyType.HOTELS: 1,
    PropertyType.VACATION_RENTALS: 2,
}

# Each adult in the party block is a bare [3] marker.
ADULT_MARKER: Final = 3

_CHILD_BUCKETS: Final[tuple[tuple[int, int], ...]] = ((0, 1), (2, 12), (13, 17))


def child_age_bucket(age: int) -> list[int]:
    """Map a child age to Google's ``[low, high]`` age-bucket pair.

    The 2-12 bucket is confirmed from captured UI requests; 0-1 and 13-17
    follow the observed boundary pattern.
    """
    for low, high in _CHILD_BUCKETS:
        if low <= age <= high:
            return [low, high]
    return [age, age]
