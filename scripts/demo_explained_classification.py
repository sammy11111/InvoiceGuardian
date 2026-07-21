#!/usr/bin/env python3
"""DEMO-ONLY: prints the model's live, unscripted reasoning for a made-up
invoice line description, to show on camera that classification isn't a
templated/hardcoded response.

Not part of the real pipeline, the evaluator, or SCORING.md's fixed
11-operation manifest. Never called by src/invoiceguardian/analyze,
checks/semantic.py, or extraction/semantic.py — those are untouched. This
script only *reuses* their already-frozen, already-tested extraction calls
to load real MSA/SOW context, then makes one additional, demo-only model
call with its own local schema and prompt (not one of the versioned files
under extraction/prompts/, since this call is never scored or replayed by
the evaluation harness).

The demo-only model call has its own local HTTP function (_call_demo_tool)
rather than reusing extraction.anthropic_client.call_tool_validated: that
shared helper aggregates token counts across a schema-validation retry and
doesn't expose the message id, but this script needs each attempt's id and
usage kept distinct so a failed attempt is never printed paired with the
successful reasoning. The shared client itself is untouched — only its
constants (URL, version, API key loader, repair-message text) are reused.

Usage:
    uv run python scripts/demo_explained_classification.py "<line description>"
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from invoiceguardian.checks.role_matching import ROLE_LABELS
from invoiceguardian.dataset_generator.content import MSA_DOCUMENT_ID, SOW_DOCUMENT_ID
from invoiceguardian.dataset_generator.generate import DEFAULT_OUTPUT_DIR, generate_dataset
from invoiceguardian.extraction.anthropic_client import _REPAIR_MESSAGE as _SHARED_REPAIR_MESSAGE
from invoiceguardian.extraction.anthropic_client import (
    ANTHROPIC_API_URL,
    ANTHROPIC_VERSION,
    DEFAULT_MODEL,
    get_api_key,
)
from invoiceguardian.extraction.extractor import extract_contract, extract_sow
from invoiceguardian.extraction.json_schema_utils import resolve_refs
from invoiceguardian.schemas.runtime import ContractTerms, StatementOfWork

_DEMO_SYSTEM_PROMPT = (
    "You are helping demonstrate, on camera, how a service-invoice review system "
    "reasons about whether a described service falls within an authorized scope. "
    "You are given a single service description and the authorized-scope material "
    "from the governing contract and statement of work. Judge only against the "
    "supplied material — do not rely on outside assumptions about what such a "
    "service usually involves.\n\n"
    "First explain, in 2-3 sentences of plain, genuine reasoning, whether the "
    "description plausibly falls within the authorized scope, is clearly outside "
    "it, or is genuinely ambiguous given what the supplied material does and does "
    "not say. Then choose exactly one classification:\n\n"
    "- EQUIVALENT: clearly maps to a specific authorized role or service.\n"
    "- NOT_AUTHORIZED: no reasonable reading of the supplied material authorizes it.\n"
    "- AMBIGUOUS: plausibly related, but the supplied material cannot settle it."
)

_DEMO_TOOL_NAME = "explain_and_classify_service_description"
_DEMO_TOOL_DESCRIPTION = (
    "Record genuine reasoning and a three-way authorization classification for one "
    "novel, unscripted service description against the supplied authorized-scope "
    "material. Demo-only — never used for scoring."
)


class DemoReasonedClassification(BaseModel):
    reasoning: str = Field(
        description="2-3 sentences of genuine, unscripted reasoning about whether the "
        "description falls within, outside, or ambiguously relates to the authorized "
        "scope material — written before the classification, not after."
    )
    classification: Literal["EQUIVALENT", "NOT_AUTHORIZED", "AMBIGUOUS"]


_DEMO_SCHEMA = resolve_refs(DemoReasonedClassification.model_json_schema())


class DemoSchemaValidationFailure(Exception):
    """Both the initial demo call and its one retry failed schema validation."""


@dataclass(frozen=True)
class DemoToolCallResponse:
    """Everything from a single API response, kept together so a caller can
    never accidentally pair one attempt's message id with another attempt's
    token usage or tool input."""

    message_id: str
    tool_use_id: str
    tool_input: dict[str, Any]
    raw_content: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int


def _call_demo_tool(
    *,
    client: httpx.Client,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 4096,
    timeout: float = 90.0,
) -> DemoToolCallResponse:
    response = client.post(
        ANTHROPIC_API_URL,
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "tools": [
                {
                    "name": _DEMO_TOOL_NAME,
                    "description": _DEMO_TOOL_DESCRIPTION,
                    "input_schema": _DEMO_SCHEMA,
                }
            ],
            "tool_choice": {"type": "tool", "name": _DEMO_TOOL_NAME},
        },
        headers={
            "x-api-key": get_api_key(),
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    tool_use = next(block for block in data["content"] if block["type"] == "tool_use")
    usage = data.get("usage", {})
    return DemoToolCallResponse(
        message_id=data["id"],
        tool_use_id=tool_use["id"],
        tool_input=tool_use["input"],
        raw_content=data["content"],
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )


def _scope_material(contract: ContractTerms, sow: StatementOfWork) -> str:
    roles = "\n".join(f"- {ROLE_LABELS[entry.role]}" for entry in sow.monthly_hour_limits)
    return (
        "[Statement of Work — Scope of services]\n"
        f"{sow.scope.text}\n\n"
        "[Statement of Work — Authorized roles]\n"
        f"{roles}\n\n"
        "[Master Services Agreement — Authorization principle]\n"
        f"{contract.authorization_principle.text}"
    )


def explain_and_classify(
    description: str,
    contract: ContractTerms,
    sow: StatementOfWork,
    model: str = DEFAULT_MODEL,
    *,
    transport: httpx.BaseTransport | None = None,
) -> tuple[DemoReasonedClassification, DemoToolCallResponse]:
    """Returns (validated classification, the metadata of whichever attempt
    actually succeeded) — never a mix of one attempt's id/tokens with
    another attempt's content."""
    user_content = f'Service description:\n"{description}"\n\n{_scope_material(contract, sow)}'
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]
    client = httpx.Client(transport=transport) if transport is not None else httpx.Client()
    try:
        first = _call_demo_tool(
            client=client, model=model, system=_DEMO_SYSTEM_PROMPT, messages=messages
        )
        try:
            return DemoReasonedClassification.model_validate(first.tool_input), first
        except ValidationError as first_error:
            print(
                f"[API attempt 1: {first.message_id} | input_tokens: {first.input_tokens} | "
                f"output_tokens: {first.output_tokens} | schema_invalid]"
            )
            messages = [
                *messages,
                {"role": "assistant", "content": first.raw_content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": first.tool_use_id,
                            "is_error": True,
                            "content": _SHARED_REPAIR_MESSAGE.format(error=str(first_error)),
                        }
                    ],
                },
            ]
            retry = _call_demo_tool(
                client=client, model=model, system=_DEMO_SYSTEM_PROMPT, messages=messages
            )
            try:
                return DemoReasonedClassification.model_validate(retry.tool_input), retry
            except ValidationError as retry_error:
                raise DemoSchemaValidationFailure(
                    f"{_DEMO_TOOL_NAME} failed schema validation on the initial call and "
                    f"the one allowed retry. Retry error: {retry_error}"
                ) from retry_error
    finally:
        client.close()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print('Usage: python scripts/demo_explained_classification.py "<line description>"')
        return 1
    description = argv[0]

    start = time.perf_counter()

    pdf_dir = DEFAULT_OUTPUT_DIR
    required = {f"{MSA_DOCUMENT_ID}.pdf", f"{SOW_DOCUMENT_ID}.pdf"}
    if not pdf_dir.exists() or not required.issubset({p.name for p in pdf_dir.glob("*.pdf")}):
        print("Generating dataset PDFs...")
        generate_dataset(output_dir=pdf_dir)

    print("Extracting MSA...")
    contract, _ = extract_contract(pdf_dir / f"{MSA_DOCUMENT_ID}.pdf", MSA_DOCUMENT_ID)
    print("Extracting SOW...")
    sow, _ = extract_sow(pdf_dir / f"{SOW_DOCUMENT_ID}.pdf", SOW_DOCUMENT_ID)

    print(f'\nNovel line description: "{description}"')
    print("Asking the model to reason about authorization...\n")
    result, call_meta = explain_and_classify(description, contract, sow)

    print(result.reasoning)
    print(f"\nClassification: {result.classification}")
    print(
        f"[API response: {call_meta.message_id} | input_tokens: {call_meta.input_tokens} | "
        f"output_tokens: {call_meta.output_tokens}]"
    )

    elapsed = time.perf_counter() - start
    print(f"\n[wall-clock: {elapsed:.1f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
