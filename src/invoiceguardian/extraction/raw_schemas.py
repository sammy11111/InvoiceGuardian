"""Raw (loosely-typed) extraction results — what the model actually returns
via tool-use, before normalization.

JSON has no Decimal/date types, so the model returns strings; a separate
normalization step (invoiceguardian.extraction.normalize) converts these
into the strict runtime domain objects. This mirrors the locked pipeline
order: parse -> typed extraction with provenance -> normalization -> ...

`line_id` is deliberately absent from `RawInvoiceLine` — it is never
model-extracted (CLAUDE.md); the parser assigns it from table row order and
the extractor zips it in positionally.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

_ROLE = Literal["SENIOR_CONSULTANT", "CONSULTANT", "PROJECT_MANAGER"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RawSourceRef(_Model):
    section: str
    page: int


class RawRateCardEntry(_Model):
    role: _ROLE
    rate_cad_per_hour: str
    quote: str
    source: RawSourceRef


class RawMonthlyCap(_Model):
    value_cad: str
    quote: str
    source: RawSourceRef


class RawScopeClause(_Model):
    text: str
    source: RawSourceRef


class RawContractExtraction(_Model):
    document_id: str
    client_party: str
    vendor_party: str
    effective_from: str
    effective_to: str
    currency: str
    rate_card: list[RawRateCardEntry]
    monthly_cap: RawMonthlyCap
    authorization_principle: RawScopeClause


class RawHourLimitEntry(_Model):
    role: _ROLE
    max_hours_per_month: int
    source: RawSourceRef


class RawSowExtraction(_Model):
    document_id: str
    period_from: str
    period_to: str
    scope: RawScopeClause
    monthly_hour_limits: list[RawHourLimitEntry]


class RawInvoiceLine(_Model):
    description: str
    hours: int
    rate_cad: str
    amount_cad: str


class RawInvoiceExtraction(_Model):
    invoice_id: str
    invoice_date: str
    service_period_start: str
    service_period_end: str
    sow_reference: str
    currency: str
    lines: list[RawInvoiceLine]
    total_cad: str
