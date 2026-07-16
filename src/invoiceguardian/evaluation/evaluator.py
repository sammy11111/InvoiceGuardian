"""The evaluator: metric families, hard gates, and the weighted score,
preregistered in SCORING.md.

Interpretation notes, made explicit because they are load-bearing:

1. Abstention scenarios (disposition ESCALATE — S4 on v1.3, plus S7 if the
   v1.4 branch lands) are "excluded from detection metrics and scored solely
   under abstention." They contribute to no weighted metric except
   abstention: excluded from detection precision/recall, disposition
   accuracy, false-positive counting, value accuracy, AND grounding. They
   remain subject to hard gate 1 (no unsupported / fabricated evidence) and
   hard gate 3 (every abstention scenario must escalate).

2. Hard gate 2 (schema validity) and first-pass validity are scored over the
   preregistered required operations only (MSA + SOW extraction, one per
   invoice, and the three semantic ops). Any additional model call is logged
   as an extra operation and "never alters the preregistered denominator."
   Only 8 of the frozen 11 operations exist until the semantic checks are
   built (step 6); the gate asserts 100% of the required ops a run performed
   were schema-valid within one retry, not that the count is 11 yet.

3. Detection recall's denominator is fixed at the dataset's planted-exception
   count (3 non-abstention expected findings on v1.3, i.e. ÷ 3). A scenario
   with no AnalysisResult in the run has its expected findings counted as
   false negatives (its predictions are simply empty), never skipped — a run
   missing S2 scores recall 2/3, not 2/2.

4. Grounding completeness is macro-averaged: each matched finding's own
   correct/required atom ratio, averaged over matched findings. Hard gate 1
   for a matched finding uses the answer key's required atoms (so a
   RATE_MISMATCH citing the monthly-cap clause fails); an unmatched predicted
   finding is checked only for fabrication (gate 4 already scores it as a
   false positive).

5. Latency: per-invoice latencies are pooled across replicates into a single
   median (not a median of per-run medians). Full latency credit when no
   latency data is present is DEV-ONLY convenience — a formal benchmark run
   MUST carry per-invoice latency covering extraction plus the semantic ops
   (wired in step 9), or the latency component is not trustworthy.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from invoiceguardian.evaluation.grounding import (
    grounding_for_pair,
    has_fabricated_citation,
    matched_finding_is_supported,
)
from invoiceguardian.evaluation.manifest import ExtractionScore, score_extraction
from invoiceguardian.evaluation.matching import MatchedPair, ScenarioMatch, match_scenario
from invoiceguardian.schemas.evaluation import (
    BenchmarkRun,
    EvaluationDataset,
    HardGateResults,
    MetricSummary,
    ScenarioAnswerKey,
)
from invoiceguardian.schemas.runtime import AnalysisResult, FindingDisposition

AbstentionOutcome = str  # "correct" | "incorrect_confident" | "miss"

# The preregistered required operations (SCORING.md): MSA + SOW extraction,
# one extraction per invoice, and the three semantic-comparison operations.
_REQUIRED_OP_EXACT = frozenset({"MSA_EXTRACTION", "SOW_EXTRACTION"})
_REQUIRED_OP_PREFIXES = ("INVOICE_EXTRACTION", "SEMANTIC_")
# Per-invoice (incremental) operations, for latency accounting. Step 9 must
# ensure this covers extraction AND the semantic ops, not just extraction.
_INVOICE_OP_PREFIXES = ("INVOICE_EXTRACTION", "SEMANTIC_")

_WEIGHTS = {
    "recall": 0.40,
    "grounding": 0.30,
    "extraction": 0.20,
    "first_pass_schema_validity": 0.05,
    "normalized_latency": 0.05,
}


def is_required_operation(operation: str) -> bool:
    return operation in _REQUIRED_OP_EXACT or operation.startswith(_REQUIRED_OP_PREFIXES)


def _is_invoice_operation(operation: str) -> bool:
    return operation.startswith(_INVOICE_OP_PREFIXES)


def _is_abstention_scenario(scenario: ScenarioAnswerKey) -> bool:
    return any(f.expected_disposition == "ESCALATE" for f in scenario.expected_findings)


def _scenario_abstention(match: ScenarioMatch, result: AnalysisResult | None) -> AbstentionOutcome:
    """Abstention outcome for one escalation scenario. A confident exception
    anywhere on the invoice dominates; otherwise "correct" requires an
    ESCALATE-disposition finding that key-matched the expected finding."""
    findings = result.findings if result is not None else []
    dispositions = {f.disposition for f in findings}
    if dispositions & {FindingDisposition.AUTO_EXCEPTION, FindingDisposition.SEMANTIC_EXCEPTION}:
        return "incorrect_confident"
    if any(pair.predicted.disposition is FindingDisposition.ESCALATE for pair in match.matched):
        return "correct"
    return "miss"


def _invoice_latencies_ms(run: BenchmarkRun) -> list[float]:
    return [
        entry.latency_ms
        for entry in run.model_call_log
        if _is_invoice_operation(entry.operation) and entry.latency_ms > 0
    ]


def _decimal_equal(a: str | Decimal, b: str | Decimal) -> bool:
    try:
        cents = Decimal("0.01")
        return Decimal(a).quantize(cents) == Decimal(b).quantize(cents)
    except InvalidOperation:
        return False


def _value_tally(pair: MatchedPair) -> tuple[int, int]:
    """(correct, total) observational value-accuracy tally for one matched
    finding: predicted computed_values vs the answer key's expected_values."""
    expected_values = pair.expected.expected_values
    if not expected_values:
        return 0, 0
    predicted = pair.predicted.computed_values or {}
    correct = 0
    for key, expected in expected_values.items():
        got = predicted.get(key)
        if got is not None and _decimal_equal(got, expected):
            correct += 1
    return correct, len(expected_values)


