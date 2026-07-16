"""Adversarial tests: deliberately-wrong predictions that MUST fail the
right hard gate. These are the tests that keep the evaluator honest — a
grader that silently passes bad output corrupts every downstream metric.
"""

from __future__ import annotations

from decimal import Decimal

import eval_fixtures as fx
import pytest

from invoiceguardian.dataset_generator.content import load_answer_keys
from invoiceguardian.evaluation.evaluator import evaluate_run
from invoiceguardian.evaluation.grounding import (
    has_fabricated_citation,
    matched_finding_is_supported,
)
from invoiceguardian.schemas.evaluation import EvaluationDataset, ModelCallLogEntry
from invoiceguardian.schemas.runtime import (
    ActionType,
    ComputedTotalEvidence,
    ExceptionFinding,
    ExceptionType,
    FindingDisposition,
    InvoiceLineEvidence,
    SupportingQuoteEvidence,
)

RATE_QUOTE = "Senior Consultant services shall be billed at CAD $150.00 per hour."


@pytest.fixture(scope="module")
def dataset() -> EvaluationDataset:
    return load_answer_keys()


def _rate_finding(evidence) -> ExceptionFinding:
    return ExceptionFinding(
        finding_type=ExceptionType.RATE_MISMATCH,
        basis="deterministic",
        scope="line",
        invoice_line_id="L1",
        disposition=FindingDisposition.AUTO_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=evidence,
        computed_values={
            "billed_rate_cad": Decimal("175.00"),
            "authorized_rate_cad": Decimal("150.00"),
        },
    )


def test_fabricated_quote_on_a_false_positive_finding_fails_gate_1(dataset) -> None:
    """A fabricated citation on an UNMATCHED (false-positive) finding must
    still fail gate 1 — "zero fabricated citations anywhere". This exercises
    the false-positive branch of the unsupported check, distinct from the
    matched-finding branch."""
    s6 = next(s for s in dataset.scenarios if s.scenario_id == "S6")  # clean: any finding is an FP
    fabricated_fp = _rate_finding(
        [
            SupportingQuoteEvidence(
                document_id="MSA-2026-014",
                section="4.1",
                page=2,
                quote="Senior Consultant services shall be billed at CAD $999.00 per hour.",
            ),
            InvoiceLineEvidence(document_id=s6.invoice_id, line_id="L1"),
        ]
    )
    result = fx.build_perfect_result(dataset, s6, findings=[fabricated_fp])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.detection_false_positives == 1  # unmatched on a clean scenario
    assert ev.unsupported_finding_count == 1  # ... and unsupported via fabrication
    assert ev.hard_gates().zero_unsupported_findings is False
    assert ev.hard_gates().zero_false_positives is False


# --- Gate 4: false positives -------------------------------------------------


@pytest.mark.parametrize("clean_scenario_id", ["S3", "S6"])
def test_finding_on_a_clean_scenario_is_a_false_positive_and_fails_gate_4(
    dataset, clean_scenario_id
) -> None:
    clean = next(s for s in dataset.scenarios if s.scenario_id == clean_scenario_id)
    bogus = _rate_finding(
        [
            SupportingQuoteEvidence(
                document_id="MSA-2026-014", section="4.1", page=2, quote=RATE_QUOTE
            ),
            InvoiceLineEvidence(document_id=clean.invoice_id, line_id="L1"),
        ]
    )
    result = fx.build_perfect_result(dataset, clean, findings=[bogus])
    run = fx.build_run(dataset, results=[result])
    ev = evaluate_run(dataset, run)

    assert ev.detection_false_positives == 1
    assert ev.hard_gates().zero_false_positives is False
    assert ev.hard_gates().passed is False


def test_duplicate_finding_second_copy_is_a_false_positive_not_a_second_tp(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    correct = fx.expected_finding_to_runtime(s1.expected_findings[0])
    result = fx.build_perfect_result(dataset, s1, findings=[correct, correct.model_copy(deep=True)])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))

    assert ev.detection_true_positives == 1
    assert ev.detection_false_positives == 1
    assert ev.hard_gates().zero_false_positives is False


# --- Gate 1: unsupported findings (missing evidence / fabrication) -----------
#
# Gate 1 for a matched finding uses the answer key's required atoms: a finding
# that key-matches but does not satisfy every required atom is unsupported.


