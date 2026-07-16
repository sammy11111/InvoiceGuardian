"""Guarding tests for the Codex-review addenda (each item gets its own test)."""

from __future__ import annotations

from decimal import Decimal

import eval_fixtures as fx
import pytest

from invoiceguardian.dataset_generator.content import load_answer_keys
from invoiceguardian.evaluation.evaluator import _pooled_latency_median, evaluate_run
from invoiceguardian.evaluation.grounding import grounding_for_pair, matched_finding_is_supported
from invoiceguardian.evaluation.matching import expected_key, predicted_key
from invoiceguardian.schemas.evaluation import EvaluationDataset, ScenarioAnswerKey
from invoiceguardian.schemas.runtime import (
    ExceptionType,
    FindingDisposition,
    SupportingQuoteEvidence,
)


@pytest.fixture(scope="module")
def dataset() -> EvaluationDataset:
    return load_answer_keys()


# --- Item 1: missing scenario results count as false negatives --------------


def test_run_missing_s2_scores_recall_two_thirds(dataset) -> None:
    # A 5-scenario run (every scenario except S2) — S2's planted exception must
    # count as a false negative, not be skipped.
    present = [s for s in dataset.scenarios if s.scenario_id != "S2"]
    results = [fx.build_perfect_result(dataset, s) for s in present]
    ev = evaluate_run(dataset, fx.build_run(dataset, results=results))

    assert ev.planted_exceptions == 3
    assert ev.detection_true_positives == 2  # S1 + S5
    assert ev.detection_false_negatives == 1  # S2 absent -> FN
    assert ev.detection_recall == pytest.approx(2 / 3)
    assert ev.detection_precision == 1.0  # no false positives among what ran


# --- Item 2: S4 escalation must key-match -----------------------------------


def test_s4_escalate_on_wrong_line_does_not_count_as_correct(dataset) -> None:
    s4 = next(s for s in dataset.scenarios if s.scenario_id == "S4")
    scope_quote = next(
        e.quote for e in s4.expected_findings[0].evidence if e.kind == "supporting_quote"
    )
    # ESCALATE disposition, but on line L9 — cannot key-match the expected
    # finding on L1, so it is not a correct abstention.
    from invoiceguardian.schemas.runtime import (
        ActionType,
        ExceptionFinding,
        InvoiceLineEvidence,
    )

    wrong_line = ExceptionFinding(
        finding_type=ExceptionType.SCOPE_AMBIGUITY,
        basis="semantic",
        scope="line",
        invoice_line_id="L9",
        disposition=FindingDisposition.ESCALATE,
        action=ActionType.HUMAN_REVIEW,
        evidence=[
            SupportingQuoteEvidence(
                document_id="SOW-2026-03", section="2", page=1, quote=scope_quote
            ),
            InvoiceLineEvidence(document_id=s4.invoice_id, line_id="L9"),
        ],
    )
    result = fx.build_perfect_result(dataset, s4, findings=[wrong_line])
    ev = evaluate_run(dataset, fx.build_run(dataset, results=[result]))
    assert ev.abstention == "miss"
    assert ev.hard_gates().s4_escalated is False


# --- Item 3: multiple abstention scenarios ----------------------------------


def _two_abstention_dataset(
    dataset: EvaluationDataset,
) -> tuple[EvaluationDataset, ScenarioAnswerKey]:
    """Adds a synthetic second escalation scenario (mirroring the v1.4 S7
    branch) so multi-abstention handling can be exercised."""
    s4 = next(s for s in dataset.scenarios if s.scenario_id == "S4")
    s7 = s4.model_copy(update={"scenario_id": "S7", "invoice_id": "INV-2026-067"})
    extended = dataset.model_copy(update={"scenarios": [*dataset.scenarios, s7]})
    return extended, s7


def test_all_abstention_scenarios_must_escalate_for_gate_3(dataset) -> None:
    extended, s7 = _two_abstention_dataset(dataset)
    results = [fx.build_perfect_result(extended, s) for s in extended.scenarios]
    ev = evaluate_run(extended, fx.build_run(extended, results=results))
    assert ev.abstention == "correct"
    assert ev.hard_gates().s4_escalated is True


