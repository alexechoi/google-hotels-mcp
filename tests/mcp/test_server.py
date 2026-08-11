"""MCP server tests via an in-process FastMCP client (no network)."""

import json
from pathlib import Path

import pytest
from fastmcp import Client

from ghotels.api import AsyncGoogleHotels
from ghotels.mcp import runtime
from ghotels.mcp.server import mcp

FIXTURES = Path(__file__).parent.parent / "fixtures"

DATE_ARGS = {"check_in": "2026-09-10", "check_out": "2026-09-13"}


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
def scripted_api():
    runtime.set_api(AsyncGoogleHotels(ScriptedTransport()))
    yield
    runtime.set_api(None)


def tool_payload(result):
    return json.loads(result.content[0].text)


class TestSurface:
    async def test_three_tools_two_prompts_one_resource(self):
        async with Client(mcp) as client:
            tools = {t.name for t in await client.list_tools()}
            prompts = {p.name for p in await client.list_prompts()}
            resources = [str(r.uri) for r in await client.list_resources()]
        assert tools == {"search_hotels", "get_hotel_details", "search_hotels_with_details"}
        assert prompts == {"choosing-a-tool", "compare-hotels-in-city"}
        assert resources == ["resource://google-hotels-mcp/configuration"]

    async def test_configuration_resource_payload(self):
        async with Client(mcp) as client:
            content = await client.read_resource("resource://google-hotels-mcp/configuration")
        payload = json.loads(content[0].text)
        assert payload["environment"]["prefix"] == "GHOTELS_MCP_"
        assert "GHOTELS_RPS" in payload["environment"]["variables"]
        assert payload["hard_max_hotels"] == 15


class TestSearchHotels:
    async def test_success_envelope(self):
        async with Client(mcp) as client:
            result = await client.call_tool("search_hotels", {"query": "new york hotels"})
        envelope = tool_payload(result)
        assert envelope["ok"] is True
        assert envelope["kind"] == "search"
        assert envelope["count"] == 20
        assert envelope["results"][0]["entity_key"]

    async def test_case_insensitive_enums(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_hotels",
                {
                    "query": "new york hotels",
                    "amenities": ["pool", "Wifi"],
                    "brands": ["hilton"],
                    "sort_by": "lowest_price",
                    "currency": "usd",
                },
            )
        envelope = tool_payload(result)
        assert envelope["ok"] is True
        assert envelope["query"]["amenities"] == ["POOL", "WIFI"]

    async def test_unknown_amenity_is_helpful_error(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_hotels", {"query": "x", "amenities": ["JACUZZI"]}
            )
        envelope = tool_payload(result)
        assert envelope["ok"] is False
        assert "JACUZZI" in envelope["error"]["message"]
        assert "POOL" in envelope["error"]["message"]

    async def test_children_ages_mismatch_is_error(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_hotels", {"query": "x", "children": 2, "child_ages": [7]}
            )
        envelope = tool_payload(result)
        assert envelope["ok"] is False
        assert "one age" in envelope["error"]["message"]

    async def test_max_results_caps(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_hotels", {"query": "new york hotels", "max_results": 4}
            )
        assert tool_payload(result)["count"] == 4


class TestGetHotelDetails:
    async def test_success_with_occupancy(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_hotel_details",
                {"entity_key": "ChkX", **DATE_ARGS, "adults": 3, "children": 1, "child_ages": [7]},
            )
        envelope = tool_payload(result)
        assert envelope["ok"] is True
        assert envelope["query"]["guests"]["adults"] == 3
        (record,) = envelope["results"]
        assert record["rooms"][0]["rates"][0]["currency"] == "USD"

    async def test_bad_date_is_error_envelope(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_hotel_details",
                {"entity_key": "ChkX", "check_in": "soon", "check_out": "2026-09-13"},
            )
        envelope = tool_payload(result)
        assert envelope["ok"] is False
        assert "YYYY-MM-DD" in envelope["error"]["message"]


class TestSearchWithDetails:
    async def test_enrich_envelope(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_hotels_with_details",
                {"query": "new york hotels", **DATE_ARGS, "max_hotels": 2},
            )
        envelope = tool_payload(result)
        assert envelope["ok"] is True
        assert envelope["kind"] == "enrich"
        assert envelope["count"] == 2
        assert all(item["ok"] and item["detail"] for item in envelope["results"])


class TestPrompts:
    async def test_choosing_a_tool(self):
        async with Client(mcp) as client:
            result = await client.get_prompt("choosing-a-tool", {"user_intent": "compare rates"})
        text = result.messages[0].content.text
        assert "search_hotels_with_details" in text
        assert "compare rates" in text

    async def test_compare_hotels_caps_max(self):
        async with Client(mcp) as client:
            result = await client.get_prompt(
                "compare-hotels-in-city",
                {
                    "city": "Paris",
                    "check_in": "2026-09-10",
                    "check_out": "2026-09-13",
                    "max_hotels": 99,
                },
            )
        assert "max_hotels=15" in result.messages[0].content.text
