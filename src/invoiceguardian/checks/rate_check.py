"""S1: deterministic rate-mismatch check.

Ordinary Python, no model call: for each invoice line whose role resolves
via an exact-prefix match, compares the billed rate to the contract's rate
card for that role. Lines whose description doesn't exactly match a known
role label are left unresolved (out of scope for this check — S5's
aggregate cap and S2/S3/S4's semantic paths are separate build steps).
"""

from __future__ import annotations

from invoiceguardian.checks.role_matching import match_role_exact
from invoiceguardian.schemas.runtime import (
    ActionType,
    ContractTerms,
    DeterministicRuleResult,
    ExceptionFinding,
    ExceptionType,
    FindingDisposition,
    Invoice,
    InvoiceLineEvidence,
    SupportingQuoteEvidence,
)

RATE_MISMATCH_CHECK = "RATE_MISMATCH_CHECK"


def check_rate_mismatches(
    invoice: Invoice, contract: ContractTerms
) -> tuple[list[ExceptionFinding], list[DeterministicRuleResult]]:
    rate_by_role = {entry.role: entry for entry in contract.rate_card}
    findings: list[ExceptionFinding] = []
    rule_results: list[DeterministicRuleResult] = []

    for line in invoice.lines:
        role = match_role_exact(line.description)
        if role is None:
            continue
        rate_entry = rate_by_role.get(role)
        if rate_entry is None:
            continue

        if line.rate_cad == rate_entry.rate_cad_per_hour:
            rule_results.append(
                DeterministicRuleResult(
                    rule_name=RATE_MISMATCH_CHECK,
                    invoice_line_id=line.line_id,
                    passed=True,
                    detail=f"billed {line.rate_cad} == contract {rate_entry.rate_cad_per_hour}",
                )
            )
            continue

        rule_results.append(
            DeterministicRuleResult(
                rule_name=RATE_MISMATCH_CHECK,
                invoice_line_id=line.line_id,
                passed=False,
                detail=f"billed {line.rate_cad} != contract {rate_entry.rate_cad_per_hour}",
            )
        )
        findings.append(
            ExceptionFinding(
                finding_type=ExceptionType.RATE_MISMATCH,
                basis="deterministic",
                scope="line",
                invoice_line_id=line.line_id,
                disposition=FindingDisposition.AUTO_EXCEPTION,
                action=ActionType.DRAFT_VENDOR_CLARIFICATION,
                evidence=[
                    SupportingQuoteEvidence(
                        document_id=rate_entry.source.document_id,
                        section=rate_entry.source.section,
                        page=rate_entry.source.page,
                        quote=rate_entry.quote,
                    ),
                    InvoiceLineEvidence(document_id=invoice.invoice_id, line_id=line.line_id),
                ],
                computed_values={
                    "billed_rate_cad": line.rate_cad,
                    "authorized_rate_cad": rate_entry.rate_cad_per_hour,
                },
            )
        )

    return findings, rule_results
