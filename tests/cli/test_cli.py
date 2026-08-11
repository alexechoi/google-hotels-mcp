"""CLI behavior over scripted transports (no network)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ghotels.api import GoogleHotels
from ghotels.cli import runtime
from ghotels.cli.app import app, reroute_bare_query

FIXTURES = Path(__file__).parent.parent / "fixtures"

runner = CliRunner()

DATE_FLAGS = ["--check-in", "2026-09-10", "--check-out", "2026-09-13"]


class ScriptedTransport:
    def __init__(self):
        self.search_inner = json.loads((FIXTURES / "search_response.json").read_text())
        self.detail_inner = json.loads((FIXTURES / "detail_response.json").read_text())

    async def post_rpc(self, rpc_id, payload):
        if payload[2][5] is None:
            return self.search_inner
        return self.detail_inner

    async def aclose(self):
        pass


@pytest.fixture(autouse=True)
def scripted_client(monkeypatch):
    monkeypatch.setattr(runtime, "make_client", lambda: GoogleHotels(ScriptedTransport()))


class TestRouting:
    def test_bare_query_becomes_search(self):
        argv = ["ghotels", "tokyo hotels", "--max-results", "3"]
        assert reroute_bare_query(argv) == [
            "ghotels",
            "search",
            "tokyo hotels",
            "--max-results",
            "3",
        ]

    def test_known_commands_untouched(self):
        argv = ["ghotels", "details", "ChkX"]
        assert reroute_bare_query(argv) == argv

    def test_flags_untouched(self):
        argv = ["ghotels", "--help"]
        assert reroute_bare_query(argv) == argv


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("ghotels ")


class TestSearch:
    def test_text_table(self):
        result = runner.invoke(app, ["search", "new york hotels"])
        assert result.exit_code == 0
        assert "Mandarin" in result.output  # rich may wrap the full name
        assert "USD" in result.output
        assert "20 hotels" in result.output

    def test_json_envelope(self):
        result = runner.invoke(app, ["search", "new york hotels", "--format", "json"])
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["ok"] is True
        assert envelope["kind"] == "search"
        assert envelope["count"] == 20
        assert envelope["query"]["location"]["query"] == "new york hotels"
        assert envelope["results"][0]["name"]

    def test_jsonl_streams_records(self):
        result = runner.invoke(
            app, ["search", "new york hotels", "--format", "jsonl", "--max-results", "5"]
        )
        assert result.exit_code == 0
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert len(lines) == 5
        assert all(json.loads(line)["name"] for line in lines)

    def test_max_results_caps_output(self):
        result = runner.invoke(
            app, ["search", "new york hotels", "--format", "json", "--max-results", "3"]
        )
        assert json.loads(result.output)["count"] == 3

    def test_sort_by_lowest_price(self):
        result = runner.invoke(
            app,
            ["search", "new york hotels", "--sort-by", "lowest_price", "--format", "json"],
        )
        prices = [r["price"]["amount"] for r in json.loads(result.output)["results"] if r["price"]]
        assert prices == sorted(prices)

    def test_bad_date_is_usage_error(self):
        result = runner.invoke(
            app, ["search", "x", "--check-in", "tomorrow", "--check-out", "2026-09-13"]
        )
        assert result.exit_code == 2
        assert "YYYY-MM-DD" in result.output

    def test_single_date_is_usage_error(self):
        result = runner.invoke(app, ["search", "x", "--check-in", "2026-09-10"])
        assert result.exit_code == 2
        assert "must be given together" in result.output


class TestDetails:
    def test_requires_dates(self):
        result = runner.invoke(app, ["details", "ChkX-entity"])
        assert result.exit_code == 2
        assert "required" in result.output

    def test_text_output(self):
        result = runner.invoke(app, ["details", "ChkX-entity", *DATE_FLAGS])
        assert result.exit_code == 0
        assert "Mandarin Oriental" in result.output
        assert "Booking.com" in result.output

    def test_json_envelope_echoes_query(self):
        result = runner.invoke(app, ["details", "ChkX-entity", *DATE_FLAGS, "-f", "json"])
        envelope = json.loads(result.output)
        assert envelope["kind"] == "detail"
        assert envelope["query"]["entity_key"] == "ChkX-entity"
        assert envelope["query"]["guests"]["adults"] == 2
        (record,) = envelope["results"]
        assert record["rooms"][0]["rates"][0]["currency"] == "USD"

    def test_occupancy_flags_accepted(self):
        result = runner.invoke(
            app,
            ["details", "ChkX", *DATE_FLAGS, "--adults", "3", "--child-age", "7", "-f", "json"],
        )
        envelope = json.loads(result.output)
        assert envelope["query"]["guests"]["adults"] == 3
        assert envelope["query"]["guests"]["child_ages"] == [7]


class TestEnrich:
    def test_requires_dates(self):
        result = runner.invoke(app, ["enrich", "new york hotels"])
        assert result.exit_code == 2

    def test_json_envelope(self):
        result = runner.invoke(
            app, ["enrich", "new york hotels", *DATE_FLAGS, "--max-hotels", "2", "-f", "json"]
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["kind"] == "enrich"
        assert envelope["count"] == 2
        assert all(item["ok"] for item in envelope["results"])
        assert all(item["detail"] for item in envelope["results"])
