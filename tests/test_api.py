"""API facade tests over captured fixtures and scripted transports."""

import json
from datetime import date
from pathlib import Path

import pytest

from ghotels.api import AsyncGoogleHotels, GoogleHotels, _stable_sort
from ghotels.errors import ProtocolError, TransportError
from ghotels.models import (
    Currency,
    Hotel,
    Location,
    PriceSnapshot,
    RatingSummary,
    SearchFilters,
    SortBy,
    StayDates,
)

FIXTURES = Path(__file__).parent / "fixtures"
DATES = StayDates(check_in=date(2026, 9, 10), check_out=date(2026, 9, 13))


class ScriptedTransport:
    """Returns canned inner payloads; entity-key-aware for detail calls."""

    def __init__(self, search_inner=None, detail_inner=None, failures=None):
        self.search_inner = search_inner
        self.detail_inner = detail_inner
        self.failures = failures or {}
        self.detail_keys = []

    async def post_rpc(self, rpc_id, payload):
        entity_key = payload[2][5]
        if entity_key is None:
            return self.search_inner
        self.detail_keys.append(entity_key)
        if entity_key in self.failures:
            raise self.failures[entity_key]
        return self.detail_inner

    async def aclose(self):
        pass


@pytest.fixture(scope="module")
def search_inner():
    return json.loads((FIXTURES / "search_response.json").read_text())


@pytest.fixture(scope="module")
def detail_inner():
    return json.loads((FIXTURES / "detail_response.json").read_text())


def make_hotel(name, price=None, score=None, reviews=None):
    return Hotel(
        name=name,
        price=PriceSnapshot(amount=price, currency="USD") if price is not None else None,
        rating=(
            RatingSummary(score=score, review_count=reviews)
            if score is not None or reviews is not None
            else None
        ),
    )


class TestStableSort:
    def test_lowest_price_none_last(self):
        hotels = [make_hotel("b", 200), make_hotel("x"), make_hotel("a", 100)]
        assert [h.name for h in _stable_sort(hotels, SortBy.LOWEST_PRICE)] == ["a", "b", "x"]

    def test_highest_rating(self):
        hotels = [make_hotel("mid", score=4.1), make_hotel("none"), make_hotel("top", score=4.9)]
        assert [h.name for h in _stable_sort(hotels, SortBy.HIGHEST_RATING)] == [
            "top",
            "mid",
            "none",
        ]

    def test_most_reviewed(self):
        hotels = [make_hotel("few", reviews=10), make_hotel("many", reviews=9000)]
        assert [h.name for h in _stable_sort(hotels, SortBy.MOST_REVIEWED)] == ["many", "few"]

    def test_relevance_keeps_order(self):
        hotels = [make_hotel("z", 900), make_hotel("a", 100)]
        assert _stable_sort(hotels, SortBy.RELEVANCE) == hotels

    def test_ties_are_stable(self):
        hotels = [make_hotel("first", 100), make_hotel("second", 100)]
        assert [h.name for h in _stable_sort(hotels, SortBy.LOWEST_PRICE)] == ["first", "second"]


class TestAsyncApi:
    async def test_search_parses_and_sorts(self, search_inner):
        api = AsyncGoogleHotels(ScriptedTransport(search_inner=search_inner))
        filters = SearchFilters(
            location=Location(query="new york hotels"), sort_by=SortBy.LOWEST_PRICE
        )
        hotels = await api.search(filters)
        assert len(hotels) == 20
        prices = [h.price.amount for h in hotels if h.price]
        assert prices == sorted(prices)

    async def test_details_roundtrip(self, detail_inner):
        api = AsyncGoogleHotels(ScriptedTransport(detail_inner=detail_inner))
        detail = await api.details("ChkI-x", dates=DATES, currency=Currency.USD)
        assert detail.name == "Mandarin Oriental, New York"
        assert detail.rooms[0].rates[0].currency == "USD"

    async def test_search_with_details_requires_dates(self, search_inner):
        api = AsyncGoogleHotels(ScriptedTransport(search_inner=search_inner))
        with pytest.raises(ValueError, match=r"requires filters\.dates"):
            await api.search_with_details(SearchFilters(location=Location(query="x")))

    async def test_enrich_captures_per_hotel_failures(self, search_inner, detail_inner):
        transport = ScriptedTransport(search_inner=search_inner, detail_inner=detail_inner)
        api = AsyncGoogleHotels(transport)
        filters = SearchFilters(location=Location(query="new york hotels"), dates=DATES)

        probe = await api.search(filters)
        transport.failures = {
            probe[0].entity_key: TransportError("boom"),
            probe[1].entity_key: ProtocolError("bad shape"),
        }
        enriched = await api.search_with_details(filters, max_hotels=4)

        assert len(enriched) == 4
        assert not enriched[0].ok
        assert enriched[0].retryable
        assert "TransportError" in enriched[0].error
        assert not enriched[1].ok
        assert not enriched[1].retryable
        assert enriched[2].ok
        assert enriched[3].ok

    async def test_enrich_propagates_programmer_errors(self, search_inner):
        class ExplodingTransport(ScriptedTransport):
            async def post_rpc(self, rpc_id, payload):
                if payload[2][5] is not None:
                    raise ZeroDivisionError
                return self.search_inner

        api = AsyncGoogleHotels(ExplodingTransport(search_inner=search_inner))
        filters = SearchFilters(location=Location(query="new york hotels"), dates=DATES)
        with pytest.raises(ZeroDivisionError):
            await api.search_with_details(filters, max_hotels=1)


class TestSyncFacade:
    def test_search_and_close(self, search_inner):
        with GoogleHotels(ScriptedTransport(search_inner=search_inner)) as api:
            hotels = api.search(SearchFilters(location=Location(query="new york hotels")))
            assert len(hotels) == 20

    def test_close_is_idempotent(self, search_inner):
        api = GoogleHotels(ScriptedTransport(search_inner=search_inner))
        api.close()
        api.close()