def test_one_abstention_scenario_missing_escalation_fails_gate_3(dataset) -> None:
    extended, s7 = _two_abstention_dataset(dataset)
    # S4 escalates correctly; the synthetic S7 is a clean pass (miss).
    results = []
    for s in extended.scenarios:
        findings = [] if s.scenario_id == "S7" else None
        results.append(fx.build_perfect_result(extended, s, findings=findings))
    ev = evaluate_run(extended, fx.build_run(extended, results=results))
    assert ev.abstention != "correct"
    assert ev.hard_gates().s4_escalated is False


# --- Item 5: atom checks include source metadata ----------------------------


def test_supporting_quote_with_wrong_section_does_not_satisfy_its_atom(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    correct = fx.expected_finding_to_runtime(s1.expected_findings[0])
    # Correct quote text, but cite it under the wrong section number.
    tampered = correct.model_copy(
        update={
            "evidence": [
                SupportingQuoteEvidence(
                    document_id="MSA-2026-014",
                    section="9.9",  # wrong section
                    page=2,
                    quote="Senior Consultant services shall be billed at CAD $150.00 per hour.",
                ),
                correct.evidence[1],  # keep the valid invoice-line ref
            ]
        }
    )
    assert grounding_for_pair(tampered, s1.expected_findings[0]).completeness < 1.0
    assert matched_finding_is_supported(tampered, s1.expected_findings[0]) is False


# --- Item 7: value accuracy (observational) ---------------------------------


def test_value_accuracy_is_one_for_a_perfect_run(dataset) -> None:
    ev = evaluate_run(dataset, fx.perfect_run(dataset))
    assert ev.value_total == 5  # S1 (2) + S5 (3)
    assert ev.value_accuracy == 1.0


def test_value_accuracy_penalizes_wrong_computed_values_without_touching_gates(dataset) -> None:
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    perfect_s1 = fx.expected_finding_to_runtime(s1.expected_findings[0])
    wrong_values = perfect_s1.model_copy(
        update={
            "computed_values": {
                "billed_rate_cad": Decimal("999.00"),  # wrong
                "authorized_rate_cad": Decimal("150.00"),  # right
            }
        }
    )
    results = [
        fx.build_perfect_result(
            dataset, s, findings=[wrong_values] if s.scenario_id == "S1" else None
        )
        for s in dataset.scenarios
    ]
    ev = evaluate_run(dataset, fx.build_run(dataset, results=results))
    assert ev.value_correct == 4  # 1 of 2 on S1, 3 of 3 on S5
    assert ev.value_total == 5
    assert ev.value_accuracy == pytest.approx(4 / 5)
    # Value accuracy is observational: detection and gates are unaffected.
    assert ev.detection_true_positives == 3
    assert ev.hard_gates().passed is True


# --- Item 8: latency pooled across replicates, not median-of-medians --------


def test_latency_is_pooled_across_replicates_not_median_of_medians(dataset) -> None:
    # Replicate 1 contributes one invoice latency (1000); replicate 2
    # contributes three (2000 each). Pooled: median([1000, 2000, 2000, 2000])
    # = 2000. A median-of-per-run-medians would be median([1000, 2000]) = 1500.
    r1 = fx.build_run(
        dataset,
        run_id="r1",
        results=[],
        model_call_log=fx.build_model_call_log(["INV-2026-061"], latency_ms=1000.0),
    )
    r2 = fx.build_run(
        dataset,
        run_id="r2",
        results=[],
        model_call_log=fx.build_model_call_log(
            ["INV-2026-061", "INV-2026-062", "INV-2026-063"], latency_ms=2000.0
        ),
    )
    assert _pooled_latency_median([r1, r2]) == 2000.0


# --- Item 9: invoice-scope match key includes invoice_id --------------------


def test_invoice_scope_key_uses_invoice_id_and_line_scope_uses_line_id(dataset) -> None:
    s5 = next(s for s in dataset.scenarios if s.scenario_id == "S5")  # AGGREGATE_CAP, invoice-scope
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")  # RATE_MISMATCH, line-scope

    cap = fx.expected_finding_to_runtime(s5.expected_findings[0])
    rate = fx.expected_finding_to_runtime(s1.expected_findings[0])

    assert predicted_key(cap, s5.invoice_id) == ("AGGREGATE_CAP_EXCEEDED", "invoice", s5.invoice_id)
    assert expected_key(s5.expected_findings[0], s5.invoice_id) == (
        "AGGREGATE_CAP_EXCEEDED",
        "invoice",
        s5.invoice_id,
    )
    assert predicted_key(rate, s1.invoice_id) == ("RATE_MISMATCH", "line", "L1")
