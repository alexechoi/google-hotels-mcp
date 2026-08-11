"""Unit tests for result models."""

from datetime import date

import pytest
from pydantic import ValidationError

from ghotels.models import (
    Amenity,
    Cancellation,
    CancellationKind,
    Hotel,
    HotelDetail,
    PriceSnapshot,
    Rate,
    RatingSummary,
    Review,
    Room,
)


def make_hotel(**overrides) -> Hotel:
    defaults = {
        "name": "Test Hotel",
        "entity_key": "ChkQ8aH-example",
        "star_class": 4,
        "price": PriceSnapshot(amount=180, currency="USD"),
        "rating": RatingSummary(score=4.4, review_count=1200),
        "amenities": frozenset({Amenity.POOL, Amenity.WIFI}),
    }
    defaults.update(overrides)
    return Hotel(**defaults)


class TestHotel:
    def test_results_are_frozen(self):
        hotel = make_hotel()
        with pytest.raises(ValidationError):
            hotel.name = "Renamed"

    def test_star_class_bounds(self):
        with pytest.raises(ValidationError):
            make_hotel(star_class=6)

    def test_minimal_hotel_needs_only_name(self):
        hotel = Hotel(name="Bare Minimum Inn")
        assert hotel.price is None
        assert hotel.amenities == frozenset()


class TestHotelDetail:
    def test_extends_hotel(self):
        detail = HotelDetail(
            name="Test Hotel",
            address="1 Example St",
            rooms=(
                Room(
                    name="King Room",
                    rates=(
                        Rate(
                            provider="Booking.com",
                            price=150,
                            currency="USD",
                            cancellation=Cancellation(
                                kind=CancellationKind.FREE_UNTIL,
                                free_until=date(2026, 9, 1),
                            ),
                        ),
                    ),
                ),
            ),
        )
        assert isinstance(detail, Hotel)
        assert detail.rooms[0].rates[0].cancellation.kind is CancellationKind.FREE_UNTIL

    def test_default_cancellation_is_unknown(self):
        rate = Rate(provider="Expedia", price=99, currency="USD")
        assert rate.cancellation.kind is CancellationKind.UNKNOWN
        assert rate.cancellation.free_until is None


class TestReview:
    @pytest.mark.parametrize("rating", [0, 6])
    def test_rating_bounds(self, rating):
        with pytest.raises(ValidationError):
            Review(rating=rating, body="text")
