"""Deterministic finding assembly from a semantic classification.

Given the model's bounded classification (EQUIVALENT / NOT_AUTHORIZED /
AMBIGUOUS) for one unresolved line, ordinary code builds the finding, sets
the disposition, and assembles the evidence from the cached typed
extractions. The model supplies the classification only; it never writes
evidence structures.
"""

from __future__ import annotations

from invoiceguardian.extraction.raw_schemas import RawSemanticClassification
from invoiceguardian.schemas.runtime import (
    AbsenceOfAuthorizationEvidence,
    AbsenceQuote,
    ActionType,
    ContractTerms,
    DeterministicRuleResult,
    ExceptionFinding,
    ExceptionType,
    FindingDisposition,
    InvoiceLine,
    InvoiceLineEvidence,
    SearchedSection,
    StatementOfWork,
    SupportingQuoteEvidence,
)

SEMANTIC_COMPARISON_CHECK = "SEMANTIC_COMPARISON_CHECK"

NO_MATCH_STATEMENT = "No authorization matching this line item was found in the searched documents."


def _searched_sections(contract: ContractTerms, sow: StatementOfWork) -> list[SearchedSection]:
    """The SOW scope (§2) and role (§3) sections plus the MSA authorization
    principle (§2.1) — the documents/sections actually consulted."""
    sow_sections = {sow.scope.source.section}
    sow_sections.update(entry.source.section for entry in sow.monthly_hour_limits)
    return [
        SearchedSection(document_id=sow.document_id, sections=sorted(sow_sections)),
        SearchedSection(
            document_id=contract.document_id,
            sections=[contract.authorization_principle.source.section],
        ),
    ]


def _unauthorized_finding(
    line: InvoiceLine, invoice_id: str, contract: ContractTerms, sow: StatementOfWork
) -> ExceptionFinding:
    return ExceptionFinding(
        finding_type=ExceptionType.UNAUTHORIZED_SERVICE,
        basis="absence",
        scope="line",
        invoice_line_id=line.line_id,
        disposition=FindingDisposition.SEMANTIC_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            AbsenceOfAuthorizationEvidence(
                searched=_searched_sections(contract, sow),
                quotes=[
                    AbsenceQuote(
                        document_id=sow.document_id,
                        section=sow.scope.source.section,
                        page=sow.scope.source.page,
                        quote=sow.scope.text,
                    ),
                    AbsenceQuote(
                        document_id=contract.document_id,
                        section=contract.authorization_principle.source.section,
                        page=contract.authorization_principle.source.page,
                        quote=contract.authorization_principle.text,
                    ),
                ],
                statement=NO_MATCH_STATEMENT,
            ),
            InvoiceLineEvidence(document_id=invoice_id, line_id=line.line_id),
        ],
    )


def _ambiguous_finding(
    line: InvoiceLine, invoice_id: str, sow: StatementOfWork
) -> ExceptionFinding:
    return ExceptionFinding(
        finding_type=ExceptionType.SCOPE_AMBIGUITY,
        basis="semantic",
        scope="line",
        invoice_line_id=line.line_id,
        disposition=FindingDisposition.ESCALATE,
        action=ActionType.HUMAN_REVIEW,
        evidence=[
            SupportingQuoteEvidence(
                document_id=sow.document_id,
                section=sow.scope.source.section,
                page=sow.scope.source.page,
                quote=sow.scope.text,
            ),
            InvoiceLineEvidence(document_id=invoice_id, line_id=line.line_id),
        ],
    )


def build_semantic_finding(
    classification: RawSemanticClassification,
    line: InvoiceLine,
    invoice_id: str,
    contract: ContractTerms,
    sow: StatementOfWork,
) -> tuple[ExceptionFinding | None, DeterministicRuleResult]:
    """Maps a bounded classification to a finding (or None when the line is
    authorized-equivalent and therefore clean)."""
    detail = classification.classification
    if classification.matched_authorized_item:
        detail = f"{detail} -> {classification.matched_authorized_item}"
    rule = DeterministicRuleResult(
        rule_name=SEMANTIC_COMPARISON_CHECK,
        invoice_line_id=line.line_id,
        passed=classification.classification == "EQUIVALENT",
        detail=detail,
    )

    match classification.classification:
        case "EQUIVALENT":
            return None, rule
        case "NOT_AUTHORIZED":
            return _unauthorized_finding(line, invoice_id, contract, sow), rule
        case "AMBIGUOUS":
            return _ambiguous_finding(line, invoice_id, sow), rule
