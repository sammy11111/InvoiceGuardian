"""Evaluation schemas for InvoiceGuardian.

These objects mirror `answer_keys.json` and the benchmark protocol in
`SCORING.md`. They alone may carry ground-truth / answer-key fields
(`expected_findings`, `difficulty`, `why_this_exists`, `trap`, `scoring_note`,
`confidence_expectation`). This module may import runtime schemas (a
predicted result is a real pipeline output); runtime schemas must never
import this module.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from invoiceguardian.schemas.runtime import AnalysisResult

__all__ = [
    "DocumentMeta",
    "ExpectedSource",
    "ExpectedRateCardEntry",
    "ExpectedMonetaryWithSource",
    "ExpectedHourLimitEntry",
    "ExpectedExtractions",
    "ExpectedInvoiceLine",
    "ExpectedSupportingQuote",
    "ExpectedInvoiceLineRef",
    "ExpectedSearchedSection",
    "ExpectedAbsenceQuote",
    "ExpectedAbsenceOfAuthorization",
    "ExpectedComputedTotal",
    "ExpectedEvidence",
    "ExpectedFinding",
    "ScenarioAnswerKey",
    "ExtractionManifestEntry",
    "NormalizationRules",
    "EvaluationDataset",
    "ModelConfig",
    "ModelCallLogEntry",
    "BenchmarkRun",
    "HardGateResults",
    "MetricSummary",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


Difficulty = Literal["easy", "medium", "hard"]
InvoiceDispositionKey = Literal["CLEAN", "EXCEPTIONS_FOUND", "ESCALATION_REQUIRED"]
FindingBasisKey = Literal["deterministic", "semantic", "absence"]
FindingScopeKey = Literal["line", "invoice"]
DispositionKey = Literal["AUTO_EXCEPTION", "SEMANTIC_EXCEPTION", "ESCALATE"]
ActionKey = Literal["DRAFT_VENDOR_CLARIFICATION", "HUMAN_REVIEW"]
ConfidenceExpectation = Literal["HIGH", "MEDIUM", "ABSTAIN"]


# --- Shared documents / expected_extractions (answer_keys.json top matter) --


class DocumentMeta(_Model):
    type: Literal["contract", "sow"]
    parties: list[str] | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    period_from: date | None = None
    period_to: date | None = None


class ExpectedSource(_Model):
    document_id: str
    section: str
    page: int


class ExpectedRateCardEntry(_Model):
    role: str
    rate_cad_per_hour: str
    source: ExpectedSource


class ExpectedMonetaryWithSource(_Model):
    value: str
    source: ExpectedSource


class ExpectedHourLimitEntry(_Model):
    role: str
    max_hours_per_month: int
    source: ExpectedSource


class ExpectedExtractions(_Model):
    rate_card: list[ExpectedRateCardEntry]
    monthly_cap_cad: ExpectedMonetaryWithSource
    sow_monthly_hour_limits: list[ExpectedHourLimitEntry]


# --- Expected evidence (answer-key mirror of runtime EvidenceReference) -----


class ExpectedSupportingQuote(_Model):
    kind: Literal["supporting_quote"] = "supporting_quote"
    document_id: str
    section: str
    page: int
    quote: str


class ExpectedInvoiceLineRef(_Model):
    kind: Literal["invoice_line"] = "invoice_line"
    document_id: str
    line_id: str


class ExpectedSearchedSection(_Model):
    document_id: str
    sections: list[str]


class ExpectedAbsenceQuote(_Model):
    document_id: str
    section: str
    page: int
    quote: str


class ExpectedAbsenceOfAuthorization(_Model):
    kind: Literal["absence_of_authorization"] = "absence_of_authorization"
    searched: list[ExpectedSearchedSection]
    quotes: list[ExpectedAbsenceQuote]
    statement: str


class ExpectedComputedTotal(_Model):
    kind: Literal["computed_total"] = "computed_total"
    document_id: str
    value_cad: str


ExpectedEvidence = Annotated[
    ExpectedSupportingQuote
    | ExpectedInvoiceLineRef
    | ExpectedAbsenceOfAuthorization
    | ExpectedComputedTotal,
    Field(discriminator="kind"),
]


# --- Expected findings and scenario answer keys ------------------------------


class ExpectedFinding(_Model):
    finding_type: str
    basis: FindingBasisKey
    scope: FindingScopeKey
    invoice_line_id: str | None
    expected_disposition: DispositionKey
    expected_action: ActionKey
    confidence_expectation: ConfidenceExpectation
    evidence: list[ExpectedEvidence]
    expected_values: dict[str, str] | None = None
    scoring_note: str | None = None
    rationale: str | None = None


class ExpectedInvoiceLine(_Model):
    line_id: str
    description: str
    hours: int
    rate_cad: str
    amount_cad: str


class ScenarioAnswerKey(_Model):
    scenario_id: str
    invoice_id: str
    difficulty: Difficulty
    why_this_exists: str
    invoice_lines: list[ExpectedInvoiceLine]
    expected_findings: list[ExpectedFinding]
    expected_clean_line_ids: list[str]
    expected_invoice_disposition: InvoiceDispositionKey
    invoice_date: date
    service_period_start: date
    service_period_end: date
    sow_reference: str
    currency: str
    invoice_total_cad: str
    trap: str | None = None
    notes: str | None = None


# --- Extraction manifest ------------------------------------------------


class ExtractionManifestEntry(_Model):
    document_id: str
    field: str
    expected: str | int
    normalization: str


class NormalizationRules(_Model):
    iso_date: str
    decimal_2dp: str
    iso_currency: str
    integer: str
    identifier_trim: str
    whitespace_collapse: str
    whitespace_collapse_exact: str
    role_enum: dict[str, str]
    semantic_equivalence_note: str


class EvaluationDataset(_Model):
    """Direct mirror of `answer_keys.json`."""

    schema_version: str
    dataset_version: str
    note: str
    documents: dict[str, DocumentMeta]
    expected_extractions: ExpectedExtractions
    scenarios: list[ScenarioAnswerKey]
    extraction_manifest: list[ExtractionManifestEntry]
    extraction_field_count: int
    normalization_rules: NormalizationRules
    state: str
    lifecycle: str


# --- Benchmark run log (SCORING.md "per-run log") ----------------------------


class ModelConfig(_Model):
    model_id: str
    effort: str | None
    thinking_mode: str | None
    temperature: float | None


class ModelCallLogEntry(_Model):
    operation: str
    schema_valid_first_pass: bool
    # The client structurally enforces one retry maximum (SCORING.md); this
    # records the actual count (0 or 1) for bookkeeping fidelity.
    retry_count: int
    schema_valid_final: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int


class BenchmarkRun(_Model):
    run_id: str
    phase: Literal["A", "B"]
    arm_label: str
    model: ModelConfig
    prompt_version: str
    prompt_hash: str
    dataset_version: str
    answer_key_schema_version: str
    replicate_index: int
    timestamp: datetime
    analysis_results: list[AnalysisResult]
    model_call_log: list[ModelCallLogEntry]
    excluded: bool = False
    exclusion_reason: str | None = None


# --- Metric summary (SCORING.md metric families + hard gates + weighted score)


class HardGateResults(_Model):
    zero_unsupported_findings: bool
    schema_validity_100pct: bool
    s4_escalated: bool
    zero_false_positives: bool
    passed: bool


class MetricSummary(_Model):
    arm_label: str
    run_ids: list[str]
    detection_precision: float
    detection_recall: float
    disposition_accuracy: float
    grounding_completeness: float
    abstention_correctness: Literal["correct", "incorrect_confident", "miss"]
    extraction_accuracy: float
    first_pass_schema_validity: float
    normalized_latency: float | None
    weighted_score: float | None
    hard_gates: HardGateResults
    value_accuracy: float  # observational: matched findings' computed_values vs expected_values
    replicate_range: dict[str, list[float]] | None = None
