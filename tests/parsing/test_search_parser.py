"""Search-response parsing: live-captured golden plus synthetic edge cases."""

import json
from pathlib import Path

from ghotels.models import Amenity
from ghotels.parsing import parse_search_response
from ghotels.parsing.entry import extract_kgmid, find_hotel_entries

FIXTURES = Path(__file__).parent.parent / "fixtures"


def normalize(hotel):
    data = hotel.model_dump(mode="json")
    data["amenities"] = sorted(data["amenities"])
    return data


class TestGolden:
    """Pin the full parse of a live-captured response (New York, Sep 2026)."""

    def test_parse_is_stable(self):
        inner = json.loads((FIXTURES / "search_response.json").read_text())
        golden = json.loads((FIXTURES / "search_parsed_golden.json").read_text())
        assert [normalize(h) for h in parse_search_response(inner)] == golden

    def test_golden_sanity(self):
        golden = json.loads((FIXTURES / "search_parsed_golden.json").read_text())
        assert len(golden) == 20
        assert all(h["name"] for h in golden)
        assert all(h["entity_key"] for h in golden)
        priced = [h for h in golden if h["price"]]
        assert len(priced) >= 15
        assert all(h["price"]["currency"] == "USD" for h in priced)


def make_entry(name="Test Hotel", *, entity_key="ChkI-abc", fid="0x1:0x2", stars=4):
    """Build a minimal synthetic hotel entry (48 slots)."""
    entry = [None] * 48
    entry[1] = name
    entry[2] = [[40.7, -74.0]]
    entry[3] = [f"{stars}-star hotel", stars]
    entry[9] = fid
    entry[20] = entity_key
    return entry


class TestEntryDetection:
    def test_minimal_entry_found(self):
        assert len(find_hotel_entries([[make_entry()]])) == 1

    def test_starless_hotels_are_kept(self):
        entry = make_entry(stars=4)
        entry[3] = None
        hotels = parse_search_response([entry])
        assert len(hotels) == 1
        assert hotels[0].star_class is None

    def test_entry_without_identifiers_rejected(self):
        entry = make_entry()
        entry[9] = None
        entry[20] = None
        assert find_hotel_entries([entry]) == []

    def test_entry_without_coords_rejected(self):
        entry = make_entry()
        entry[2] = [None]
        assert find_hotel_entries([entry]) == []

    def test_fid_only_entry_accepted(self):
        entry = make_entry(entity_key=None)
        assert len(find_hotel_entries([entry])) == 1


class TestDeduplication:
    def test_duplicate_fid_dropped(self):
        tree = [make_entry(entity_key=None), make_entry(entity_key=None, name="Duplicate")]
        hotels = parse_search_response(tree)
        assert [h.name for h in hotels] == ["Test Hotel"]

    def test_unidentifiable_hotels_kept(self):
        first = make_entry(entity_key="zzz-not-decodable", fid=None)
        second = make_entry(entity_key="zzz-not-decodable", fid=None, name="Also Kept")
        hotels = parse_search_response([first, second])
        assert len(hotels) == 2


class TestFieldExtraction:
    def test_amenity_bits_map_to_enums(self):
        entry = make_entry()
        entry[10] = [[[True, 6], [False, 10], [True, 35], [True, 9999]]]
        (hotel,) = parse_search_response([entry])
        assert hotel.amenities == frozenset({Amenity.POOL, Amenity.WIFI})

    def test_price_requires_currency(self):
        entry = make_entry()
        entry[6] = [None, [[250, 0], None, None, None, None]]
        (hotel,) = parse_search_response([entry])
        assert hotel.price is None

    def test_display_price_wins_over_pair(self):
        entry = make_entry()
        entry[6] = [
            None,
            [[250, 0], None, None, "USD", [[2026, 9, 10], [2026, 9, 13]]],
            [None, [None, None, None, None, 240]],
        ]
        (hotel,) = parse_search_response([entry])
        assert hotel.price is not None
        assert hotel.price.amount == 240
        assert hotel.price.currency == "USD"
        assert hotel.price.check_in.isoformat() == "2026-09-10"


class TestKgmidExtraction:
    def test_from_live_entity_keys(self):
        golden = json.loads((FIXTURES / "search_parsed_golden.json").read_text())
        keyed = [h for h in golden if h["entity_key"]]
        decoded = [h for h in keyed if h["kgmid"]]
        assert len(decoded) >= len(keyed) - 2
        assert all(h["kgmid"].startswith(("/g/", "/m/")) for h in decoded)

    def test_garbage_returns_none(self):
        assert extract_kgmid("!!!not-base64!!!") is None
        assert extract_kgmid("aGVsbG8=") is None
