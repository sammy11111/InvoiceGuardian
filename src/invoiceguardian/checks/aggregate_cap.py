"""S5: aggregate monthly-cap check (deterministic, no model call).

Ordinary Python: sums the invoice's line amounts and compares the total to
the MSA §4.3 monthly cap. Every line can be individually valid (correct
rate, within hour limits) while the aggregate still breaches the cap — that
is exactly what S5 tests, so this check is invoice-scoped and leaves the
individual lines untouched (they remain clean).
"""

from __future__ import annotations

from decimal import Decimal

from invoiceguardian.schemas.runtime import (
    ActionType,
    ComputedTotalEvidence,
    ContractTerms,
    DeterministicRuleResult,
    ExceptionFinding,
    ExceptionType,
    FindingDisposition,
    Invoice,
    SupportingQuoteEvidence,
)

AGGREGATE_CAP_CHECK = "AGGREGATE_CAP_CHECK"


def check_aggregate_cap(
    invoice: Invoice, contract: ContractTerms
) -> tuple[list[ExceptionFinding], list[DeterministicRuleResult]]:
    cap = contract.monthly_cap
    total = sum((line.amount_cad for line in invoice.lines), Decimal("0.00"))

    if total <= cap.value_cad:
        rule = DeterministicRuleResult(
            rule_name=AGGREGATE_CAP_CHECK,
            invoice_line_id=None,
            passed=True,
            detail=f"invoice total {total} <= cap {cap.value_cad}",
        )
        return [], [rule]

    excess = total - cap.value_cad
    rule = DeterministicRuleResult(
        rule_name=AGGREGATE_CAP_CHECK,
        invoice_line_id=None,
        passed=False,
        detail=f"invoice total {total} > cap {cap.value_cad} (excess {excess})",
    )
    finding = ExceptionFinding(
        finding_type=ExceptionType.AGGREGATE_CAP_EXCEEDED,
        basis="deterministic",
        scope="invoice",
        invoice_line_id=None,
        disposition=FindingDisposition.AUTO_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            SupportingQuoteEvidence(
                document_id=cap.source.document_id,
                section=cap.source.section,
                page=cap.source.page,
                quote=cap.quote,
            ),
            ComputedTotalEvidence(document_id=invoice.invoice_id, value_cad=total),
        ],
        computed_values={
            "invoice_total_cad": total,
            "cap_cad": cap.value_cad,
            "excess_cad": excess,
        },
    )
    return [finding], [rule]
