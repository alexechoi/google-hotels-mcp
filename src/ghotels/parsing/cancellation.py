"""Cancellation policy extraction.

Google encodes per-rate cancellation two ways:

- a structured tuple ``[True, "Jul 20", "11:59 PM"]`` (free until that date)
  or ``[False, ...]`` (non-refundable), and
- free-text labels like ``"Free cancellation until Apr 25"`` or
  ``"Non-refundable"``.

Deadline strings usually omit the year. Instead of guessing from the wall
clock (the bug that broke the original project's CI), the caller passes the
stay's check-in date as ``reference`` and the year is inferred from it —
including the December-deadline / January-check-in boundary. Parsing is
fully deterministic: no ``date.today()`` anywhere.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Final

from ghotels.models.detail import Cancellation, CancellationKind

_FREE_UNTIL_RE: Final = re.compile(
    r"free cancellation until\s+([A-Za-z]+ \d{1,2}(?:,?\s*\d{4})?)", re.IGNORECASE
)
_FREE_RE: Final = re.compile(r"free cancellation", re.IGNORECASE)
_PARTIAL_RE: Final = re.compile(r"partial(?:ly)? refund", re.IGNORECASE)
_NON_REFUNDABLE_RE: Final = re.compile(r"non.?refundable|no cancel", re.IGNORECASE)

#: "Apr 24", "December 5", "Apr 24, 2026" — month names are matched against
#: the table below instead of strptime, which keeps parsing locale-proof.
_DEADLINE_RE: Final = re.compile(r"([A-Za-z]+)\s+(\d{1,2})(?:,?\s*(\d{4}))?")

_MONTHS: Final[dict[str, int]] = {
    name: number
    for number, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}

#: A free-cancellation deadline is never meaningfully later than check-in;
#: anything beyond this grace window means the deadline belongs to the
#: previous calendar year (e.g. a "Dec 28" deadline for a January stay).
_DEADLINE_GRACE: Final = timedelta(days=7)


def resolve_deadline(text: str, reference: date | None) -> date | None:
    """Parse a deadline like ``"Apr 24"`` or ``"Apr 24, 2026"`` to a date.

    Yearless strings need ``reference`` (the stay's check-in date) to pick
    the calendar year; without it they resolve to ``None`` rather than to a
    wall-clock-dependent guess.
    """
    match = _DEADLINE_RE.match(text.strip())
    if match is None:
        return None
    month = _MONTHS.get(match.group(1).casefold())
    if month is None:
        return None
    day = int(match.group(2))
    year_text = match.group(3)
    try:
        if year_text is not None:
            return date(int(year_text), month, day)
        return _anchor_to_reference(month, day, reference)
    except ValueError:
        return None


def _anchor_to_reference(month: int, day: int, reference: date | None) -> date | None:
    """Pick the calendar year for a yearless month-day deadline."""
    if reference is None:
        return None
    candidate = date(reference.year, month, day)
    if candidate > reference + _DEADLINE_GRACE:
        return candidate.replace(year=reference.year - 1)
    return candidate


def cancellation_from_slot(raw: Any, reference: date | None) -> Cancellation:  # noqa: ANN401 - decoded JSON
    """Interpret a rate's structured cancellation slot."""
    if not isinstance(raw, list) or not raw:
        return Cancellation()
    if raw[0] is not True:
        return Cancellation(kind=CancellationKind.NON_REFUNDABLE)

    deadline_text = raw[1] if len(raw) > 1 and isinstance(raw[1], str) else None
    if deadline_text is None:
        return Cancellation(kind=CancellationKind.FREE)

    description = f"Free cancellation until {deadline_text.strip()}"
    if len(raw) > 2 and isinstance(raw[2], str):  # noqa: PLR2004 - slot position
        description += f" {raw[2].strip()}"
    return Cancellation(
        kind=CancellationKind.FREE_UNTIL,
        free_until=resolve_deadline(deadline_text, reference),
        description=description,
    )


def cancellation_from_text(text: str, reference: date | None) -> Cancellation | None:
    """Interpret a human-readable cancellation label, if it is one."""
    label = text.strip()
    if not label:
        return None

    if match := _FREE_UNTIL_RE.search(label):
        return Cancellation(
            kind=CancellationKind.FREE_UNTIL,
            free_until=resolve_deadline(match.group(1), reference),
            description=label,
        )
    if _FREE_RE.search(label):
        return Cancellation(kind=CancellationKind.FREE, description=label)
    if _PARTIAL_RE.search(label):
        return Cancellation(kind=CancellationKind.PARTIAL_REFUND, description=label)
    if _NON_REFUNDABLE_RE.search(label):
        return Cancellation(kind=CancellationKind.NON_REFUNDABLE, description=label)
    return None
