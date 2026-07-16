"""Normalization: raw (string-typed) extraction results -> strict runtime
domain objects.

Ordinary code, no model calls — matches the locked pipeline order (parse ->
typed extraction with provenance -> normalization -> deterministic checks).
Money is quantized to 0.01 via Decimal, never float (CLAUDE.md).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from invoiceguardian.extraction.raw_schemas import (
    RawContractExtraction,
    RawInvoiceExtraction,
    RawSourceRef,
    RawSowExtraction,
)
from invoiceguardian.schemas.runtime import (
    ContractTerms,
    HourLimitEntry,
    Invoice,
    InvoiceLine,
    MonthlyCap,
    RateCardEntry,
    ScopeClause,
    ServiceRole,
    SourceRef,
    StatementOfWork,
)

_CENTS = Decimal("0.01")


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _to_decimal(value: str) -> Decimal:
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def _to_date(value: str) -> date:
    return date.fromisoformat(value)


def _source(document_id: str, raw: RawSourceRef) -> SourceRef:
    return SourceRef(document_id=document_id, section=raw.section, page=raw.page)


def normalize_contract(raw: RawContractExtraction) -> ContractTerms:
    return ContractTerms(
        document_id=raw.document_id,
        client_party=_collapse_whitespace(raw.client_party),
        vendor_party=_collapse_whitespace(raw.vendor_party),
        effective_from=_to_date(raw.effective_from),
        effective_to=_to_date(raw.effective_to),
        currency=raw.currency.strip().upper(),
        rate_card=[
            RateCardEntry(
                role=ServiceRole(entry.role),
                rate_cad_per_hour=_to_decimal(entry.rate_cad_per_hour),
                quote=_collapse_whitespace(entry.quote),
                source=_source(raw.document_id, entry.source),
            )
            for entry in raw.rate_card
        ],
        monthly_cap=MonthlyCap(
            value_cad=_to_decimal(raw.monthly_cap.value_cad),
            quote=_collapse_whitespace(raw.monthly_cap.quote),
            source=_source(raw.document_id, raw.monthly_cap.source),
        ),
        authorization_principle=ScopeClause(
            text=_collapse_whitespace(raw.authorization_principle.text),
            source=_source(raw.document_id, raw.authorization_principle.source),
        ),
    )


def normalize_sow(raw: RawSowExtraction) -> StatementOfWork:
    return StatementOfWork(
        document_id=raw.document_id,
        period_from=_to_date(raw.period_from),
        period_to=_to_date(raw.period_to),
        scope=ScopeClause(
            text=_collapse_whitespace(raw.scope.text),
            source=_source(raw.document_id, raw.scope.source),
        ),
        monthly_hour_limits=[
            HourLimitEntry(
                role=ServiceRole(entry.role),
                max_hours_per_month=entry.max_hours_per_month,
                source=_source(raw.document_id, entry.source),
            )
            for entry in raw.monthly_hour_limits
        ],
    )


def normalize_invoice(raw: RawInvoiceExtraction, line_ids: list[str]) -> Invoice:
    if len(raw.lines) != len(line_ids):
        raise ValueError(
            f"extraction returned {len(raw.lines)} line items but the parser found "
            f"{len(line_ids)} table rows for {raw.invoice_id}"
        )
    return Invoice(
        invoice_id=raw.invoice_id,
        invoice_date=_to_date(raw.invoice_date),
        service_period_start=_to_date(raw.service_period_start),
        service_period_end=_to_date(raw.service_period_end),
        sow_reference=raw.sow_reference.strip(),
        currency=raw.currency.strip().upper(),
        lines=[
            InvoiceLine(
                line_id=line_id,
                description=_collapse_whitespace(line.description),
                hours=line.hours,
                rate_cad=_to_decimal(line.rate_cad),
                amount_cad=_to_decimal(line.amount_cad),
            )
            for line_id, line in zip(line_ids, raw.lines, strict=True)
        ],
        total_cad=_to_decimal(raw.total_cad),
    )
