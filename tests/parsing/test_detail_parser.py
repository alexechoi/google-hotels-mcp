"""Detail-response parsing: live-captured golden plus synthetic edge cases."""

import json
from datetime import date
from pathlib import Path

import pytest

from ghotels.errors import ProtocolError
from ghotels.models.detail import CancellationKind
from ghotels.parsing import parse_detail_response

FIXTURES = Path(__file__).parent.parent / "fixtures"

REFERENCE = date(2026, 9, 10)


def normalize(detail):
    data = detail.model_dump(mode="json")
    data["amenities"] = sorted(data["amenities"])
    return data


class TestGolden:
    """Pin the full parse of a live-captured detail response."""

    def test_parse_is_stable(self):
        inner = json.loads((FIXTURES / "detail_response.json").read_text())
        golden = json.loads((FIXTURES / "detail_parsed_golden.json").read_text())
        parsed = parse_detail_response(inner, requested_currency="USD", reference=REFERENCE)
        assert normalize(parsed) == golden

    def test_golden_sanity(self):
        golden = json.loads((FIXTURES / "detail_parsed_golden.json").read_text())
        assert golden["name"] == "Mandarin Oriental, New York"
        assert golden["address"].startswith("80 Columbus Cir")
        assert golden["phone"].startswith("+1")
        assert golden["description"]
        (room,) = golden["rooms"]
        assert len(room["rates"]) == 4
        prices = [rate["price"] for rate in room["rates"]]
        assert prices == sorted(prices)
        assert all(rate["currency"] == "USD" for rate in room["rates"])
        deadlines = [rate["cancellation"]["free_until"] for rate in room["rates"]]
        assert all(d and d.startswith("2026-09-0") for d in deadlines)
        assert len(golden["reviews"]) == 2
        assert all(review["body"] for review in golden["reviews"])


def make_detail_entry():
    """Synthetic single-hotel detail entry with one provider."""
    entry = [None] * 48
    entry[1] = "Detail Hotel"
    entry[2] = [[40.7, -74.0], [[["1 Test St, Test City"]]], ["+1 555-0100"]]
    entry[9] = "0x1:0x2"
    entry[11] = ["A lovely test property."]
    entry[20] = "ChkI-detail"
    provider = [
        ["Booking.com", None, "/aclk?deeplink"],
        [
            [
                "King Room",
                None,
                [
                    [None, None, [True, "Sep 8", "11:59 PM"], None, [None, None, None, None, 180]],
                    [None, None, [False], None, [None, None, None, None, 150]],
                ],
            ],
        ],
    ]
    entry[6] = [None, None, [None, None, [provider]]]
    return entry


class TestSyntheticDetail:
    def test_cheapest_rate_and_its_own_cancellation_win(self):
        detail = parse_detail_response([make_detail_entry()], reference=REFERENCE)
        (room,) = detail.rooms
        (rate,) = room.rates
        assert rate.price == 150
        assert rate.cancellation.kind is CancellationKind.NON_REFUNDABLE
        assert rate.booking_url == "https://www.google.com/aclk?deeplink"

    def test_requested_currency_propagates_to_rates(self):
        """Detail responses carry no currency — the request context must (fix PR #5)."""
        detail = parse_detail_response(
            [make_detail_entry()], requested_currency="EUR", reference=REFERENCE
        )
        assert detail.rooms[0].rates[0].currency == "EUR"

    def test_currency_defaults_to_usd(self):
        detail = parse_detail_response([make_detail_entry()], reference=REFERENCE)
        assert detail.rooms[0].rates[0].currency == "USD"

    def test_address_phone_description(self):
        detail = parse_detail_response([make_detail_entry()], reference=REFERENCE)
        assert detail.address == "1 Test St, Test City"
        assert detail.phone == "+1 555-0100"
        assert detail.description == "A lovely test property."

    def test_no_entry_raises_protocol_error(self):
        with pytest.raises(ProtocolError, match="no hotel entry"):
            parse_detail_response([["not", "a", "hotel"]])


class TestAmenityLabels:
    def test_structured_labels_parsed_and_cleaned(self):
        entry = make_detail_entry()
        entry[10] = [
            [
                [None, [["<b>Free Wi-Fi</b>"], ["Pool &amp; spa"]]],
                [None, [["Free Wi-Fi"], ["  Breakfast   buffet  "]]],
            ]
        ]
        detail = parse_detail_response([entry], reference=REFERENCE)
        assert detail.amenity_labels == ("Free Wi-Fi", "Pool & spa", "Breakfast buffet")

    def test_absent_label_groups_yield_empty(self):
        """Live responses often carry no label records — never invent labels."""
        detail = parse_detail_response([make_detail_entry()], reference=REFERENCE)
        assert detail.amenity_labels == ()


class TestReviews:
    def test_segmented_body_with_author(self):
        entry = make_detail_entry()
        entry[7] = [
            None,
            None,
            None,
            [
                [
                    [["“Loved the ", False], ["pool", True], [" and the staff.”", False]],
                    ["https://avatar.example/img", 40, 40],
                    "Jane D",
                ],
            ],
        ]
        detail = parse_detail_response([entry], reference=REFERENCE)
        (review,) = detail.reviews
        assert review.body == "“Loved the pool and the staff.”"
        assert review.author == "Jane D"
        assert review.rating is None