def test_matched_finding_missing_its_invoice_line_reference_fails_gate_1(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    # Governing rate quote only, no invoice-line reference -> a required atom
    # (the line reference) is unsatisfied.
    missing = _rate_finding(
        [
            SupportingQuoteEvidence(
                document_id="MSA-2026-014", section="4.1", page=2, quote=RATE_QUOTE
            )
        ]
    )
    assert matched_finding_is_supported(missing, s1.expected_findings[0]) is False
    result = fx.build_perfect_result(dataset, s1, findings=[missing])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.unsupported_finding_count == 1
    assert ev.hard_gates().zero_unsupported_findings is False


def test_matched_finding_with_only_an_invoice_line_reference_fails_gate_1(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    line_only = _rate_finding([InvoiceLineEvidence(document_id=s1.invoice_id, line_id="L1")])
    # A line reference alone leaves the governing-rate-quote atom unsatisfied.
    assert matched_finding_is_supported(line_only, s1.expected_findings[0]) is False


def test_rate_mismatch_citing_the_cap_quote_fails_gate_1(dataset) -> None:
    """Codex item 6: a RATE_MISMATCH whose supporting quote is the (canonical,
    non-fabricated) monthly-cap clause instead of the governing rate clause
    must fail gate 1 — carrying *a* quote is not enough."""
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    cap_quote = "Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00."
    wrong_quote = _rate_finding(
        [
            SupportingQuoteEvidence(
                document_id="MSA-2026-014", section="4.3", page=2, quote=cap_quote
            ),
            InvoiceLineEvidence(document_id=s1.invoice_id, line_id="L1"),
        ]
    )
    # The cap quote is not fabricated, but it is not the required rate atom.
    assert has_fabricated_citation(wrong_quote) is False
    assert matched_finding_is_supported(wrong_quote, s1.expected_findings[0]) is False
    result = fx.build_perfect_result(dataset, s1, findings=[wrong_quote])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.unsupported_finding_count == 1
    assert ev.hard_gates().zero_unsupported_findings is False


def test_fabricated_quote_fails_gate_1(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    fabricated = _rate_finding(
        [
            SupportingQuoteEvidence(
                document_id="MSA-2026-014",
                section="4.1",
                page=2,
                quote="Senior Consultant services shall be billed at CAD $999.00 per hour.",
            ),
            InvoiceLineEvidence(document_id=s1.invoice_id, line_id="L1"),
        ]
    )
    assert has_fabricated_citation(fabricated) is True
    result = fx.build_perfect_result(dataset, s1, findings=[fabricated])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.unsupported_finding_count == 1
    assert ev.hard_gates().zero_unsupported_findings is False


def test_aggregate_cap_finding_missing_computed_total_fails_gate_1(dataset) -> None:
    s5 = next(s for s in dataset.scenarios if s.scenario_id == "S5")
    cap_quote = "Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00."
    no_total = ExceptionFinding(
        finding_type=ExceptionType.AGGREGATE_CAP_EXCEEDED,
        basis="deterministic",
        scope="invoice",
        invoice_line_id=None,
        disposition=FindingDisposition.AUTO_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            SupportingQuoteEvidence(
                document_id="MSA-2026-014", section="4.3", page=2, quote=cap_quote
            )
        ],
    )
    # Matched to S5 but missing the required computed-total atom.
    assert matched_finding_is_supported(no_total, s5.expected_findings[0]) is False
    with_total = no_total.model_copy(
        update={
            "evidence": [
                *no_total.evidence,
                ComputedTotalEvidence(document_id="INV-2026-065", value_cad=Decimal("25750.00")),
            ]
        }
    )
    assert matched_finding_is_supported(with_total, s5.expected_findings[0]) is True


# --- Gate 3: S4 abstention ---------------------------------------------------


def test_s4_confident_exception_fails_gate_3(dataset) -> None:
    s4 = next(s for s in dataset.scenarios if s.scenario_id == "S4")
    scope_quote = next(
        e.quote for e in s4.expected_findings[0].evidence if e.kind == "supporting_quote"
    )
    confident = ExceptionFinding(
        finding_type=ExceptionType.SCOPE_AMBIGUITY,
        basis="semantic",
        scope="line",
        invoice_line_id="L1",
        disposition=FindingDisposition.SEMANTIC_EXCEPTION,  # confident, not ESCALATE
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            SupportingQuoteEvidence(
                document_id="SOW-2026-03", section="2", page=1, quote=scope_quote
            ),
            InvoiceLineEvidence(document_id=s4.invoice_id, line_id="L1"),
        ],
    )
    result = fx.build_perfect_result(dataset, s4, findings=[confident])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.abstention == "incorrect_confident"
    assert ev.hard_gates().s4_escalated is False


def test_s4_clean_pass_fails_gate_3_as_a_miss(dataset) -> None:
    s4 = next(s for s in dataset.scenarios if s.scenario_id == "S4")
    result = fx.build_perfect_result(dataset, s4, findings=[])  # clean pass
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.abstention == "miss"
    assert ev.hard_gates().s4_escalated is False


def test_s4_both_escalate_and_confident_exception_is_disqualifying(dataset) -> None:
    """A confident exception on S4 must dominate even when an ESCALATE finding
    is also present — its presence disqualifies, per SCORING.md."""
    s4 = next(s for s in dataset.scenarios if s.scenario_id == "S4")
    scope_quote = next(
        e.quote for e in s4.expected_findings[0].evidence if e.kind == "supporting_quote"
    )
    escalate = fx.expected_finding_to_runtime(s4.expected_findings[0])
    confident = ExceptionFinding(
        finding_type=ExceptionType.SCOPE_AMBIGUITY,
        basis="semantic",
        scope="line",
        invoice_line_id="L1",
        disposition=FindingDisposition.SEMANTIC_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            SupportingQuoteEvidence(
                document_id="SOW-2026-03", section="2", page=1, quote=scope_quote
            ),
            InvoiceLineEvidence(document_id=s4.invoice_id, line_id="L1"),
        ],
    )
    result = fx.build_perfect_result(dataset, s4, findings=[escalate, confident])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.abstention == "incorrect_confident"
    assert ev.hard_gates().s4_escalated is False


