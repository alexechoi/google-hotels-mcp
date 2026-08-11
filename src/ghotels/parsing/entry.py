"""The shared hotel-entry walker.

Both response modes carry hotels as large position-encoded lists ("entries",
~48 slots). Search responses contain many; detail responses contain one
enriched entry. This module locates entries anywhere in the payload tree and
converts them into :class:`~ghotels.models.hotel.Hotel` snapshots.

Slot map (relative to an entry; see also ``docs/PROTOCOL.md``):

======  =====================================================================
Slot    Content
======  =====================================================================
[1]     hotel name (str)
[2][0]  ``[lat, lng]`` float pair — the structural anchor for detection
[2]     also hosts category ratings, check-in/out times, nearby places
[3]     ``["N-star hotel", N]``
[5]     image URL(s)
[6]     pricing block: ``[6][1][0]`` = ``[price, 0]`` cheapest pair,
        ``[6][1][3]`` = currency, ``[6][1][4]`` = rate-date window,
        ``[6][2][1][4]`` = list-view display price
[7]     review summary: ``[[overall, count], [histogram triples], ...]``
[9]     Maps feature id (fid)
[10]    amenities as ``[available: bool, wire_id: int]`` pairs
[12]    more image URLs
[20]    entity key (base64 protobuf; embeds the KGMID)
[25]    numeric google hotel id
======  =====================================================================
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import date
from typing import Any, Final

from ghotels.models.hotel import (
    CategoryScore,
    Hotel,
    NearbyPlace,
    PriceSnapshot,
    RatingSummary,
)
from ghotels.parsing._pluck import pluck
from ghotels.protocol.ids import AMENITY_BY_ID

_MIN_ENTRY_LEN: Final = 20
_COORD_PAIR_LEN: Final = 2
_MAX_IMAGES: Final = 10
_MAX_NEARBY: Final = 20
_MAX_STAR: Final = 5

#: Category-rating labels by Google's category id.
_CATEGORY_LABELS: Final = {1: "location", 2: "rooms", 3: "service", 4: "cleanliness", 5: "value"}
_TRAVEL_MODES: Final = {0: "walk", 1: "drive", 2: "transit", 3: "bike"}

_LEADING_INT_RE: Final = re.compile(r"(\d+)")


def extract_kgmid(entity_key: str) -> str | None:
    """Pull the ``/g/...`` or ``/m/...`` KGMID out of a base64 entity key."""
    padded = entity_key + "=" * (-len(entity_key) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError):
        return None
    for marker in (b"/g/", b"/m/"):
        start = raw.find(marker)
        if start < 0:
            continue
        end = start
        while end < len(raw) and 32 <= raw[end] < 127:  # noqa: PLR2004 - printable ASCII range
            end += 1
        return raw[start:end].decode("ascii")
    return None


def _is_hotel_entry(node: object) -> bool:
    """Structural test: name at [1], coords at [2][0], an id at [9] or [20].

    Star class is deliberately NOT required — budget and boutique properties
    often lack one and must still surface.
    """
    if not isinstance(node, list) or len(node) < _MIN_ENTRY_LEN:
        return False
    name = pluck(node, 1)
    if not isinstance(name, str) or not name:
        return False
    fid = pluck(node, 9)
    entity_key = pluck(node, 20)
    has_id = (isinstance(fid, str) and fid) or (isinstance(entity_key, str) and entity_key)
    if not has_id:
        return False
    coords = pluck(node, 2, 0)
    return (
        isinstance(coords, list)
        and len(coords) == _COORD_PAIR_LEN
        and all(isinstance(c, (int, float)) for c in coords)
    )


def find_hotel_entries(tree: Any) -> list[list[Any]]:  # noqa: ANN401 - decoded JSON
    """Collect every subtree that structurally looks like a hotel entry."""
    found: list[list[Any]] = []

    def descend(node: object) -> None:
        if _is_hotel_entry(node):
            found.append(node)  # type: ignore[arg-type]  # narrowed by _is_hotel_entry
            return
        if isinstance(node, list):
            for child in node:
                descend(child)
        elif isinstance(node, dict):
            for child in node.values():
                descend(child)

    descend(tree)
    return found


def parse_hotel_entry(entry: list[Any]) -> Hotel | None:
    """Convert one raw entry into a :class:`Hotel`; ``None`` if nameless."""
    name = pluck(entry, 1)
    if not isinstance(name, str) or not name:
        return None

    entity_key = _string_at(entry, 20)
    latitude, longitude = _coordinates(entry)
    star_class, star_label = _star_info(entry)
    categories, check_in_time, check_out_time, nearby = _entry_metadata(entry)

    return Hotel(
        name=name,
        entity_key=entity_key,
        kgmid=extract_kgmid(entity_key) if entity_key else None,
        fid=_string_at(entry, 9),
        google_hotel_id=_string_at(entry, 25),
        latitude=latitude,
        longitude=longitude,
        star_class=star_class,
        star_class_label=star_label,
        price=_price_snapshot(entry),
        rating=_rating_summary(entry, categories),
        amenities=_amenity_set(entry),
        check_in_time=check_in_time,
        check_out_time=check_out_time,
        nearby=tuple(nearby[:_MAX_NEARBY]),
        image_urls=tuple(_image_urls(entry)),
    )


def _string_at(entry: list[Any], index: int) -> str | None:
    value = pluck(entry, index)
    return value if isinstance(value, str) and value else None


def _coordinates(entry: list[Any]) -> tuple[float | None, float | None]:
    pair = pluck(entry, 2, 0)
    if isinstance(pair, list) and len(pair) == _COORD_PAIR_LEN:
        lat, lng = pair
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            return float(lat), float(lng)
    return None, None


def _star_info(entry: list[Any]) -> tuple[int | None, str | None]:
    block = pluck(entry, 3)
    if not isinstance(block, list) or len(block) < 2:  # noqa: PLR2004 - [label, stars] pair
        return None, None
    label = block[0] if isinstance(block[0], str) else None
    stars = block[1] if isinstance(block[1], int) and 1 <= block[1] <= _MAX_STAR else None
    return stars, label


def _price_snapshot(entry: list[Any]) -> PriceSnapshot | None:
    """Assemble pricing from the [6] block.

    The cheapest-rate pair at [6][1][0] only exists in search mode; detail
    responses omit it (and with it, currency and the date window). The
    list-view display number at [6][2][1][4] wins over the pair when both
    are present.
    """
    amount: int | None = None
    currency: str | None = None
    check_in: date | None = None
    check_out: date | None = None

    pair = pluck(entry, 6, 1, 0)
    if isinstance(pair, list):
        currency_value = pluck(entry, 6, 1, 3)
        if isinstance(currency_value, str):
            currency = currency_value
        check_in, check_out = _rate_window(pluck(entry, 6, 1, 4))
        if pair and isinstance(pair[0], int):
            amount = pair[0]

    display = pluck(entry, 6, 2, 1, 4)
    if isinstance(display, (int, float)) and display > 0:
        amount = int(display)

    if amount is None or currency is None:
        return None
    return PriceSnapshot(amount=amount, currency=currency, check_in=check_in, check_out=check_out)


def _rate_window(block: Any) -> tuple[date | None, date | None]:  # noqa: ANN401 - decoded JSON
    if not (isinstance(block, list) and len(block) >= 2):  # noqa: PLR2004 - [in, out] pair
        return None, None
    dates: list[date] = []
    for ymd in block[:2]:
        if not (isinstance(ymd, list) and len(ymd) == 3 and all(isinstance(x, int) for x in ymd)):  # noqa: PLR2004 - [Y, M, D]
            return None, None
        try:
            dates.append(date(*ymd))
        except ValueError:
            return None, None
    return dates[0], dates[1]


def _rating_summary(entry: list[Any], categories: list[CategoryScore]) -> RatingSummary | None:
    block = pluck(entry, 7)
    score: float | None = None
    count: int | None = None
    histogram: dict[int, int] = {}

    head = pluck(block, 0)
    if isinstance(head, list) and len(head) >= 2:  # noqa: PLR2004 - [score, count] pair
        if isinstance(head[0], (int, float)):
            score = float(head[0])
        if isinstance(head[1], int):
            count = head[1]

    triples = pluck(block, 1, 0)
    if isinstance(triples, list):
        for triple in triples:
            if (
                isinstance(triple, list)
                and len(triple) >= 3  # noqa: PLR2004 - [stars, pct, count]
                and isinstance(triple[0], int)
                and isinstance(triple[2], int)
            ):
                histogram[triple[0]] = triple[2]

    if score is None and count is None and not histogram and not categories:
        return None
    return RatingSummary(
        score=score, review_count=count, histogram=histogram, categories=categories
    )


def _amenity_set(entry: list[Any]) -> frozenset[Any]:
    """Collect available amenities from the ``[available, wire_id]`` pairs at [10]."""
    amenities = set()

    def descend(node: object) -> None:
        if not isinstance(node, list):
            return
        if len(node) >= 2 and isinstance(node[0], bool) and isinstance(node[1], int):  # noqa: PLR2004 - [flag, id] pair
            if node[0] and (amenity := AMENITY_BY_ID.get(node[1])):
                amenities.add(amenity)
            return
        for child in node:
            descend(child)

    descend(pluck(entry, 10))
    return frozenset(amenities)


def _image_urls(entry: list[Any]) -> list[str]:
    urls: list[str] = []

    def descend(node: object) -> None:
        if len(urls) >= _MAX_IMAGES:
            return
        if isinstance(node, str) and node.startswith("http"):
            urls.append(node)
        elif isinstance(node, list):
            for child in node:
                descend(child)

    for slot in (12, 5):
        descend(pluck(entry, slot))
        if len(urls) >= _MAX_IMAGES:
            break
    return urls[:_MAX_IMAGES]


def _is_category_block(node: list[Any]) -> bool:
    return len(node) >= 3 and all(  # noqa: PLR2004 - at least 3 of the 5 categories
        isinstance(item, list)
        and len(item) == 2  # noqa: PLR2004 - [id, "score"] pair
        and isinstance(item[0], int)
        and 1 <= item[0] <= 5  # noqa: PLR2004 - category id range
        and isinstance(item[1], str)
        for item in node
    )


def _category_scores(node: list[Any]) -> list[CategoryScore]:
    scores: list[CategoryScore] = []
    for category_id, score_text in node:
        try:
            score = float(score_text)
        except ValueError:
            continue
        label = _CATEGORY_LABELS.get(category_id, f"category_{category_id}")
        scores.append(CategoryScore(label=label, score=score))
    return scores


def _is_time_pair(node: list[Any]) -> bool:
    return (
        len(node) == 2  # noqa: PLR2004 - [in, out] pair
        and all(isinstance(item, str) for item in node)
        and any(token in node[0] for token in ("AM", "PM"))
        and any(token in node[1] for token in ("AM", "PM"))
    )


def _nearby_place(node: list[Any]) -> NearbyPlace | None:
    """Interpret ``[name, None, [[mode_id, "N min"]]]`` as a nearby place."""
    mode_id = pluck(node, 2, 0, 0)
    duration_text = pluck(node, 2, 0, 1)
    if not (
        len(node) >= 3  # noqa: PLR2004 - [name, None, mode-block]
        and isinstance(node[0], str)
        and node[1] is None
        and isinstance(mode_id, int)
        and isinstance(duration_text, str)
    ):
        return None
    match = _LEADING_INT_RE.match(duration_text)
    return NearbyPlace(
        name=node[0],
        travel_mode=_TRAVEL_MODES.get(mode_id, f"mode_{mode_id}"),
        duration_minutes=int(match.group(1)) if match else None,
        distance_text=duration_text,
    )


def _entry_metadata(
    entry: list[Any],
) -> tuple[list[CategoryScore], str | None, str | None, list[NearbyPlace]]:
    """Walk the [2] subtree for category scores, check-in/out times, nearby places."""
    categories: list[CategoryScore] = []
    check_in_time: str | None = None
    check_out_time: str | None = None
    nearby: list[NearbyPlace] = []

    def visit(node: object) -> None:
        nonlocal check_in_time, check_out_time
        if isinstance(node, dict):
            for child in node.values():
                visit(child)
            return
        if not isinstance(node, list):
            return
        if not categories and _is_category_block(node):
            categories.extend(_category_scores(node))
            return
        if check_in_time is None and _is_time_pair(node):
            check_in_time, check_out_time = node
            return
        if (place := _nearby_place(node)) is not None:
            nearby.append(place)
            return
        for child in node:
            visit(child)

    visit(pluck(entry, 2))
    return categories, check_in_time, check_out_time, nearby
