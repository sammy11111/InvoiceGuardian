"""Malformed-input behavior for normalize.py — not just the happy path.

Normalization is ordinary code that coerces model-returned strings into
strict typed values; these tests pin down what it does with inputs the model
could plausibly emit (bad decimals, bad dates, an out-of-vocabulary role, a
line-count disagreement with the parser)."""

from __future__ import annotations

from decimal import InvalidOperation

import pytest

from invoiceguardian.extraction.normalize import (
    normalize_contract,
    normalize_invoice,
    normalize_sow,
)
from invoiceguardian.extraction.raw_schemas import (
    RawContractExtraction,
    RawInvoiceExtraction,
    RawInvoiceLine,
    RawMonthlyCap,
    RawRateCardEntry,
    RawScopeClause,
    RawSourceRef,
    RawSowExtraction,
)


def _source() -> RawSourceRef:
    return RawSourceRef(section="4.1", page=2)


def _contract(*, rate: str = "150.00") -> RawContractExtraction:
    return RawContractExtraction(
        document_id="MSA-2026-014",
        client_party="Maplecore Logistics Inc.",
        vendor_party="Northbridge Consulting Ltd.",
        effective_from="2026-03-01",
        effective_to="2027-02-28",
        currency="CAD",
        rate_card=[
            RawRateCardEntry(
                role="SENIOR_CONSULTANT", rate_cad_per_hour=rate, quote="q", source=_source()
            )
        ],
        monthly_cap=RawMonthlyCap(value_cad="25000.00", quote="q", source=_source()),
        authorization_principle=RawScopeClause(text="a", source=_source()),
    )


def _sow(*, period_from: str = "2026-04-01") -> RawSowExtraction:
    return RawSowExtraction(
        document_id="SOW-2026-03",
        period_from=period_from,
        period_to="2026-09-30",
        scope=RawScopeClause(text="s", source=RawSourceRef(section="2", page=1)),
        monthly_hour_limits=[],
    )


def _invoice(lines: list[RawInvoiceLine]) -> RawInvoiceExtraction:
    return RawInvoiceExtraction(
        invoice_id="INV-2026-061",
        invoice_date="2026-05-03",
        service_period_start="2026-04-01",
        service_period_end="2026-04-30",
        sow_reference="SOW-2026-03",
        currency="CAD",
        lines=lines,
        total_cad="8350.00",
    )


def test_bad_decimal_string_raises() -> None:
    with pytest.raises(InvalidOperation):
        normalize_contract(_contract(rate="not-a-number"))


def test_bad_date_string_raises() -> None:
    with pytest.raises(ValueError):
        normalize_sow(_sow(period_from="2026-13-99"))


def test_unrecognized_role_raises() -> None:
    # Bypass the raw-schema Literal to simulate a model returning an
    # out-of-vocabulary role; normalization must reject it, not coerce it.
    bad_entry = RawRateCardEntry.model_construct(
        role="MANAGER", rate_cad_per_hour="150.00", quote="q", source=_source()
    )
    contract = _contract()
    contract = contract.model_copy(update={"rate_card": [bad_entry]})
    with pytest.raises(ValueError):
        normalize_contract(contract)


def test_line_count_mismatch_with_parser_raises() -> None:
    invoice = _invoice(
        [RawInvoiceLine(description="x", hours=1, rate_cad="1.00", amount_cad="1.00")]
    )
    with pytest.raises(ValueError, match="line"):
        normalize_invoice(invoice, ["L1", "L2"])  # parser saw 2 rows, extraction returned 1


def test_clean_inputs_normalize_successfully() -> None:
    contract = normalize_contract(_contract())
    assert str(contract.rate_card[0].rate_cad_per_hour) == "150.00"
    invoice = normalize_invoice(
        _invoice([RawInvoiceLine(description="x", hours=1, rate_cad="1.005", amount_cad="1.00")]),
        ["L1"],
    )
    # decimal_2dp quantization applies: 1.005 -> 1.01 under ROUND_HALF_UP.
    assert str(invoice.lines[0].rate_cad) == "1.01"
