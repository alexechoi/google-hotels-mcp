"""Deadline resolution and cancellation classification tests.

Everything here is wall-clock independent by construction — the reference
date is always explicit. This is the bug class that broke the original
project's CI (a golden test started failing the day a captured deadline
passed).
"""

from datetime import date

import pytest

from ghotels.models.detail import CancellationKind
from ghotels.parsing.cancellation import (
    cancellation_from_slot,
    cancellation_from_text,
    resolve_deadline,
)

SEPTEMBER_STAY = date(2026, 9, 10)
JANUARY_STAY = date(2027, 1, 5)


class TestResolveDeadline:
    def test_yearless_takes_reference_year(self):
        assert resolve_deadline("Sep 8", SEPTEMBER_STAY) == date(2026, 9, 8)

    def test_explicit_year_wins(self):
        assert resolve_deadline("Apr 24, 2026", JANUARY_STAY) == date(2026, 4, 24)
        assert resolve_deadline("April 24 2026", JANUARY_STAY) == date(2026, 4, 24)

    def test_december_deadline_for_january_stay_lands_in_prior_year(self):
        assert resolve_deadline("Dec 28", JANUARY_STAY) == date(2026, 12, 28)

    def test_deadline_just_after_checkin_stays_in_reference_year(self):
        assert resolve_deadline("Sep 11", SEPTEMBER_STAY) == date(2026, 9, 11)

    def test_full_month_names(self):
        assert resolve_deadline("December 5", JANUARY_STAY) == date(2026, 12, 5)

    def test_no_reference_yields_none_not_a_guess(self):
        assert resolve_deadline("Apr 24", None) is None

    @pytest.mark.parametrize("junk", ["", "tomorrow", "Foo 12", "Apr 99"])
    def test_unparseable_text(self, junk):
        assert resolve_deadline(junk, SEPTEMBER_STAY) is None


class TestCancellationFromSlot:
    def test_free_until_tuple(self):
        c = cancellation_from_slot([True, "Sep 8", "11:59 PM"], SEPTEMBER_STAY)
        assert c.kind is CancellationKind.FREE_UNTIL
        assert c.free_until == date(2026, 9, 8)
        assert c.description == "Free cancellation until Sep 8 11:59 PM"

    def test_false_flag_is_non_refundable(self):
        c = cancellation_from_slot([False], SEPTEMBER_STAY)
        assert c.kind is CancellationKind.NON_REFUNDABLE

    def test_true_without_date_is_free(self):
        assert cancellation_from_slot([True], SEPTEMBER_STAY).kind is CancellationKind.FREE

    @pytest.mark.parametrize("raw", [None, [], "text", 42])
    def test_unrecognized_slot_is_unknown(self, raw):
        assert cancellation_from_slot(raw, SEPTEMBER_STAY).kind is CancellationKind.UNKNOWN


class TestCancellationFromText:
    def test_free_until_label(self):
        c = cancellation_from_text("\n  Free cancellation until Apr 25\n ", date(2026, 5, 1))
        assert c is not None
        assert c.kind is CancellationKind.FREE_UNTIL
        assert c.free_until == date(2026, 4, 25)

    def test_generic_free(self):
        c = cancellation_from_text("Free cancellation", SEPTEMBER_STAY)
        assert c is not None
        assert c.kind is CancellationKind.FREE

    def test_partial(self):
        c = cancellation_from_text("Partially refundable", SEPTEMBER_STAY)
        assert c is not None
        assert c.kind is CancellationKind.PARTIAL_REFUND

    def test_non_refundable(self):
        c = cancellation_from_text("Non-refundable", SEPTEMBER_STAY)
        assert c is not None
        assert c.kind is CancellationKind.NON_REFUNDABLE

    @pytest.mark.parametrize("text", ["", "   ", "Great location"])
    def test_non_policy_text(self, text):
        assert cancellation_from_text(text, SEPTEMBER_STAY) is None