@dataclass(frozen=True)
class RunEvaluation:
    run_id: str
    detection_true_positives: int
    detection_false_positives: int
    detection_false_negatives: int
    planted_exceptions: int
    matched_disposition_correct: int
    matched_disposition_total: int
    grounding_completeness: float
    abstention: AbstentionOutcome
    s4_present: bool
    extraction: ExtractionScore
    first_pass_valid_ops: int
    total_ops: int
    unsupported_finding_count: int
    all_ops_schema_valid: bool
    value_correct: int
    value_total: int
    invoice_latencies_ms: tuple[float, ...]
    scenario_matches: tuple[ScenarioMatch, ...] = field(default_factory=tuple)

    @property
    def detection_precision(self) -> float:
        predicted = self.detection_true_positives + self.detection_false_positives
        if predicted == 0:
            # Zero-prediction convention: reporting no exceptions where the
            # dataset expects some is precision 0, not undefined.
            return 0.0 if self.planted_exceptions > 0 else 1.0
        return self.detection_true_positives / predicted

    @property
    def detection_recall(self) -> float:
        return (
            self.detection_true_positives / self.planted_exceptions
            if self.planted_exceptions
            else 0.0
        )

    @property
    def disposition_accuracy(self) -> float:
        if self.matched_disposition_total == 0:
            return 1.0
        return self.matched_disposition_correct / self.matched_disposition_total

    @property
    def value_accuracy(self) -> float:
        return self.value_correct / self.value_total if self.value_total else 1.0

    def hard_gates(self) -> HardGateResults:
        zero_unsupported = self.unsupported_finding_count == 0
        schema_valid = self.all_ops_schema_valid
        s4_ok = self.s4_present and self.abstention == "correct"
        zero_fp = self.detection_false_positives == 0
        return HardGateResults(
            zero_unsupported_findings=zero_unsupported,
            schema_validity_100pct=schema_valid,
            s4_escalated=s4_ok,
            zero_false_positives=zero_fp,
            passed=zero_unsupported and schema_valid and s4_ok and zero_fp,
        )


