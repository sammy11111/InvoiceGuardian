"""Evaluator against REAL pipeline output (not fixtures): run the live
pipeline on S1 and S6, wrap the AnalysisResults in a BenchmarkRun, and
confirm the evaluator scores them correctly. Skipped without an API key.
"""

from __future__ import annotations

import eval_fixtures as fx
import pytest

from invoiceguardian.analyze import run_analysis
from invoiceguardian.dataset_generator.content import load_answer_keys
from invoiceguardian.evaluation.evaluator import evaluate_run
from invoiceguardian.extraction.anthropic_client import get_api_key


def _has_api_key() -> bool:
    try:
        get_api_key()
    except RuntimeError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_api_key(), reason="ANTHROPIC_API_KEY not set; skipping live-model evaluation test"
)


@pytest.fixture(scope="module")
def real_s1_s6_evaluation():
    dataset = load_answer_keys()
    s1 = run_analysis("INV-2026-061")
    s6 = run_analysis("INV-2026-066")
    log = fx.build_model_call_log(["INV-2026-061", "INV-2026-066"])
    run = fx.build_run(dataset, run_id="real-s1-s6", results=[s1, s6], model_call_log=log)
    return dataset, evaluate_run(dataset, run)


def test_real_s1_scores_as_one_matched_rate_mismatch_with_full_grounding(
    real_s1_s6_evaluation,
) -> None:
    _dataset, ev = real_s1_s6_evaluation
    # S1's real exception is matched with full grounding; S6 is clean and
    # produces no false positive.
    assert ev.detection_true_positives == 1
    assert ev.detection_false_positives == 0
    assert ev.grounding_completeness == 1.0
    assert ev.disposition_accuracy == 1.0
    # Fixed denominator: the two planted exceptions in the scenarios this
    # partial run did NOT analyze (S2, S5) count as false negatives, so recall
    # is 1/3 — not silently 1/1 (Codex item 1).
    assert ev.detection_false_negatives == 2
    assert ev.planted_exceptions == 3
    assert ev.detection_recall == pytest.approx(1 / 3)


def test_real_run_has_zero_false_positives_and_zero_unsupported(real_s1_s6_evaluation) -> None:
    _dataset, ev = real_s1_s6_evaluation
    assert ev.hard_gates().zero_false_positives is True
    assert ev.hard_gates().zero_unsupported_findings is True
    assert ev.hard_gates().schema_validity_100pct is True


def test_real_extraction_is_perfect_over_the_covered_fields(real_s1_s6_evaluation) -> None:
    _dataset, ev = real_s1_s6_evaluation
    # MSA (9) + SOW (7) + INV-061 (15) + INV-066 (15) = 46 covered manifest fields.
    assert ev.extraction.covered == 46
    assert ev.extraction.correct == 46
    assert ev.extraction.accuracy_over_covered == 1.0


def test_real_partial_run_does_not_pass_all_gates_because_s4_absent(real_s1_s6_evaluation) -> None:
    _dataset, ev = real_s1_s6_evaluation
    # An S1/S6-only run never escalated S4 (it wasn't analyzed) -> gate 3 fails.
    assert ev.s4_present is False
    assert ev.hard_gates().s4_escalated is False
    assert ev.hard_gates().passed is False
