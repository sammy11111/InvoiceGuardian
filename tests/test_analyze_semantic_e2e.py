"""Live end-to-end tests for the semantic path and the aggregate cap (S2-S5),
plus the full-dataset capstone.

These assert the pipeline's ACTUAL behavior under the neutral, committed
semantic prompt — not the answer key — per the Fable 5 adjudication that the
prompt is neutral and claude-sonnet-5's S2/S4 misclassifications are genuine
model behavior on the frozen dataset. Deterministic scenarios (S5) and the
stable semantic outcomes (S3) are asserted exactly; S4 is asserted as its
stable (answer-key-divergent) outcome; S2 is unstable and asserted only as
"not clean". Skipped without an API key.
"""

from __future__ import annotations

import eval_fixtures as fx
import pytest

from invoiceguardian.analyze import run_analysis
from invoiceguardian.dataset_generator.content import load_answer_keys
from invoiceguardian.evaluation.evaluator import evaluate_run
from invoiceguardian.extraction.anthropic_client import get_api_key
from invoiceguardian.schemas.runtime import ExceptionType, InvoiceDisposition


def _has_api_key() -> bool:
    try:
        get_api_key()
    except RuntimeError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_api_key(), reason="ANTHROPIC_API_KEY not set; skipping live-model tests"
)

ALL_INVOICES = [
    "INV-2026-061",
    "INV-2026-062",
    "INV-2026-063",
    "INV-2026-064",
    "INV-2026-065",
    "INV-2026-066",
]


@pytest.fixture(scope="module")
def all_results():
    """Run every scenario once, live, and reuse across the capstone assertions."""
    return {invoice_id: run_analysis(invoice_id) for invoice_id in ALL_INVOICES}


# --- S5: deterministic aggregate cap (answer-key-faithful) ------------------


def test_s5_fires_invoice_scope_aggregate_cap_with_all_lines_clean(all_results) -> None:
    result = all_results["INV-2026-065"]
    assert result.disposition is InvoiceDisposition.EXCEPTIONS_FOUND
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.finding_type == ExceptionType.AGGREGATE_CAP_EXCEEDED
    assert finding.scope == "invoice"
    assert finding.invoice_line_id is None
    assert result.clean_line_ids == ["L1", "L2", "L3"]


# --- S3: stable EQUIVALENT (answer-key-faithful) ----------------------------


def test_s3_equivalence_trap_produces_zero_findings(all_results) -> None:
    result = all_results["INV-2026-063"]
    assert result.disposition is InvoiceDisposition.CLEAN
    assert result.findings == []
    assert result.clean_line_ids == ["L1", "L2"]


# --- S4: stable but answer-key-DIVERGENT (documented model finding) ---------


def test_s4_is_classified_equivalent_diverging_from_the_answer_key(all_results) -> None:
    """DOCUMENTED DIVERGENCE (Fable 5 adjudicated, genuine model behavior):
    the answer key expects SCOPE_AMBIGUITY / ESCALATION_REQUIRED, but
    claude-sonnet-5 stably reads 'ERP Rollout Advisory Support' as EQUIVALENT
    to the SOW scope, producing a clean pass. This test records the actual
    behavior; it is NOT an endorsement of it."""
    result = all_results["INV-2026-064"]
    assert result.disposition is InvoiceDisposition.CLEAN
    assert result.findings == []


# --- S2: unstable — asserted only as "not clean" ----------------------------


def test_s2_line_is_flagged_not_passed_as_authorized(all_results) -> None:
    """S2 is unstable (AMBIGUOUS ~3/4, NOT_AUTHORIZED ~1/4). Both non-clean
    outcomes produce a finding on L1, so we assert only that L1 is flagged
    (not EQUIVALENT), never the specific class — asserting the class would be
    flaky."""
    result = all_results["INV-2026-062"]
    assert result.disposition is not InvoiceDisposition.CLEAN
    assert any(f.invoice_line_id == "L1" for f in result.findings)
    assert "L1" not in result.clean_line_ids


# --- Capstone: full-dataset scorecard, observational ------------------------


def test_capstone_full_dataset_scorecard(all_results) -> None:
    """The whole system closing the loop for real: six live AnalysisResults
    scored as one benchmark run. Asserts only the STABLE facts; the S2/S4
    misclassifications mean this arm does NOT pass all hard gates — which is
    the honest, Fable-adjudicated result, not a bug."""
    dataset = load_answer_keys()
    results = [all_results[i] for i in ALL_INVOICES]
    run = fx.build_run(
        dataset,
        run_id="capstone",
        results=results,
        model_call_log=fx.build_model_call_log_from_results(results),
    )
    ev = evaluate_run(dataset, run)

    # The deterministic exceptions (S1 rate, S5 cap) always match.
    matched_types = {p.predicted.finding_type for m in ev.scenario_matches for p in m.matched}
    assert ExceptionType.RATE_MISMATCH in matched_types
    assert ExceptionType.AGGREGATE_CAP_EXCEEDED in matched_types
    assert ev.detection_true_positives >= 2

    # Every matched finding is fully grounded (evidence is deterministically built).
    assert ev.grounding_completeness == 1.0

    # Extraction is perfect over the full 106-field manifest.
    assert ev.extraction.accuracy_over_manifest == 1.0

    # The 11-operation manifest is real and all schema-valid.
    assert ev.total_ops == 11
    assert ev.all_ops_schema_valid is True

    # S4's stable EQUIVALENT is an abstention miss -> gate 3 fails -> arm does
    # not pass all gates. This is the adjudicated genuine result.
    assert ev.abstention == "miss"
    assert ev.hard_gates().s4_escalated is False
    assert ev.hard_gates().passed is False
