"""Unit tests for search input models."""

from datetime import date

import pytest
from pydantic import ValidationError

from ghotels.models import Guests, Location, SearchFilters, StayDates


class TestLocation:
    def test_query_is_stripped(self):
        assert Location(query="  tokyo hotels  ").query == "tokyo hotels"

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_empty_query_rejected(self, bad):
        with pytest.raises(ValidationError, match="query must not be empty"):
            Location(query=bad)

    @pytest.mark.parametrize("kgmid", ["/m/05qtj", "/g/1tfbypzs"])
    def test_valid_kgmid_accepted(self, kgmid):
        assert Location(query="paris", kgmid=kgmid).kgmid == kgmid

    def test_bad_kgmid_rejected(self):
        with pytest.raises(ValidationError, match="kgmid"):
            Location(query="paris", kgmid="05qtj")

    def test_bad_fid_rejected(self):
        with pytest.raises(ValidationError, match="fid"):
            Location(query="paris", fid="not-a-fid")

    def test_pin_detection(self):
        assert not Location(query="paris").is_pinned
        assert Location(query="paris", kgmid="/m/05qtj").is_pinned
        assert Location(query="paris", display_name="Paris").is_pinned


class TestStayDates:
    def test_nights(self):
        dates = StayDates(check_in=date(2026, 9, 1), check_out=date(2026, 9, 4))
        assert dates.nights == 3

    def test_iso_strings_accepted(self):
        dates = StayDates.model_validate({"check_in": "2026-09-01", "check_out": "2026-09-04"})
        assert dates.check_in == date(2026, 9, 1)

    def test_checkout_must_follow_checkin(self):
        with pytest.raises(ValidationError, match="check_out must be after check_in"):
            StayDates(check_in=date(2026, 9, 4), check_out=date(2026, 9, 4))


class TestGuests:
    def test_defaults(self):
        guests = Guests()
        assert guests.adults == 2
        assert guests.children == 0
        assert guests.total == 2

    def test_children_derived_from_ages(self):
        guests = Guests(adults=2, child_ages=[7, 10])
        assert guests.children == 2
        assert guests.total == 4

    @pytest.mark.parametrize("age", [-1, 18])
    def test_child_age_bounds(self, age):
        with pytest.raises(ValidationError, match="child ages"):
            Guests(child_ages=[age])

    @pytest.mark.parametrize("adults", [0, 13])
    def test_adult_bounds(self, adults):
        with pytest.raises(ValidationError):
            Guests(adults=adults)


class TestSearchFilters:
    def test_minimal(self):
        filters = SearchFilters(location=Location(query="tokyo hotels"))
        assert filters.guests.adults == 2
        assert filters.dates is None

    @pytest.mark.parametrize("star", [0, 6])
    def test_star_class_bounds(self, star):
        with pytest.raises(ValidationError, match="star classes"):
            SearchFilters(location=Location(query="x"), star_classes=[star])

    def test_price_band_order_enforced(self):
        with pytest.raises(ValidationError, match="price_min must not exceed price_max"):
            SearchFilters(location=Location(query="x"), price_min=300, price_max=100)

    def test_open_ended_price_band_allowed(self):
        filters = SearchFilters(location=Location(query="x"), price_max=150)
        assert filters.price_min is None
        assert filters.price_max == 150
