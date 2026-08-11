"""Wire-id table completeness and error taxonomy checks."""

import pytest

from ghotels.errors import (
    GHotelsError,
    MissingEntityKeyError,
    ProtocolError,
    RateLimitedError,
    TransportError,
)
from ghotels.models import Amenity, Brand, MinRating, PropertyType, SortBy
from ghotels.protocol.ids import (
    AMENITY_IDS,
    BRAND_IDS,
    BRAND_SUB_IDS,
    MIN_RATING_IDS,
    PROPERTY_TYPE_IDS,
    SORT_IDS,
    child_age_bucket,
)


class TestWireTables:
    def test_every_amenity_has_an_id(self):
        assert set(AMENITY_IDS) == set(Amenity)

    def test_every_brand_has_id_and_subbrands(self):
        assert set(BRAND_IDS) == set(Brand)
        assert set(BRAND_SUB_IDS) == set(Brand)

    def test_only_four_seasons_lacks_subbrands(self):
        bare = {brand for brand, subs in BRAND_SUB_IDS.items() if not subs}
        assert bare == {Brand.FOUR_SEASONS}

    def test_every_sort_mapped_and_relevance_is_null(self):
        assert set(SORT_IDS) == set(SortBy)
        assert SORT_IDS[SortBy.RELEVANCE] is None

    def test_min_rating_ids_follow_double_encoding(self):
        assert MIN_RATING_IDS[MinRating.THREE_FIVE_PLUS] == 7
        assert MIN_RATING_IDS[MinRating.FOUR_ZERO_PLUS] == 8
        assert MIN_RATING_IDS[MinRating.FOUR_FIVE_PLUS] == 9

    def test_property_types_mapped(self):
        assert set(PROPERTY_TYPE_IDS) == set(PropertyType)


class TestChildAgeBuckets:
    @pytest.mark.parametrize(
        ("age", "bucket"),
        [
            (0, [0, 1]),
            (1, [0, 1]),
            (2, [2, 12]),
            (7, [2, 12]),
            (12, [2, 12]),
            (13, [13, 17]),
            (17, [13, 17]),
        ],
    )
    def test_bucket_boundaries(self, age, bucket):
        assert child_age_bucket(age) == bucket


class TestErrorTaxonomy:
    def test_retryable_flags(self):
        assert TransportError.retryable
        assert RateLimitedError.retryable
        assert not ProtocolError.retryable
        assert not MissingEntityKeyError.retryable
        assert not GHotelsError.retryable

    def test_hierarchy(self):
        assert issubclass(RateLimitedError, TransportError)
        for exc in (TransportError, ProtocolError, MissingEntityKeyError):
            assert issubclass(exc, GHotelsError)
