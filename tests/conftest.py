"""Shared pytest configuration.

Live tests (marked ``live``) hit the real Google Hotels endpoint and are
deselected by default so the offline suite stays deterministic. Opt in with
``pytest --live`` or an explicit ``-m live`` expression.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run tests that hit the real Google Hotels endpoint",
    )


def pytest_configure(config: pytest.Config) -> None:
    # Golden CLI fixtures compare rendered stdout byte-for-byte; force a
    # colorless, deterministic environment regardless of the host terminal/CI.
    os.environ.pop("FORCE_COLOR", None)
    os.environ["NO_COLOR"] = "1"
    os.environ["TERM"] = "dumb"
    _ = config


def pytest_collection_modifyitems(config: pytest.Config, items: Sequence[pytest.Item]) -> None:
    if config.getoption("--live") or "live" in config.getoption("-m", default=""):
        return
    skip_live = pytest.mark.skip(reason="live test: pass --live to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
