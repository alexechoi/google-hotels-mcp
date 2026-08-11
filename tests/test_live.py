"""Live end-to-end tests against the real endpoint (``pytest --live``)."""

from datetime import date, timedelta

import pytest

from ghotels import AsyncGoogleHotels
from ghotels.models import Currency, Guests, Location, SearchFilters, SortBy, StayDates

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def dates():
    check_in = date.today() + timedelta(days=45)
    return StayDates(check_in=check_in, check_out=check_in + timedelta(days=3))


@pytest.fixture
async def api():
    # Function-scoped on purpose: pytest-asyncio gives each test its own
    # event loop, and the curl session must be created inside it.
    async with AsyncGoogleHotels() as client:
        yield client


async def test_search_returns_priced_hotels(api, dates):
    filters = SearchFilters(
        location=Location(query="tokyo hotels"),
        dates=dates,
        guests=Guests(adults=2),
        currency=Currency.USD,
        sort_by=SortBy.LOWEST_PRICE,
    )
    hotels = await api.search(filters)
    assert len(hotels) >= 5
    priced = [h for h in hotels if h.price]
    assert len(priced) >= 3
    assert all(h.price.currency == "USD" for h in priced)
    prices = [h.price.amount for h in priced]
    assert prices == sorted(prices)


async def test_details_roundtrip(api, dates):
    hotels = await api.search(SearchFilters(location=Location(query="london hotels"), dates=dates))
    target = next(h for h in hotels if h.entity_key)
    detail = await api.details(target.entity_key, dates=dates, currency=Currency.USD)
    assert detail.name
    assert detail.rooms, "expected at least one room with rates"
    rates = detail.rooms[0].rates
    assert all(r.currency == "USD" for r in rates)
    assert all(r.price > 0 for r in rates)


async def test_search_with_details_partial_contract(api, dates):
    filters = SearchFilters(location=Location(query="paris hotels"), dates=dates)
    enriched = await api.search_with_details(filters, max_hotels=2)
    assert len(enriched) == 2
    assert all(item.ok or item.error for item in enriched)
