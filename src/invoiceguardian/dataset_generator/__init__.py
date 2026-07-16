"""Generates the InvoiceGuardian synthetic evaluation-dataset PDFs
(MSA-2026-014, SOW-2026-03, INV-2026-061..066) from scenario-spec.md §3-§4.

This is dataset-authoring tooling, not the runtime pipeline: it produces the
fixtures that the (future) parser consumes. It must never leak into
`invoiceguardian.schemas.runtime`.
"""
