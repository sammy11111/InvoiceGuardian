"""S5 aggregate-cap check: Decimal arithmetic, boundary, evidence shape."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoiceguardian.checks.aggregate_cap import check_aggregate_cap
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

CAP_QUOTE = "Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00."


def _contract(cap: str = "25000.00") -> ContractTerms:
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
            value_cad=Decimal(cap),
            quote=CAP_QUOTE,
            source=SourceRef(document_id="MSA-2026-014", section="4.3", page=2),
        ),
        authorization_principle=ScopeClause(
            text="Northbridge shall perform only those services described in an executed "
            "Statement of Work under this Agreement.",
            source=SourceRef(document_id="MSA-2026-014", section="2.1", page=1),
        ),
    )


def _invoice(amounts: list[str]) -> Invoice:
    lines = [
        InvoiceLine(
            line_id=f"L{i}",
            description=f"line {i}",
            hours=1,
            rate_cad=Decimal(a),
            amount_cad=Decimal(a),
        )
        for i, a in enumerate(amounts, start=1)
    ]
    total = sum((line.amount_cad for line in lines), Decimal("0.00"))
    return Invoice(
        invoice_id="INV-2026-065",
        invoice_date=date(2026, 9, 3),
        service_period_start=date(2026, 8, 1),
        service_period_end=date(2026, 8, 31),
        sow_reference="SOW-2026-03",
        currency="CAD",
        lines=lines,
        total_cad=total,
    )


def test_cap_exceeded_fires_with_exact_excess() -> None:
    contract = _contract()
    invoice = _invoice(["14250.00", "8800.00", "2700.00"])  # 25750.00
    findings, rules = check_aggregate_cap(invoice, contract)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == ExceptionType.AGGREGATE_CAP_EXCEEDED
    assert finding.scope == "invoice"
    assert finding.invoice_line_id is None
    assert finding.disposition == FindingDisposition.AUTO_EXCEPTION
    assert finding.action == ActionType.DRAFT_VENDOR_CLARIFICATION
    assert finding.computed_values == {
        "invoice_total_cad": Decimal("25750.00"),
        "cap_cad": Decimal("25000.00"),
        "excess_cad": Decimal("750.00"),
    }
    assert rules[0].passed is False


def test_cap_finding_carries_cap_quote_and_computed_total() -> None:
    contract = _contract()
    invoice = _invoice(["25750.00"])
    finding = check_aggregate_cap(invoice, contract)[0][0]

    quote = next(e for e in finding.evidence if e.kind == "supporting_quote")
    total = next(e for e in finding.evidence if e.kind == "computed_total")
    assert quote.document_id == "MSA-2026-014"
    assert quote.section == "4.3"
    assert quote.quote == CAP_QUOTE
    assert total.document_id == "INV-2026-065"
    assert total.value_cad == Decimal("25750.00")


def test_total_exactly_at_cap_does_not_fire() -> None:
    contract = _contract()
    invoice = _invoice(["25000.00"])  # exactly the cap
    findings, rules = check_aggregate_cap(invoice, contract)
    assert findings == []
    assert rules[0].passed is True


def test_one_cent_over_cap_fires_with_one_cent_excess() -> None:
    contract = _contract()
    invoice = _invoice(["25000.01"])
    findings, _rules = check_aggregate_cap(invoice, contract)
    computed = findings[0].computed_values
    assert computed is not None
    assert computed["excess_cad"] == Decimal("0.01")


def test_well_under_cap_does_not_fire() -> None:
    contract = _contract()
    invoice = _invoice(["7000.00", "1350.00"])  # 8350.00
    findings, rules = check_aggregate_cap(invoice, contract)
    assert findings == []
    assert rules[0].passed is True
