"""Deterministic finding assembly from a semantic classification.

These exercise `build_semantic_finding` directly with constructed
classifications and cached extractions — no model call. They pin down that
each of the three outcomes produces the evidence structure the answer key
requires, independent of what the model actually classifies at runtime.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from invoiceguardian.checks.semantic import NO_MATCH_STATEMENT, build_semantic_finding
from invoiceguardian.extraction.raw_schemas import RawSemanticClassification
from invoiceguardian.schemas.runtime import (
    ActionType,
    ContractTerms,
    ExceptionType,
    FindingDisposition,
    HourLimitEntry,
    InvoiceLine,
    MonthlyCap,
    RateCardEntry,
    ScopeClause,
    ServiceRole,
    SourceRef,
    StatementOfWork,
)

SCOPE_TEXT = (
    "Northbridge shall provide implementation support for Maplecore's ERP rollout, "
    "data migration validation, and training documentation."
)
AUTH_TEXT = (
    "Northbridge shall perform only those services described in an executed "
    "Statement of Work under this Agreement."
)
INVOICE_ID = "INV-2026-062"


def _contract() -> ContractTerms:
    return ContractTerms(
        document_id="MSA-2026-014",
        client_party="Maplecore Logistics Inc.",
        vendor_party="Northbridge Consulting Ltd.",
        effective_from=date(2026, 3, 1),
        effective_to=date(2027, 2, 28),
        currency="CAD",
        rate_card=[
            RateCardEntry(
                role=ServiceRole.SENIOR_CONSULTANT,
                rate_cad_per_hour=Decimal("150.00"),
                quote="Senior Consultant services shall be billed at CAD $150.00 per hour.",
                source=SourceRef(document_id="MSA-2026-014", section="4.1", page=2),
            )
        ],
        monthly_cap=MonthlyCap(
            value_cad=Decimal("25000.00"),
            quote="Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00.",
            source=SourceRef(document_id="MSA-2026-014", section="4.3", page=2),
        ),
        authorization_principle=ScopeClause(
            text=AUTH_TEXT,
            source=SourceRef(document_id="MSA-2026-014", section="2.1", page=1),
        ),
    )


def _sow() -> StatementOfWork:
    return StatementOfWork(
        document_id="SOW-2026-03",
        period_from=date(2026, 4, 1),
        period_to=date(2026, 9, 30),
        scope=ScopeClause(
            text=SCOPE_TEXT, source=SourceRef(document_id="SOW-2026-03", section="2", page=1)
        ),
        monthly_hour_limits=[
            HourLimitEntry(
                role=ServiceRole.SENIOR_CONSULTANT,
                max_hours_per_month=100,
                source=SourceRef(document_id="SOW-2026-03", section="3", page=1),
            ),
            HourLimitEntry(
                role=ServiceRole.PROJECT_MANAGER,
                max_hours_per_month=20,
                source=SourceRef(document_id="SOW-2026-03", section="3", page=1),
            ),
        ],
    )


def _line() -> InvoiceLine:
    return InvoiceLine(
        line_id="L1",
        description="Architecture Workshop Facilitation",
        hours=12,
        rate_cad=Decimal("150.00"),
        amount_cad=Decimal("1800.00"),
    )


def test_not_authorized_builds_absence_of_authorization_evidence() -> None:
    classification = RawSemanticClassification(classification="NOT_AUTHORIZED")
    finding, rule = build_semantic_finding(classification, _line(), INVOICE_ID, _contract(), _sow())

    assert finding is not None
    assert finding.finding_type == ExceptionType.UNAUTHORIZED_SERVICE
    assert finding.basis == "absence"
    assert finding.disposition == FindingDisposition.SEMANTIC_EXCEPTION
    assert finding.action == ActionType.DRAFT_VENDOR_CLARIFICATION
    assert rule.passed is False

    absence = next(e for e in finding.evidence if e.kind == "absence_of_authorization")
    searched = {(s.document_id, tuple(s.sections)) for s in absence.searched}
    assert searched == {("SOW-2026-03", ("2", "3")), ("MSA-2026-014", ("2.1",))}
    quotes = {(q.document_id, q.section, q.quote) for q in absence.quotes}
    assert ("SOW-2026-03", "2", SCOPE_TEXT) in quotes
    assert ("MSA-2026-014", "2.1", AUTH_TEXT) in quotes
    assert absence.statement == NO_MATCH_STATEMENT

    line_ref = next(e for e in finding.evidence if e.kind == "invoice_line")
    assert line_ref.document_id == INVOICE_ID
    assert line_ref.line_id == "L1"


def test_ambiguous_builds_scope_quote_and_line_reference() -> None:
    classification = RawSemanticClassification(classification="AMBIGUOUS")
    finding, rule = build_semantic_finding(classification, _line(), INVOICE_ID, _contract(), _sow())

    assert finding is not None
    assert finding.finding_type == ExceptionType.SCOPE_AMBIGUITY
    assert finding.basis == "semantic"
    assert finding.disposition == FindingDisposition.ESCALATE
    assert finding.action == ActionType.HUMAN_REVIEW
    assert rule.passed is False

    quote = next(e for e in finding.evidence if e.kind == "supporting_quote")
    assert quote.document_id == "SOW-2026-03"
    assert quote.section == "2"
    assert quote.quote == SCOPE_TEXT
    line_ref = next(e for e in finding.evidence if e.kind == "invoice_line")
    assert line_ref.line_id == "L1"


def test_equivalent_produces_no_finding_and_line_is_clean() -> None:
    classification = RawSemanticClassification(
        classification="EQUIVALENT", matched_authorized_item="Senior Consultant"
    )
    finding, rule = build_semantic_finding(classification, _line(), INVOICE_ID, _contract(), _sow())
    assert finding is None
    assert rule.passed is True
    assert "Senior Consultant" in (rule.detail or "")


@pytest.mark.parametrize("classification", ["NOT_AUTHORIZED", "AMBIGUOUS"])
def test_semantic_evidence_matches_answer_key_atoms_for_the_expected_scenarios(
    classification,
) -> None:
    """The assembled evidence must satisfy the evaluator's grounding for the
    scenario each outcome corresponds to (S2 / S4), so that WHEN the model
    classifies correctly the finding is fully grounded."""
    from invoiceguardian.dataset_generator.content import load_answer_keys
    from invoiceguardian.evaluation.grounding import grounding_for_pair

    dataset = load_answer_keys()
    scenario_id = "S2" if classification == "NOT_AUTHORIZED" else "S4"
    scenario = next(s for s in dataset.scenarios if s.scenario_id == scenario_id)
    line = InvoiceLine(
        line_id="L1",
        description=scenario.invoice_lines[0].description,
        hours=scenario.invoice_lines[0].hours,
        rate_cad=Decimal(scenario.invoice_lines[0].rate_cad),
        amount_cad=Decimal(scenario.invoice_lines[0].amount_cad),
    )
    finding, _rule = build_semantic_finding(
        RawSemanticClassification(classification=classification),
        line,
        scenario.invoice_id,
        _contract(),
        _sow(),
    )
    assert finding is not None
    assert grounding_for_pair(finding, scenario.expected_findings[0]).completeness == 1.0
