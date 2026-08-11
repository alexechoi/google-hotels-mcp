"""The public search API: async-first, with a thread-backed sync facade."""

from __future__ import annotations

import asyncio
import atexit
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from typing_extensions import Self

from ghotels.errors import GHotelsError
from ghotels.models.enums import Currency, SortBy
from ghotels.parsing import parse_detail_response, parse_search_response
from ghotels.protocol import RPC_ID, build_detail_payload, build_search_payload
from ghotels.transport import Transport

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from ghotels.models.detail import HotelDetail
    from ghotels.models.filters import Guests, Location, SearchFilters, StayDates
    from ghotels.models.hotel import Hotel

T = TypeVar("T")

_DEFAULT_MAX_HOTELS = 5
_DEFAULT_DETAIL_CONCURRENCY = 4


@dataclass(frozen=True)
class EnrichedHotel:
    """One hotel from :meth:`AsyncGoogleHotels.search_with_details`.

    ``hotel`` is always the list-view record. Exactly one of ``detail`` or
    ``error`` is set; ``retryable`` mirrors the underlying error class so
    callers can re-issue transient failures.
    """

    hotel: Hotel
    detail: HotelDetail | None = None
    error: str | None = None
    retryable: bool = False

    @property
    def ok(self) -> bool:
        """Whether the detail lookup for this hotel succeeded."""
        return self.detail is not None


def _stable_sort(hotels: list[Hotel], sort_by: SortBy) -> list[Hotel]:
    """Re-sort parsed results so an explicit ``sort_by`` is monotonic.

    Google's response order is *mostly* sorted with small same-price
    reorderings. A stable local sort guarantees the requested key; hotels
    missing the key always sink to the end. RELEVANCE keeps Google's order.
    """
    if sort_by is SortBy.LOWEST_PRICE:
        return sorted(hotels, key=lambda h: (h.price is None, h.price.amount if h.price else 0))
    if sort_by is SortBy.HIGHEST_RATING:
        return sorted(
            hotels,
            key=lambda h: (
                h.rating is None or h.rating.score is None,
                -(h.rating.score if h.rating and h.rating.score else 0.0),
            ),
        )
    if sort_by is SortBy.MOST_REVIEWED:
        return sorted(
            hotels,
            key=lambda h: (
                h.rating is None or h.rating.review_count is None,
                -(h.rating.review_count if h.rating and h.rating.review_count else 0),
            ),
        )
    return hotels


class AsyncGoogleHotels:
    """Async Google Hotels client.

    Usage::

        async with AsyncGoogleHotels() as api:
            hotels = await api.search(SearchFilters(location=Location(query="tokyo hotels")))
    """

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        detail_concurrency: int = _DEFAULT_DETAIL_CONCURRENCY,
    ) -> None:
        self._transport = transport or Transport()
        self._detail_concurrency = max(1, detail_concurrency)

    async def aclose(self) -> None:
        """Release the underlying HTTP session."""
        await self._transport.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def search(self, filters: SearchFilters) -> list[Hotel]:
        """Run a list-view search: one RPC, up to ~20 hotels."""
        inner = await self._transport.post_rpc(RPC_ID, build_search_payload(filters))
        return _stable_sort(parse_search_response(inner), filters.sort_by)

    async def details(
        self,
        entity_key: str,
        *,
        dates: StayDates,
        guests: Guests | None = None,
        currency: Currency = Currency.USD,
        location: Location | None = None,
    ) -> HotelDetail:
        """Fetch rooms, per-provider rates, and policies for one hotel.

        ``entity_key`` comes from a prior search result. ``dates`` is
        required because rate plans are computed for a concrete window;
        ``guests`` affects pricing and availability.
        """
        payload = build_detail_payload(
            entity_key, dates=dates, guests=guests, currency=currency, location=location
        )
        inner = await self._transport.post_rpc(RPC_ID, payload)
        return parse_detail_response(
            inner, requested_currency=currency.value, reference=dates.check_in
        )

    async def search_with_details(
        self, filters: SearchFilters, *, max_hotels: int = _DEFAULT_MAX_HOTELS
    ) -> list[EnrichedHotel]:
        """Search, then fetch details for the top ``max_hotels`` concurrently.

        Failures are captured per hotel — one bad lookup never aborts the
        batch. Programmer errors (anything that is not a
        :class:`~ghotels.errors.GHotelsError`) still propagate.
        """
        if filters.dates is None:
            msg = "search_with_details requires filters.dates — rate plans are date-keyed"
            raise ValueError(msg)
        hotels = await self.search(filters)
        top = hotels[:max_hotels]
        semaphore = asyncio.Semaphore(self._detail_concurrency)

        async def enrich(hotel: Hotel) -> EnrichedHotel:
            if not hotel.entity_key:
                return EnrichedHotel(hotel=hotel, error="missing entity_key", retryable=False)
            assert filters.dates is not None  # noqa: S101 - narrowed above, for mypy
            async with semaphore:
                try:
                    detail = await self.details(
                        hotel.entity_key,
                        dates=filters.dates,
                        guests=filters.guests,
                        currency=filters.currency,
                        location=filters.location,
                    )
                except GHotelsError as exc:
                    return EnrichedHotel(
                        hotel=hotel,
                        error=f"{type(exc).__name__}: {exc}",
                        retryable=exc.retryable,
                    )
                return EnrichedHotel(hotel=hotel, detail=detail)

        return list(await asyncio.gather(*(enrich(hotel) for hotel in top)))


class GoogleHotels:
    """Synchronous facade over :class:`AsyncGoogleHotels`.

    Runs a private event loop on a daemon thread so the HTTP session (and
    its TLS handshake) is reused across calls, and so calls work no matter
    what the calling thread's asyncio state is.
    """

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        detail_concurrency: int = _DEFAULT_DETAIL_CONCURRENCY,
    ) -> None:
        self._api = AsyncGoogleHotels(transport, detail_concurrency=detail_concurrency)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="ghotels-io", daemon=True
        )
        self._thread.start()
        atexit.register(self.close)

    def _run(self, coroutine: Coroutine[None, None, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()

    def close(self) -> None:
        """Release the HTTP session and stop the background loop."""
        if self._loop.is_closed():
            return
        self._run(self._api.aclose())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def search(self, filters: SearchFilters) -> list[Hotel]:
        """Synchronous :meth:`AsyncGoogleHotels.search`."""
        return self._run(self._api.search(filters))

    def details(
        self,
        entity_key: str,
        *,
        dates: StayDates,
        guests: Guests | None = None,
        currency: Currency = Currency.USD,
        location: Location | None = None,
    ) -> HotelDetail:
        """Synchronous :meth:`AsyncGoogleHotels.details`."""
        return self._run(
            self._api.details(
                entity_key, dates=dates, guests=guests, currency=currency, location=location
            )
        )

    def search_with_details(
        self, filters: SearchFilters, *, max_hotels: int = _DEFAULT_MAX_HOTELS
    ) -> list[EnrichedHotel]:
        """Synchronous :meth:`AsyncGoogleHotels.search_with_details`."""
        return self._run(self._api.search_with_details(filters, max_hotels=max_hotels))