# --- Gate 2: schema validity -------------------------------------------------


def test_schema_invalid_operation_without_successful_retry_fails_gate_2(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    result = fx.build_perfect_result(dataset, s1)
    broken_log = fx.build_model_call_log(
        [s1.invoice_id], first_pass_valid=False, final_valid=False, retry_count=1
    )
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result], model_call_log=broken_log))
    assert ev.all_ops_schema_valid is False
    assert ev.hard_gates().schema_validity_100pct is False


def test_operation_valid_only_after_one_retry_still_passes_gate_2(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    result = fx.build_perfect_result(dataset, s1)
    recovered_log = fx.build_model_call_log(
        [s1.invoice_id], first_pass_valid=False, final_valid=True, retry_count=1
    )
    ev = evaluate_run(
        dataset, fx.build_run(dataset, results=[result], model_call_log=recovered_log)
    )
    assert ev.all_ops_schema_valid is True
    assert ev.hard_gates().schema_validity_100pct is True
    # First-pass validity is still penalized even though the gate passes.
    assert ev.first_pass_valid_ops == 0


def test_extra_operation_does_not_alter_the_first_pass_or_gate_2_denominator(dataset) -> None:
    """An additional (non-manifest) model call is logged but must not move the
    preregistered denominator (SCORING.md). A schema-invalid extra op is
    excluded from both first-pass validity and gate 2."""
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    result = fx.build_perfect_result(dataset, s1)

    required_log = fx.build_model_call_log([s1.invoice_id])  # MSA, SOW, INVOICE = 3 required
    extra_bad = ModelCallLogEntry(
        operation="AD_HOC_RECHECK",  # not a required-manifest identity
        schema_valid_first_pass=False,
        retry_count=1,
        schema_valid_final=False,
        latency_ms=500.0,
        input_tokens=100,
        output_tokens=20,
    )
    ev = evaluate_run(
        dataset,
        fx.build_run(dataset, results=[result], model_call_log=[*required_log, extra_bad]),
    )
    # Denominator is the 3 required ops, all first-pass valid — the bad extra
    # op is ignored by both metrics.
    assert ev.total_ops == 3
    assert ev.first_pass_valid_ops == 3
    assert ev.all_ops_schema_valid is True
    assert ev.hard_gates().schema_validity_100pct is True


# --- Wrong-type finding ------------------------------------------------------


def test_wrong_type_finding_does_not_match_and_is_a_false_positive(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    # Right line, wrong finding type -> cannot key-match S1's RATE_MISMATCH.
    wrong_type = ExceptionFinding(
        finding_type=ExceptionType.SCOPE_AMBIGUITY,
        basis="semantic",
        scope="line",
        invoice_line_id="L1",
        disposition=FindingDisposition.ESCALATE,
        action=ActionType.HUMAN_REVIEW,
        evidence=[
            SupportingQuoteEvidence(
                document_id="SOW-2026-03",
                section="2",
                page=1,
                quote=(
                    "Northbridge shall provide implementation support for Maplecore's ERP rollout, "
                    "data migration validation, and training documentation."
                ),
            ),
            InvoiceLineEvidence(document_id=s1.invoice_id, line_id="L1"),
        ],
    )
    # Full perfect run with only S1's finding swapped for the wrong type, so
    # the sole unmatched expected finding is S1's (other scenarios still
    # matched — isolating this failure from the fixed-denominator FN counting).
    results = [
        fx.build_perfect_result(
            dataset, s, findings=[wrong_type] if s.scenario_id == "S1" else None
        )
        for s in dataset.scenarios
    ]
    ev = evaluate_run(dataset, fx.build_run(dataset, results=results))
    assert ev.detection_true_positives == 2  # S2 + S5 still matched
    assert ev.detection_false_positives == 1  # the wrong-type finding on S1
    assert ev.detection_false_negatives == 1  # S1's real exception went unmatched
