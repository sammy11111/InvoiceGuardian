"""Tests for the demo-only explained-classification script's local HTTP
call, using a transport-level httpx.MockTransport (same sanctioned pattern
as test_anthropic_client_retry.py).

scripts/demo_explained_classification.py is never imported by the real
pipeline or evaluator; this test file exists purely to give its demo-local
HTTP function test-first-repair coverage before it's relied on on camera.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from invoiceguardian.schemas.runtime import (
    ContractTerms,
    MonthlyCap,
    RateCardEntry,
    ScopeClause,
    ServiceRole,
    SourceRef,
    StatementOfWork,
)
from scripts.demo_explained_classification import (
    DemoReasonedClassification,
    _call_demo_tool,
    explain_and_classify,
)


@pytest.fixture(autouse=True)
def _dummy_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used-by-mock-transport")


def _response_payload(
    *, message_id: str, tool_input: dict[str, Any], input_tokens: int, output_tokens: int
) -> dict[str, Any]:
    return {
        "id": message_id,
        "content": [
            {
                "type": "tool_use",
                "id": f"toolu_{message_id}",
                "name": "explain_and_classify_service_description",
                "input": tool_input,
            }
        ],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def test_call_demo_tool_fields_all_come_from_the_same_mocked_response() -> None:
    """Guards against message id / token counts / tool input being stitched
    together from different calls: everything returned must trace back to
    one single mocked HTTP response."""
    tool_input = {
        "reasoning": "This is plausibly related to the SOW's training scope but not named.",
        "classification": "AMBIGUOUS",
    }
    payload = _response_payload(
        message_id="msg_only_one_response",
        tool_input=tool_input,
        input_tokens=123,
        output_tokens=45,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = _call_demo_tool(
            client=client,
            model="claude-sonnet-5",
            system="system prompt",
            messages=[{"role": "user", "content": "novel description"}],
        )
    finally:
        client.close()

    assert result.message_id == "msg_only_one_response"
    assert result.tool_input == tool_input
    assert result.input_tokens == 123
    assert result.output_tokens == 45


def _make_two_call_transport(
    payloads: list[dict[str, Any]],
) -> tuple[httpx.MockTransport, dict[str, int]]:
    counter = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = counter["calls"]
        counter["calls"] += 1
        return httpx.Response(200, json=payloads[index])

    return httpx.MockTransport(handler), counter


def test_explain_and_classify_uses_only_the_successful_attempts_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """First attempt fails schema validation (missing 'classification'); the
    retry succeeds. The returned metadata — and the printed [API response]
    line — must come from the retry alone, never mixed with attempt 1's id
    or token counts."""
    failed_input = {"reasoning": "Some reasoning without a classification field."}
    valid_input = {
        "reasoning": "Clear reasoning that matches the schema.",
        "classification": "EQUIVALENT",
    }
    transport, counter = _make_two_call_transport(
        [
            _response_payload(
                message_id="msg_failed_attempt",
                tool_input=failed_input,
                input_tokens=10,
                output_tokens=5,
            ),
            _response_payload(
                message_id="msg_succeeded_attempt",
                tool_input=valid_input,
                input_tokens=30,
                output_tokens=12,
            ),
        ]
    )

    src = SourceRef(document_id="MSA-2026-014", section="4.1", page=2)
    contract = ContractTerms(
        document_id="MSA-2026-014",
        client_party="Maplecore Logistics Inc.",
        vendor_party="Northbridge Consulting Ltd.",
        effective_from=date(2026, 3, 1),
        effective_to=date(2027, 2, 28),
        currency="CAD",
        rate_card=[
            RateCardEntry(
                role=ServiceRole.SENIOR_CONSULTANT,
                rate_cad_per_hour=Decimal("150.00"),
                quote="Senior Consultant services shall be billed at CAD $150.00 per hour.",
                source=src,
            )
        ],
        monthly_cap=MonthlyCap(
            value_cad=Decimal("25000.00"), quote="Monthly cap is CAD $25,000.00.", source=src
        ),
        authorization_principle=ScopeClause(
            text="Only services described in an executed SOW are authorized.", source=src
        ),
    )
    sow = StatementOfWork(
        document_id="SOW-2026-03",
        period_from=date(2026, 4, 1),
        period_to=date(2026, 9, 30),
        monthly_hour_limits=[],
        scope=ScopeClause(text="ERP rollout implementation support.", source=src),
    )

    result, call_meta = explain_and_classify(
        "A genuinely novel service description", contract, sow, transport=transport
    )

    assert counter["calls"] == 2
    assert isinstance(result, DemoReasonedClassification)
    assert result.classification == "EQUIVALENT"

    # Metadata must be the retry's alone, never the failed attempt's.
    assert call_meta.message_id == "msg_succeeded_attempt"
    assert call_meta.input_tokens == 30
    assert call_meta.output_tokens == 12

    printed = capsys.readouterr().out
    assert (
        "[API attempt 1: msg_failed_attempt | input_tokens: 10 | output_tokens: 5 | schema_invalid]"
        in printed
    )
    assert "msg_succeeded_attempt" not in printed.split("[API attempt 1:")[0]
