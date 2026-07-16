from datetime import date
from decimal import Decimal

from invoiceguardian.checks.rate_check import check_rate_mismatches
from invoiceguardian.schemas.runtime import (
    ActionType,
    ContractTerms,
    ExceptionType,
    FindingDisposition,
    Invoice,
    InvoiceLine,
    MonthlyCap,
    RateCardEntry,
    ScopeClause,
    ServiceRole,
    SourceRef,
)


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
            ),
            RateCardEntry(
                role=ServiceRole.PROJECT_MANAGER,
                rate_cad_per_hour=Decimal("135.00"),
                quote="Project Manager services shall be billed at CAD $135.00 per hour.",
                source=SourceRef(document_id="MSA-2026-014", section="4.1", page=2),
            ),
        ],
        monthly_cap=MonthlyCap(
            value_cad=Decimal("25000.00"),
            quote=(
                "Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00."
            ),
            source=SourceRef(document_id="MSA-2026-014", section="4.3", page=2),
        ),
        authorization_principle=ScopeClause(
            text=(
                "Northbridge shall perform only those services described in an "
                "executed Statement of Work under this Agreement."
            ),
            source=SourceRef(document_id="MSA-2026-014", section="2.1", page=1),
        ),
    )


def _invoice(lines: list[InvoiceLine]) -> Invoice:
    return Invoice(
        invoice_id="INV-2026-061",
        invoice_date=date(2026, 5, 3),
        service_period_start=date(2026, 4, 1),
        service_period_end=date(2026, 4, 30),
        sow_reference="SOW-2026-03",
        currency="CAD",
        lines=lines,
        total_cad=sum((line.amount_cad for line in lines), Decimal("0.00")),
    )


def test_mismatched_rate_produces_one_cited_finding() -> None:
    contract = _contract()
    invoice = _invoice(
        [
            InvoiceLine(
                line_id="L1",
                description="Senior Consultant — ERP implementation support",
                hours=40,
                rate_cad=Decimal("175.00"),
                amount_cad=Decimal("7000.00"),
            ),
            InvoiceLine(
                line_id="L2",
                description="Project Manager — oversight",
                hours=10,
                rate_cad=Decimal("135.00"),
                amount_cad=Decimal("1350.00"),
            ),
        ]
    )

    findings, rule_results = check_rate_mismatches(invoice, contract)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == ExceptionType.RATE_MISMATCH
    assert finding.basis == "deterministic"
    assert finding.scope == "line"
    assert finding.invoice_line_id == "L1"
    assert finding.disposition == FindingDisposition.AUTO_EXCEPTION
    assert finding.action == ActionType.DRAFT_VENDOR_CLARIFICATION
    assert finding.computed_values == {
        "billed_rate_cad": Decimal("175.00"),
        "authorized_rate_cad": Decimal("150.00"),
    }

    quote_evidence, line_evidence = finding.evidence
    assert quote_evidence.kind == "supporting_quote"
    assert (
        quote_evidence.quote
        == "Senior Consultant services shall be billed at CAD $150.00 per hour."
    )
    assert quote_evidence.document_id == "MSA-2026-014"
    assert quote_evidence.section == "4.1"
    assert quote_evidence.page == 2
    assert line_evidence.kind == "invoice_line"
    assert line_evidence.document_id == "INV-2026-061"
    assert line_evidence.line_id == "L1"

    assert {r.invoice_line_id: r.passed for r in rule_results} == {"L1": False, "L2": True}


def test_matching_rate_produces_no_finding() -> None:
    contract = _contract()
    invoice = _invoice(
        [
            InvoiceLine(
                line_id="L1",
                description="Senior Consultant — ERP implementation support",
                hours=50,
                rate_cad=Decimal("150.00"),
                amount_cad=Decimal("7500.00"),
            ),
        ]
    )

    findings, rule_results = check_rate_mismatches(invoice, contract)

    assert findings == []
    assert len(rule_results) == 1
    assert rule_results[0].passed is True


def test_unresolved_role_description_is_skipped_entirely() -> None:
    """S2's line doesn't match any known role label — it must be left
    unresolved here, not misclassified into a rate check."""
    contract = _contract()
    invoice = _invoice(
        [
            InvoiceLine(
                line_id="L1",
                description="Architecture Workshop Facilitation",
                hours=12,
                rate_cad=Decimal("150.00"),
                amount_cad=Decimal("1800.00"),
            ),
        ]
    )

    findings, rule_results = check_rate_mismatches(invoice, contract)

    assert findings == []
    assert rule_results == []
