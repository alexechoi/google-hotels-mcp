"""Google Hotels ``batchexecute`` wire protocol.

Reverse-engineered request/response formats live here and only here. See
``docs/PROTOCOL.md`` for the annotated slot map and provenance.
"""

from ghotels.protocol.request import (
    ENDPOINT,
    RPC_ID,
    build_detail_payload,
    build_search_payload,
    encode_form_body,
)
from ghotels.protocol.response import decode_envelope

__all__ = [
    "ENDPOINT",
    "RPC_ID",
    "build_detail_payload",
    "build_search_payload",
    "decode_envelope",
    "encode_form_body",
]
