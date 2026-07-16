"""Invoice-level disposition precedence, including the hypothetical mixed
case no dataset scenario exercises (escalation gates the whole invoice)."""

from __future__ import annotations

from invoiceguardian.analyze import _invoice_disposition
from invoiceguardian.schemas.runtime import (
    ActionType,
    ExceptionFinding,
    ExceptionType,
    FindingDisposition,
    InvoiceDisposition,
    InvoiceLineEvidence,
)


def _finding(finding_type: ExceptionType, disposition: FindingDisposition) -> ExceptionFinding:
    return ExceptionFinding(
        finding_type=finding_type,
        basis="semantic" if disposition is FindingDisposition.ESCALATE else "deterministic",
        scope="line",
        invoice_line_id="L1",
        disposition=disposition,
        action=ActionType.HUMAN_REVIEW
        if disposition is FindingDisposition.ESCALATE
        else ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[InvoiceLineEvidence(document_id="INV-X", line_id="L1")],
    )


def test_no_findings_is_clean() -> None:
    assert _invoice_disposition([]) is InvoiceDisposition.CLEAN


def test_confident_exception_only_is_exceptions_found() -> None:
    findings = [_finding(ExceptionType.RATE_MISMATCH, FindingDisposition.AUTO_EXCEPTION)]
    assert _invoice_disposition(findings) is InvoiceDisposition.EXCEPTIONS_FOUND


def test_escalation_only_is_escalation_required() -> None:
    findings = [_finding(ExceptionType.SCOPE_AMBIGUITY, FindingDisposition.ESCALATE)]
    assert _invoice_disposition(findings) is InvoiceDisposition.ESCALATION_REQUIRED


def test_escalation_plus_confident_exception_is_escalation_required() -> None:
    # No v1 scenario mixes these; unresolved ambiguity gates the whole invoice.
    findings = [
        _finding(ExceptionType.RATE_MISMATCH, FindingDisposition.AUTO_EXCEPTION),
        _finding(ExceptionType.SCOPE_AMBIGUITY, FindingDisposition.ESCALATE),
    ]
    assert _invoice_disposition(findings) is InvoiceDisposition.ESCALATION_REQUIRED
