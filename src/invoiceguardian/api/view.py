"""Projects AnalysisResult (the audit-trail-oriented domain object) into
view models shaped for the review UI.

`AnalysisResult` deliberately does not carry a structured `Invoice` snapshot
— line items live only inside `OperationalTrace.extracted_facts` as flat
key/value pairs (e.g. `"line[L1].description"`), which is also exactly what
the evaluator's manifest scoring depends on (SCORING.md). Rather than
parsing that field-naming convention in the frontend, this module — a
server-side presentation layer, not a runtime schema — reconstructs
structured line items and invoice header fields from the documented,
tested convention. It never mutates or duplicates domain logic; it only
reshapes data already produced by the pipeline for display.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from invoiceguardian.schemas.runtime import (
    AnalysisResult,
    ApprovalState,
    DraftedAction,
    EvidenceReference,
    ExceptionFinding,
    InvoiceDisposition,
    OperationalTrace,
)

# Presentation-only labels — not runtime or evaluation data, just a display
# convenience mapping this canned six-scenario demo's invoice IDs to the
# scenario numbers used throughout the spec and answer key.
SCENARIO_LABELS: dict[str, str] = {
    "INV-2026-061": "S1",
    "INV-2026-062": "S2",
    "INV-2026-063": "S3",
    "INV-2026-064": "S4",
    "INV-2026-065": "S5",
    "INV-2026-066": "S6",
}

_LINE_FIELD_RE = re.compile(r"^line\[(?P<line_id>[^\]]+)\]\.(?P<field>\w+)$")

LineStatus = Literal["clean", "flagged", "escalated"]
DecisionMode = Literal["deterministic check", "model-assisted match", "human review required"]


class InvoiceLineView(BaseModel):
    line_id: str
    description: str
    hours: int
    rate_cad: str
    amount_cad: str
    status: LineStatus


class ScenarioSummary(BaseModel):
    invoice_id: str
    scenario_label: str
    invoice_date: str
    service_period_start: str
    service_period_end: str
    sow_reference: str
    currency: str
    invoice_total_cad: str
    disposition: InvoiceDisposition


class ScenarioDetail(BaseModel):
    summary: ScenarioSummary
    lines: list[InvoiceLineView]
    invoice_level_findings: list[ExceptionFinding]
    findings: list[ExceptionFinding]
    approval_state: ApprovalState
    drafted_action: DraftedAction | None
    trace: OperationalTrace


def _facts_by_document(trace: OperationalTrace, document_id: str) -> dict[str, str]:
    return {
        fact.field: fact.value for fact in trace.extracted_facts if fact.document_id == document_id
    }


def decision_mode_for(finding: ExceptionFinding) -> DecisionMode:
    if finding.basis == "deterministic":
        return "deterministic check"
    if finding.disposition.value == "ESCALATE":
        return "human review required"
    return "model-assisted match"  # basis: semantic / absence, confident dispositions


def _line_status(
    line_id: str, findings: list[ExceptionFinding], clean_line_ids: list[str]
) -> LineStatus:
    if line_id in clean_line_ids:
        return "clean"
    for finding in findings:
        if finding.invoice_line_id == line_id:
            return "escalated" if finding.disposition.value == "ESCALATE" else "flagged"
    return "clean"


def build_scenario_summary(result: AnalysisResult) -> ScenarioSummary:
    facts = _facts_by_document(result.trace, result.invoice_id)
    return ScenarioSummary(
        invoice_id=result.invoice_id,
        scenario_label=SCENARIO_LABELS.get(result.invoice_id, result.invoice_id),
        invoice_date=facts["invoice_date"],
        service_period_start=facts["service_period_start"],
        service_period_end=facts["service_period_end"],
        sow_reference=facts["sow_reference"],
        currency=facts["currency"],
        invoice_total_cad=facts["invoice_total_cad"],
        disposition=result.disposition,
    )


def build_scenario_detail(result: AnalysisResult) -> ScenarioDetail:
    facts = _facts_by_document(result.trace, result.invoice_id)

    line_fields: dict[str, dict[str, str]] = {}
    for field_key, value in facts.items():
        match = _LINE_FIELD_RE.match(field_key)
        if match:
            line_fields.setdefault(match["line_id"], {})[match["field"]] = value

    def _sort_key(line_id: str) -> int:
        digits = "".join(ch for ch in line_id if ch.isdigit())
        return int(digits) if digits else 0

    lines = [
        InvoiceLineView(
            line_id=line_id,
            description=values["description"],
            hours=int(values["hours"]),
            rate_cad=values["rate_cad"],
            amount_cad=values["amount_cad"],
            status=_line_status(line_id, result.findings, result.clean_line_ids),
        )
        for line_id, values in sorted(line_fields.items(), key=lambda item: _sort_key(item[0]))
    ]

    invoice_level_findings = [f for f in result.findings if f.scope == "invoice"]

    return ScenarioDetail(
        summary=build_scenario_summary(result),
        lines=lines,
        invoice_level_findings=invoice_level_findings,
        findings=result.findings,
        approval_state=result.approval_state,
        drafted_action=result.drafted_action,
        trace=result.trace,
    )


def evidence_kind(evidence: EvidenceReference) -> str:
    return evidence.kind


def scope_line_text() -> str:
    return (
        "Reviews invoice consistency against supplied contracts. Never decides payment, "
        "never determines fraud. All actions are drafts requiring human approval."
    )


def disposition_badge_variant(disposition: InvoiceDisposition) -> str:
    return {
        InvoiceDisposition.CLEAN: "clean",
        InvoiceDisposition.EXCEPTIONS_FOUND: "exceptions",
        InvoiceDisposition.ESCALATION_REQUIRED: "escalation",
    }[disposition]
