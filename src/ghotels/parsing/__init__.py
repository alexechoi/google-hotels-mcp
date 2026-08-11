"""Response parsing: decoded ``batchexecute`` payloads into typed models."""

from ghotels.parsing.detail import parse_detail_response
from ghotels.parsing.search import parse_search_response

__all__ = ["parse_detail_response", "parse_search_response"]