def evaluate_run(dataset: EvaluationDataset, run: BenchmarkRun) -> RunEvaluation:
    results_by_invoice = {r.invoice_id: r for r in run.analysis_results}

    # Match every scenario (a missing AnalysisResult means empty predictions,
    # so its expected findings fall through to false negatives).
    matches: dict[str, ScenarioMatch] = {}
    for scenario in dataset.scenarios:
        result = results_by_invoice.get(scenario.invoice_id)
        predicted = result.findings if result is not None else []
        matches[scenario.scenario_id] = match_scenario(
            scenario.scenario_id, scenario.invoice_id, predicted, scenario.expected_findings
        )

    tp = fp = fn = 0
    disp_correct = disp_total = 0
    grounding_ratios: list[float] = []
    value_correct = value_total = 0
    planted = 0

    for scenario in dataset.scenarios:
        if _is_abstention_scenario(scenario):
            continue  # scored solely under abstention
        planted += len(scenario.expected_findings)  # fixed denominator (÷3 on v1.3)
        match = matches[scenario.scenario_id]
        tp += len(match.matched)
        fp += len(match.false_positives)
        fn += len(match.false_negatives)
        for pair in match.matched:
            disp_total += 1
            if pair.predicted.disposition.value == pair.expected.expected_disposition:
                disp_correct += 1
            grounding_ratios.append(grounding_for_pair(pair.predicted, pair.expected).completeness)
            correct, total = _value_tally(pair)
            value_correct += correct
            value_total += total

    # Hard gate 1 (zero unsupported) covers every predicted finding, including
    # abstention scenarios: matched findings must satisfy the answer key's
    # required atoms; unmatched findings must merely carry no fabricated quote.
    unsupported = 0
    for scenario in dataset.scenarios:
        match = matches[scenario.scenario_id]
        for pair in match.matched:
            if not matched_finding_is_supported(pair.predicted, pair.expected):
                unsupported += 1
        for finding in match.false_positives:
            if has_fabricated_citation(finding):
                unsupported += 1

    # Abstention: every escalation scenario must be correct.
    abstention_scenarios = [s for s in dataset.scenarios if _is_abstention_scenario(s)]
    abstention_present = False
    outcomes: list[AbstentionOutcome] = []
    for scenario in abstention_scenarios:
        result = results_by_invoice.get(scenario.invoice_id)
        if result is not None:
            abstention_present = True
        outcomes.append(_scenario_abstention(matches[scenario.scenario_id], result))
    abstention: AbstentionOutcome = (
        "correct"
        if outcomes and all(o == "correct" for o in outcomes)
        else next((o for o in outcomes if o != "correct"), "miss")
    )

    extraction = score_extraction(dataset, run.analysis_results)
    required_ops = [e for e in run.model_call_log if is_required_operation(e.operation)]
    first_pass_valid = sum(1 for e in required_ops if e.schema_valid_first_pass)
    total_ops = len(required_ops)
    all_valid = total_ops > 0 and all(e.schema_valid_final for e in required_ops)

    grounding_completeness = (
        sum(grounding_ratios) / len(grounding_ratios) if grounding_ratios else 1.0
    )

    return RunEvaluation(
        run_id=run.run_id,
        detection_true_positives=tp,
        detection_false_positives=fp,
        detection_false_negatives=fn,
        planted_exceptions=planted,
        matched_disposition_correct=disp_correct,
        matched_disposition_total=disp_total,
        grounding_completeness=grounding_completeness,
        abstention=abstention,
        s4_present=abstention_present,
        extraction=extraction,
        first_pass_valid_ops=first_pass_valid,
        total_ops=total_ops,
        unsupported_finding_count=unsupported,
        all_ops_schema_valid=all_valid,
        value_correct=value_correct,
        value_total=value_total,
        invoice_latencies_ms=tuple(_invoice_latencies_ms(run)),
        scenario_matches=tuple(matches.values()),
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _range(values: list[float]) -> list[float]:
    return [min(values), max(values)] if values else [0.0, 0.0]


def _pooled_latency_median(runs: list[BenchmarkRun]) -> float | None:
    pooled = [latency for run in runs for latency in _invoice_latencies_ms(run)]
    return statistics.median(pooled) if pooled else None


def summarize_arm(
    dataset: EvaluationDataset,
    arm_label: str,
    runs: list[BenchmarkRun],
    *,
    latency_reference_ms: float | None = None,
) -> MetricSummary:
    """Aggregates replicate runs for a single arm into a MetricSummary.

    Hard gates must pass in every replicate. Weighted metrics are averaged and
    the observed range recorded. Per-invoice latencies are pooled across all
    replicates into one median. `latency_reference_ms` is the fastest passing
    arm's pooled median (supplied by `summarize_arms`); without it a lone arm
    normalizes to 100.
    """
    evaluations = [evaluate_run(dataset, run) for run in runs]

    recalls = [e.detection_recall for e in evaluations]
    precisions = [e.detection_precision for e in evaluations]
    dispositions = [e.disposition_accuracy for e in evaluations]
    groundings = [e.grounding_completeness for e in evaluations]
    extractions = [e.extraction.accuracy_over_manifest for e in evaluations]
    values = [e.value_accuracy for e in evaluations]
    first_passes = [
        e.first_pass_valid_ops / e.total_ops if e.total_ops else 0.0 for e in evaluations
    ]

    per_gate = [e.hard_gates() for e in evaluations]
    gates = HardGateResults(
        zero_unsupported_findings=all(g.zero_unsupported_findings for g in per_gate),
        schema_validity_100pct=all(g.schema_validity_100pct for g in per_gate),
        s4_escalated=all(g.s4_escalated for g in per_gate),
        zero_false_positives=all(g.zero_false_positives for g in per_gate),
        passed=all(g.passed for g in per_gate),
    )

    outcomes = [e.abstention for e in evaluations]
    abstention = (
        "correct"
        if all(a == "correct" for a in outcomes)
        else next(a for a in outcomes if a != "correct")
    )

    arm_median = _pooled_latency_median(runs)
    normalized_latency: float | None
    if arm_median is None or arm_median <= 0:
        normalized_latency = None
    else:
        reference = latency_reference_ms if latency_reference_ms is not None else arm_median
        normalized_latency = min(100.0, 100.0 * reference / arm_median)

    mean_recall = _mean(recalls)
    mean_grounding = _mean(groundings)
    mean_extraction = _mean(extractions)
    mean_first_pass = _mean(first_passes)

    weighted_score: float | None = None
    if gates.passed:
        # DEV-ONLY: absent latency data yields full latency credit. A formal
        # run must carry per-invoice latency (see module docstring note 5).
        latency_component = (normalized_latency / 100.0) if normalized_latency is not None else 1.0
        weighted_score = (
            _WEIGHTS["recall"] * mean_recall
            + _WEIGHTS["grounding"] * mean_grounding
            + _WEIGHTS["extraction"] * mean_extraction
            + _WEIGHTS["first_pass_schema_validity"] * mean_first_pass
            + _WEIGHTS["normalized_latency"] * latency_component
        )

    return MetricSummary(
        arm_label=arm_label,
        run_ids=[run.run_id for run in runs],
        detection_precision=_mean(precisions),
        detection_recall=mean_recall,
        disposition_accuracy=_mean(dispositions),
        grounding_completeness=mean_grounding,
        abstention_correctness=abstention,  # type: ignore[arg-type]
        extraction_accuracy=mean_extraction,
        first_pass_schema_validity=mean_first_pass,
        normalized_latency=normalized_latency,
        weighted_score=weighted_score,
        hard_gates=gates,
        value_accuracy=_mean(values),
        replicate_range={
            "detection_recall": _range(recalls),
            "detection_precision": _range(precisions),
            "grounding_completeness": _range(groundings),
            "extraction_accuracy": _range(extractions),
            "first_pass_schema_validity": _range(first_passes),
        },
    )


def summarize_arms(
    dataset: EvaluationDataset, arms: dict[str, list[BenchmarkRun]]
) -> list[MetricSummary]:
    """Scores multiple arms, normalizing latency against the fastest passing
    arm's pooled median (SCORING.md's latency formula)."""
    prelim = {label: summarize_arm(dataset, label, runs) for label, runs in arms.items()}

    passing_medians = [
        median
        for label, runs in arms.items()
        if prelim[label].hard_gates.passed
        for median in [_pooled_latency_median(runs)]
        if median is not None
    ]
    reference = min(passing_medians) if passing_medians else None

    return [
        summarize_arm(dataset, label, runs, latency_reference_ms=reference)
        for label, runs in arms.items()
    ]
