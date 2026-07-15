"""Runtime domain schemas for InvoiceGuardian.

These objects model pipeline state for a real analysis run (parse → extract →
normalize → check → match → finding → trace). They must never carry
answer-key fields (`expected_findings`, `difficulty`, `why_this_exists`,
`trap`, `scoring_note`, `confidence_expectation`) — ground truth lives only
in `schemas/evaluation.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ServiceRole",
    "ExceptionType",
    "FindingBasis",
    "FindingScope",
    "FindingDisposition",
    "InvoiceDisposition",
    "ActionType",
    "ApprovalState",
    "SourceRef",
    "RateCardEntry",
    "MonthlyCap",
    "HourLimitEntry",
    "ScopeClause",
    "ContractTerms",
    "StatementOfWork",
    "InvoiceLine",
    "Invoice",
    "SupportingQuoteEvidence",
    "InvoiceLineEvidence",
    "SearchedSection",
    "AbsenceQuote",
    "AbsenceOfAuthorizationEvidence",
    "ComputedTotalEvidence",
    "EvidenceReference",
    "ExceptionFinding",
    "DraftedAction",
    "OperationalTrace",
    "RunVersions",
    "ExtractedFactRecord",
    "DeterministicRuleResult",
    "ModelCallRecord",
    "AnalysisResult",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServiceRole(StrEnum):
    SENIOR_CONSULTANT = "SENIOR_CONSULTANT"
    CONSULTANT = "CONSULTANT"
    PROJECT_MANAGER = "PROJECT_MANAGER"


class ExceptionType(StrEnum):
    RATE_MISMATCH = "RATE_MISMATCH"
    UNAUTHORIZED_SERVICE = "UNAUTHORIZED_SERVICE"
    SCOPE_AMBIGUITY = "SCOPE_AMBIGUITY"
    AGGREGATE_CAP_EXCEEDED = "AGGREGATE_CAP_EXCEEDED"


FindingBasis = Literal["deterministic", "semantic", "absence"]
FindingScope = Literal["line", "invoice"]


class FindingDisposition(StrEnum):
    AUTO_EXCEPTION = "AUTO_EXCEPTION"
    SEMANTIC_EXCEPTION = "SEMANTIC_EXCEPTION"
    ESCALATE = "ESCALATE"


class InvoiceDisposition(StrEnum):
    CLEAN = "CLEAN"
    EXCEPTIONS_FOUND = "EXCEPTIONS_FOUND"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"


class ActionType(StrEnum):
    DRAFT_VENDOR_CLARIFICATION = "DRAFT_VENDOR_CLARIFICATION"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ApprovalState(StrEnum):
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# --- Shared source/evidence primitives -------------------------------------


class SourceRef(_Model):
    document_id: str
    section: str
    page: int


# --- Contract (MSA) ----------------------------------------------------------


class RateCardEntry(_Model):
    role: ServiceRole
    rate_cad_per_hour: Decimal
    source: SourceRef


class MonthlyCap(_Model):
    value_cad: Decimal
    source: SourceRef


class ScopeClause(_Model):
    text: str
    source: SourceRef


class ContractTerms(_Model):
    """The MSA, extracted once per session/arm and cached."""

    document_id: str
    client_party: str
    vendor_party: str
    effective_from: date
    effective_to: date
    currency: str
    rate_card: list[RateCardEntry]
    monthly_cap: MonthlyCap
    authorization_principle: ScopeClause


# --- Statement of Work ---------------------------------------------------


class HourLimitEntry(_Model):
    role: ServiceRole
    max_hours_per_month: int
    source: SourceRef


class StatementOfWork(_Model):
    """The SOW, extracted once per session/arm and cached."""

    document_id: str
    period_from: date
    period_to: date
    scope: ScopeClause
    monthly_hour_limits: list[HourLimitEntry]


# --- Invoice -----------------------------------------------------------------


class InvoiceLine(_Model):
    """`line_id` is deterministic parser metadata assigned from table rows;
    it is never model-extracted."""

    line_id: str
    description: str
    hours: int
    rate_cad: Decimal
    amount_cad: Decimal


class Invoice(_Model):
    invoice_id: str
    invoice_date: date
    service_period_start: date
    service_period_end: date
    sow_reference: str
    currency: str
    lines: list[InvoiceLine]
    total_cad: Decimal


# --- Evidence ------------------------------------------------------------


class SupportingQuoteEvidence(_Model):
    kind: Literal["supporting_quote"] = "supporting_quote"
    document_id: str
    section: str
    page: int
    quote: str


class InvoiceLineEvidence(_Model):
    kind: Literal["invoice_line"] = "invoice_line"
    document_id: str
    line_id: str


class SearchedSection(_Model):
    document_id: str
    sections: list[str]


class AbsenceQuote(_Model):
    document_id: str
    section: str
    page: int
    quote: str


class AbsenceOfAuthorizationEvidence(_Model):
    kind: Literal["absence_of_authorization"] = "absence_of_authorization"
    searched: list[SearchedSection]
    quotes: list[AbsenceQuote]
    statement: str


class ComputedTotalEvidence(_Model):
    kind: Literal["computed_total"] = "computed_total"
    document_id: str
    value_cad: Decimal


EvidenceReference = Annotated[
    SupportingQuoteEvidence
    | InvoiceLineEvidence
    | AbsenceOfAuthorizationEvidence
    | ComputedTotalEvidence,
    Field(discriminator="kind"),
]


# --- Findings and drafted actions -----------------------------------------


class ExceptionFinding(_Model):
    finding_type: ExceptionType
    basis: FindingBasis
    scope: FindingScope
    invoice_line_id: str | None
    disposition: FindingDisposition
    action: ActionType
    evidence: list[EvidenceReference]
    computed_values: dict[str, Decimal] | None = None


class DraftedAction(_Model):
    """A draft only — nothing is ever sent, filed, or paid by the system."""

    action_type: ActionType
    summary: str


# --- Operational trace (product requirement, spec section 7) ----------------


class RunVersions(_Model):
    dataset_version: str
    schema_version: str
    prompt_version: str


class ExtractedFactRecord(_Model):
    document_id: str
    field: str
    value: str
    source: SourceRef | None = None


class DeterministicRuleResult(_Model):
    rule_name: str
    invoice_line_id: str | None
    passed: bool
    detail: str | None = None


class ModelCallRecord(_Model):
    model_id: str
    effort: str | None
    purpose: str
    schema_valid: bool
    retried: bool = False


class OperationalTrace(_Model):
    """A render of pipeline state (inputs, extracted facts, rule results,
    model calls, evidence, decision state). Never chain-of-thought."""

    invoice_id: str
    versions: RunVersions
    input_document_ids: list[str]
    extracted_facts: list[ExtractedFactRecord]
    deterministic_rules: list[DeterministicRuleResult]
    model_calls: list[ModelCallRecord]
    findings: list[ExceptionFinding]
    disposition: InvoiceDisposition
    approval_state: ApprovalState


# --- Top-level analysis result -----------------------------------------------


class AnalysisResult(_Model):
    invoice_id: str
    disposition: InvoiceDisposition
    findings: list[ExceptionFinding]
    clean_line_ids: list[str]
    approval_state: ApprovalState
    drafted_action: DraftedAction | None
    trace: OperationalTrace
