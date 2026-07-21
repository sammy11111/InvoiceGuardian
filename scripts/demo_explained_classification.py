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

Usage:
    uv run python scripts/demo_explained_classification.py "<line description>"
"""

from __future__ import annotations

import sys
import time
from typing import Literal

from pydantic import BaseModel, Field

from invoiceguardian.checks.role_matching import ROLE_LABELS
from invoiceguardian.dataset_generator.content import MSA_DOCUMENT_ID, SOW_DOCUMENT_ID
from invoiceguardian.dataset_generator.generate import DEFAULT_OUTPUT_DIR, generate_dataset
from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL, call_tool_validated
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


class DemoReasonedClassification(BaseModel):
    reasoning: str = Field(
        description="2-3 sentences of genuine, unscripted reasoning about whether the "
        "description falls within, outside, or ambiguously relates to the authorized "
        "scope material — written before the classification, not after."
    )
    classification: Literal["EQUIVALENT", "NOT_AUTHORIZED", "AMBIGUOUS"]


_DEMO_SCHEMA = resolve_refs(DemoReasonedClassification.model_json_schema())


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
    description: str, contract: ContractTerms, sow: StatementOfWork, model: str = DEFAULT_MODEL
) -> DemoReasonedClassification:
    user_content = f'Service description:\n"{description}"\n\n{_scope_material(contract, sow)}'
    raw, _retried, _in_tok, _out_tok = call_tool_validated(
        model=model,
        system=_DEMO_SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="explain_and_classify_service_description",
        tool_description=(
            "Record genuine reasoning and a three-way authorization classification "
            "for one novel, unscripted service description against the supplied "
            "authorized-scope material. Demo-only — never used for scoring."
        ),
        input_schema=_DEMO_SCHEMA,
        raw_model=DemoReasonedClassification,
    )
    return raw


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
    result = explain_and_classify(description, contract, sow)

    print(result.reasoning)
    print(f"\nClassification: {result.classification}")

    elapsed = time.perf_counter() - start
    print(f"\n[wall-clock: {elapsed:.1f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
