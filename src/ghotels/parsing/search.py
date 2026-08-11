"""Search-mode response parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ghotels.parsing.entry import find_hotel_entries, parse_hotel_entry

if TYPE_CHECKING:
    from ghotels.models.hotel import Hotel


def parse_search_response(inner: Any) -> list[Hotel]:  # noqa: ANN401 - decoded JSON
    """Turn a decoded search payload into an ordered list of hotels.

    Duplicates are dropped on the first stable identifier available
    (kgmid, then fid, then google id). Hotels with no identifier at all
    are kept — silently losing a result is worse than a rare duplicate.
    """
    hotels: list[Hotel] = []
    seen: set[str] = set()
    for entry in find_hotel_entries(inner):
        hotel = parse_hotel_entry(entry)
        if hotel is None:
            continue
        key = hotel.kgmid or hotel.fid or hotel.google_hotel_id
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        hotels.append(hotel)
    return hotels
