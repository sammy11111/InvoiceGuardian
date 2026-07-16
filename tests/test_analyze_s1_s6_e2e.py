"""End-to-end tests for build steps 3-4, via `invoiceguardian.analyze.run_analysis`:

- Step 3: parse -> extract -> S1 deterministic rate check -> one cited finding.
- Step 4: S6 clean run producing zero findings.

Both exercise the real PDFs and make real model calls (extraction is
inherently a live-model operation, not something to mock) — skipped if no
ANTHROPIC_API_KEY is available.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from invoiceguardian.analyze import run_analysis
from invoiceguardian.dataset_generator.clauses import load_contract_clauses
from invoiceguardian.dataset_generator.generate import generate_dataset
from invoiceguardian.extraction.anthropic_client import get_api_key
from invoiceguardian.schemas.runtime import (
    ActionType,
    ApprovalState,
    ExceptionType,
    FindingDisposition,
    InvoiceDisposition,
    ServiceRole,
)


def _has_api_key() -> bool:
    try:
        get_api_key()
    except RuntimeError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_api_key(), reason="ANTHROPIC_API_KEY not set; skipping live-model extraction tests"
)


@pytest.fixture(scope="module")
def pdf_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("analyze_pdfs")
    generate_dataset(output_dir=output_dir)
    return output_dir


@pytest.fixture(scope="module")
def s1_result(pdf_dir: Path):
    return run_analysis("INV-2026-061", pdf_dir=pdf_dir)


@pytest.fixture(scope="module")
def s6_result(pdf_dir: Path):
    return run_analysis("INV-2026-066", pdf_dir=pdf_dir)


def test_s1_produces_exactly_one_rate_mismatch_finding_on_l1(s1_result) -> None:
    assert s1_result.disposition == InvoiceDisposition.EXCEPTIONS_FOUND
    assert len(s1_result.findings) == 1

    finding = s1_result.findings[0]
    assert finding.finding_type == ExceptionType.RATE_MISMATCH
    assert finding.basis == "deterministic"
    assert finding.scope == "line"
    assert finding.invoice_line_id == "L1"
    assert finding.disposition == FindingDisposition.AUTO_EXCEPTION
    assert finding.action == ActionType.DRAFT_VENDOR_CLARIFICATION
    assert finding.computed_values == {
        "billed_rate_cad": Decimal("175.00"),
        "authorized_rate_cad": Decimal("150.00"),
    }


def test_s1_evidence_quote_came_from_real_extraction_and_matches_the_canonical_clause(
    s1_result,
) -> None:
    finding = s1_result.findings[0]
    quote_evidence = next(e for e in finding.evidence if e.kind == "supporting_quote")
    line_evidence = next(e for e in finding.evidence if e.kind == "invoice_line")

    expected_clauses = load_contract_clauses()
    assert quote_evidence.quote == expected_clauses.rate_card[ServiceRole.SENIOR_CONSULTANT]
    assert quote_evidence.document_id == "MSA-2026-014"
    assert quote_evidence.section == "4.1"
    assert quote_evidence.page == 2

    assert line_evidence.document_id == "INV-2026-061"
    assert line_evidence.line_id == "L1"


def test_s1_l2_is_clean_and_not_in_any_finding(s1_result) -> None:
    assert s1_result.clean_line_ids == ["L2"]
    assert all(f.invoice_line_id != "L2" for f in s1_result.findings)


def test_s1_trace_records_all_three_required_extraction_operations(s1_result) -> None:
    purposes = {call.purpose for call in s1_result.trace.model_calls}
    assert purposes == {"MSA_EXTRACTION", "SOW_EXTRACTION", "INVOICE_EXTRACTION"}
    assert all(call.schema_valid for call in s1_result.trace.model_calls)
    assert s1_result.trace.disposition == InvoiceDisposition.EXCEPTIONS_FOUND
    assert s1_result.approval_state == ApprovalState.AWAITING_REVIEW


def test_s1_drafted_action_is_a_draft_never_an_executed_action(s1_result) -> None:
    assert s1_result.drafted_action is not None
    assert s1_result.drafted_action.action_type == ActionType.DRAFT_VENDOR_CLARIFICATION
    summary = s1_result.drafted_action.summary.lower()
    assert "draft" in summary
    assert "no communication has been sent" in summary


def test_s6_clean_invoice_produces_zero_findings(s6_result) -> None:
    assert s6_result.disposition == InvoiceDisposition.CLEAN
    assert s6_result.findings == []
    assert s6_result.clean_line_ids == ["L1", "L2"]
    assert s6_result.approval_state == ApprovalState.NO_ACTION_REQUIRED
    assert s6_result.drafted_action is None
