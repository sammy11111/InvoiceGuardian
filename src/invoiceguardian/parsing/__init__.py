"""PDF parsing: pdfplumber page text and deterministic table-row metadata.

Locked parsing library per CLAUDE.md (pdfplumber/PyMuPDF; digitally
generated PDFs only, no OCR). This module produces the raw inputs that
`invoiceguardian.extraction` turns into typed domain objects — it does not
itself do any typed extraction or model calls.
"""
