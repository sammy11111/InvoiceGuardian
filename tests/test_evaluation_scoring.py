"""Positive/correctness tests for the evaluator, using constructed fixtures
(perfect pipeline output reconstructed from the answer key)."""

from __future__ import annotations

from decimal import Decimal

import eval_fixtures as fx
import pytest

from invoiceguardian.dataset_generator.content import load_answer_keys
from invoiceguardian.evaluation.evaluator import evaluate_run, summarize_arm, summarize_arms
from invoiceguardian.evaluation.grounding import grounding_for_pair
from invoiceguardian.evaluation.manifest import score_extraction
from invoiceguardian.evaluation.matching import match_scenario
from invoiceguardian.schemas.evaluation import EvaluationDataset
from invoiceguardian.schemas.runtime import (
    ActionType,
    ExceptionFinding,
    ExceptionType,
    FindingDisposition,
    InvoiceLineEvidence,
    SupportingQuoteEvidence,
)


@pytest.fixture(scope="module")
def dataset() -> EvaluationDataset:
    return load_answer_keys()


# --- Whole-run: perfect prediction scores everything at ceiling -------------


def test_perfect_full_run_scores_all_metric_families_at_ceiling(dataset) -> None:
    ev = evaluate_run(dataset, fx.perfect_run(dataset))

    assert (
        ev.detection_true_positives,
        ev.detection_false_positives,
        ev.detection_false_negatives,
    ) == (3, 0, 0)
    assert ev.planted_exceptions == 3
    assert ev.detection_recall == 1.0
    assert ev.detection_precision == 1.0
    assert ev.grounding_completeness == 1.0
    assert ev.disposition_accuracy == 1.0
    assert ev.abstention == "correct"
    assert ev.extraction.correct == 106
    assert ev.extraction.accuracy_over_manifest == 1.0
    assert ev.hard_gates().passed is True


def test_perfect_arm_weighted_score_is_one_and_gates_pass(dataset) -> None:
    summary = summarize_arm(dataset, "perfect", [fx.perfect_run(dataset)])
    assert summary.hard_gates.passed is True
    assert summary.weighted_score == pytest.approx(1.0)
    assert summary.detection_recall == 1.0
    assert summary.grounding_completeness == 1.0
    assert summary.extraction_accuracy == 1.0
    assert summary.abstention_correctness == "correct"


# --- Per-scenario: each planted exception and each clean case ---------------


@pytest.mark.parametrize(
    ("scenario_id", "finding_type"),
    [
        ("S1", ExceptionType.RATE_MISMATCH),
        ("S2", ExceptionType.UNAUTHORIZED_SERVICE),
        ("S5", ExceptionType.AGGREGATE_CAP_EXCEEDED),
    ],
)
def test_each_planted_exception_matches_with_full_grounding(
    dataset, scenario_id, finding_type
) -> None:
    scenario = next(s for s in dataset.scenarios if s.scenario_id == scenario_id)
    result = fx.build_perfect_result(dataset, scenario)
    match = match_scenario(
        scenario_id, scenario.invoice_id, result.findings, scenario.expected_findings
    )

    assert len(match.matched) == 1
    assert not match.false_positives
    assert not match.false_negatives
    pair = match.matched[0]
    assert pair.predicted.finding_type == finding_type
    grounding = grounding_for_pair(pair.predicted, pair.expected)
    assert grounding.completeness == 1.0


@pytest.mark.parametrize("scenario_id", ["S3", "S6"])
def test_clean_scenarios_produce_zero_findings_and_zero_false_positives(
    dataset, scenario_id
) -> None:
    scenario = next(s for s in dataset.scenarios if s.scenario_id == scenario_id)
    result = fx.build_perfect_result(dataset, scenario)
    assert result.findings == []
    match = match_scenario(
        scenario_id, scenario.invoice_id, result.findings, scenario.expected_findings
    )
    assert not match.false_positives
    assert not match.matched


def test_s4_perfect_escalation_scores_as_correct_abstention(dataset) -> None:
    run = fx.perfect_run(dataset, scenario_ids=["S4"])
    ev = evaluate_run(dataset, run)
    assert ev.s4_present is True
    assert ev.abstention == "correct"
    # S4 contributes to no detection metric: it is never counted as a TP, and
    # the recall denominator stays fixed at the dataset's 3 planted exceptions.
    assert ev.detection_true_positives == 0
    assert ev.planted_exceptions == 3


# --- Matching mechanics ------------------------------------------------------


def test_matching_is_one_to_one_within_a_scenario(dataset) -> None:
    scenario = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    quote = "Senior Consultant services shall be billed at CAD $150.00 per hour."
    duplicate = ExceptionFinding(
        finding_type=ExceptionType.RATE_MISMATCH,
        basis="deterministic",
        scope="line",
        invoice_line_id="L1",
        disposition=FindingDisposition.AUTO_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            SupportingQuoteEvidence(document_id="MSA-2026-014", section="4.1", page=2, quote=quote),
            InvoiceLineEvidence(document_id=scenario.invoice_id, line_id="L1"),
        ],
        computed_values={
            "billed_rate_cad": Decimal("175.00"),
            "authorized_rate_cad": Decimal("150.00"),
        },
    )
    correct = fx.expected_finding_to_runtime(scenario.expected_findings[0])

    match = match_scenario(
        "S1", scenario.invoice_id, [correct, duplicate], scenario.expected_findings
    )
    assert len(match.matched) == 1
    assert len(match.false_positives) == 1  # the duplicate cannot match a second time


# --- Extraction accuracy -----------------------------------------------------


def test_extraction_accuracy_is_one_over_106_for_a_perfect_full_run(dataset) -> None:
    run = fx.perfect_run(dataset)
    score = score_extraction(dataset, run.analysis_results)
    assert score.covered == 106
    assert score.correct == 106
    assert score.accuracy_over_manifest == 1.0


def test_extraction_accuracy_penalizes_a_single_wrong_field(dataset) -> None:
    scenario = next(s for s in dataset.scenarios if s.scenario_id == "S1")
    facts = fx.perfect_extracted_facts(dataset, scenario.invoice_id)
    # Corrupt one field's value.
    corrupted = [
        f.model_copy(update={"value": "999.99"}) if f.field == "monthly_cap_cad" else f
        for f in facts
    ]
    result = fx.build_perfect_result(dataset, scenario, extracted_facts=corrupted)
    score = score_extraction(dataset, [result])
    assert score.correct == score.covered - 1


# --- Latency normalization across arms --------------------------------------


def test_normalized_latency_favors_the_faster_arm(dataset) -> None:
    fast = fx.build_run(
        dataset,
        run_id="fast",
        results=[fx.build_perfect_result(dataset, s) for s in dataset.scenarios],
        model_call_log=fx.build_model_call_log(
            [s.invoice_id for s in dataset.scenarios], latency_ms=1000.0
        ),
    )
    slow = fx.build_run(
        dataset,
        run_id="slow",
        results=[fx.build_perfect_result(dataset, s) for s in dataset.scenarios],
        model_call_log=fx.build_model_call_log(
            [s.invoice_id for s in dataset.scenarios], latency_ms=2000.0
        ),
    )
    summaries = {s.arm_label: s for s in summarize_arms(dataset, {"fast": [fast], "slow": [slow]})}
    assert summaries["fast"].normalized_latency == pytest.approx(100.0)
    assert summaries["slow"].normalized_latency == pytest.approx(50.0)
