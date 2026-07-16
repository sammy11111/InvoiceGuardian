"""Retry-policy tests for the Anthropic client, using a transport-level
httpx.MockTransport (the one sanctioned exception to the no-mocked-LLM rule).

Exercises SCORING.md's retry policy: one retry maximum, only after a schema
failure. No LLM abstraction is mocked — real httpx Request/Response objects
flow through the real client; only the network transport is substituted.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from invoiceguardian.extraction.anthropic_client import (
    SchemaValidationFailure,
    call_tool_validated,
)
from invoiceguardian.extraction.raw_schemas import RawSourceRef

TOOL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"section": {"type": "string"}, "page": {"type": "integer"}},
    "required": ["section", "page"],
}


def _make_transport(
    tool_inputs: list[dict[str, Any]],
) -> tuple[httpx.MockTransport, dict[str, int]]:
    counter = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = counter["calls"]
        counter["calls"] += 1
        payload = {
            "content": [
                {
                    "type": "tool_use",
                    "id": f"toolu_{index}",
                    "name": "extract_source_ref",
                    "input": tool_inputs[index],
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler), counter


@pytest.fixture(autouse=True)
def _dummy_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used-by-mock-transport")


def _call(transport: httpx.MockTransport):
    return call_tool_validated(
        model="claude-sonnet-5",
        system="extract",
        user_content="source",
        tool_name="extract_source_ref",
        tool_description="test",
        input_schema=TOOL_SCHEMA,
        raw_model=RawSourceRef,
        transport=transport,
    )


def test_schema_invalid_first_then_valid_retries_exactly_once_and_succeeds() -> None:
    transport, counter = _make_transport(
        [
            {"section": "4.1"},  # missing page -> schema-invalid
            {"section": "4.1", "page": 2},  # valid on retry
        ]
    )
    result, retried, _in_tok, _out_tok = _call(transport)

    assert counter["calls"] == 2  # initial + exactly one retry
    assert retried is True
    assert result == RawSourceRef(section="4.1", page=2)


def test_two_consecutive_schema_failures_are_not_retried_again_and_surface_a_failure() -> None:
    transport, counter = _make_transport(
        [
            {"section": "4.1"},  # invalid
            {"section": "4.2"},  # still invalid on the one retry
        ]
    )
    with pytest.raises(SchemaValidationFailure):
        _call(transport)

    assert counter["calls"] == 2  # no second retry beyond the one allowed


def test_valid_on_first_pass_does_not_retry() -> None:
    transport, counter = _make_transport([{"section": "4.1", "page": 2}])
    result, retried, _in_tok, _out_tok = _call(transport)

    assert counter["calls"] == 1
    assert retried is False
    assert result == RawSourceRef(section="4.1", page=2)
