from __future__ import annotations

from pathlib import Path

import pdfplumber


def parse_pdf_pages(pdf_path: Path) -> list[str]:
    """Returns page text, one entry per page, in order (index 0 = page 1)."""
    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def format_pages_for_prompt(pages: list[str]) -> str:
    """Page-tags text for the extraction prompt so the model can report
    which page a fact came from."""
    return "\n\n".join(f"[PAGE {i}]\n{text}" for i, text in enumerate(pages, start=1))


def extract_invoice_line_ids(pdf_path: Path) -> list[str]:
    """Deterministic parser metadata: line_id is assigned from the
    line-item table's row order, never model-extracted (CLAUDE.md)."""
    with pdfplumber.open(pdf_path) as pdf:
        tables = pdf.pages[0].extract_tables()
    if len(tables) != 1:
        raise ValueError(f"expected exactly one line-item table in {pdf_path}, found {len(tables)}")
    _header, *rows = tables[0]
    if not rows:
        raise ValueError(f"no invoice line rows found in {pdf_path}")
    return [f"L{i}" for i in range(1, len(rows) + 1)]
