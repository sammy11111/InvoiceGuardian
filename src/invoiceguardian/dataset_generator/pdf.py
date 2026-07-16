"""Renders the MSA, SOW, and invoice PDFs.

Layout follows scenario-spec.md §3.3 (invoice layout) and §3.4 (the
page-target guide for the contract and SOW). §3.4's page numbers are
explicitly provisional per the spec ("record actual pages at freeze time")
so nothing here — or downstream — should treat them as final; they only
shape how many `PageBreak`s separate the sections below.

Headers, party boilerplate, and signature blocks are invented freely per
design rule §1.1; only the canonical clause quotes are constrained.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from invoiceguardian.dataset_generator.clauses import ContractClauses, SowClauses
from invoiceguardian.schemas.evaluation import ScenarioAnswerKey

_STYLES = getSampleStyleSheet()
_TITLE = _STYLES["Title"]
_HEADING = _STYLES["Heading2"]
_BODY = ParagraphStyle("InvoiceGuardianBody", parent=_STYLES["BodyText"], spaceAfter=8)

_MARGIN = 0.9 * inch


def _doc(output_path: Path) -> SimpleDocTemplate:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
        title=output_path.stem,
    )


def build_msa_pdf(
    output_path: Path,
    clauses: ContractClauses,
    document_id: str,
    client: str,
    vendor: str,
    effective_from: str,
    effective_to: str,
) -> None:
    story: list[Flowable] = [
        Paragraph("MASTER SERVICES AGREEMENT", _TITLE),
        Paragraph(document_id, _HEADING),
        Spacer(1, 12),
        Paragraph(
            f"This Master Services Agreement is entered into between "
            f'{client} ("Client") and {vendor} ("Vendor"), effective '
            f"{effective_from} through {effective_to}.",
            _BODY,
        ),
        Paragraph("Section 1 — Term", _HEADING),
        Paragraph("1.1. This Agreement governs services performed for Client by Vendor.", _BODY),
        Paragraph(f"1.2. {clauses.term}", _BODY),
        Paragraph("Section 2 — Authorized Services", _HEADING),
        Paragraph(
            "2.1. " + clauses.authorization_principle,
            _BODY,
        ),
        PageBreak(),
        Paragraph("Section 4 — Fees", _HEADING),
        Paragraph("4.1. Rate card:", _BODY),
    ]
    for quote in clauses.rate_card.values():
        story.append(Paragraph(quote, _BODY))
    story.append(Paragraph(f"4.3. {clauses.monthly_cap}", _BODY))
    story.append(PageBreak())
    story.append(Paragraph("Section 5 — Invoicing", _HEADING))
    story.append(Paragraph(f"5.2. {clauses.required_reference}", _BODY))

    _doc(output_path).build(story)


def build_sow_pdf(
    output_path: Path,
    clauses: SowClauses,
    document_id: str,
    msa_document_id: str,
    client: str,
    vendor: str,
    period_from: str,
    period_to: str,
) -> None:
    story: list[Flowable] = [
        Paragraph("STATEMENT OF WORK", _TITLE),
        Paragraph(document_id, _HEADING),
        Spacer(1, 12),
        Paragraph(
            f"This Statement of Work is issued under Master Services Agreement "
            f"{msa_document_id} between {client} and {vendor}, for services "
            f"performed between {period_from} and {period_to}.",
            _BODY,
        ),
        Paragraph("Section 2 — Scope", _HEADING),
        Paragraph(clauses.scope, _BODY),
        Paragraph("Section 3 — Roles and Monthly Limits", _HEADING),
    ]
    for quote in clauses.role_hour_limits.values():
        story.append(Paragraph(quote, _BODY))
    story.append(PageBreak())
    story.append(Paragraph("Section 4 — Period", _HEADING))
    story.append(Paragraph(clauses.period, _BODY))

    _doc(output_path).build(story)


def build_invoice_pdf(
    output_path: Path,
    scenario: ScenarioAnswerKey,
    vendor: str,
    client: str,
) -> None:
    header_rows = [
        ["Vendor:", vendor],
        ["Client:", client],
        ["Invoice Number:", scenario.invoice_id],
        ["Invoice Date:", scenario.invoice_date.isoformat()],
        [
            "Service Period:",
            f"{scenario.service_period_start.isoformat()} to "
            f"{scenario.service_period_end.isoformat()}",
        ],
        ["SOW Reference:", scenario.sow_reference],
    ]
    header_table = Table(header_rows, colWidths=[1.6 * inch, 4.4 * inch])
    header_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    cell_style = ParagraphStyle("InvoiceGuardianCell", parent=_STYLES["BodyText"], fontSize=9)
    line_rows: list[list[str | Paragraph]] = [
        ["Line ID", "Description", "Hours", "Rate (CAD/hr)", "Amount (CAD)"]
    ]
    for line in scenario.invoice_lines:
        line_rows.append(
            [
                line.line_id,
                Paragraph(line.description, cell_style),
                str(line.hours),
                line.rate_cad,
                line.amount_cad,
            ]
        )
    line_table = Table(
        line_rows, colWidths=[0.6 * inch, 3.0 * inch, 0.7 * inch, 1.2 * inch, 1.2 * inch]
    )
    line_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ]
        )
    )

    story: list[Flowable] = [
        Paragraph("INVOICE", _TITLE),
        Spacer(1, 6),
        header_table,
        Spacer(1, 18),
        line_table,
        Spacer(1, 12),
        Paragraph(f"Total (CAD): {scenario.invoice_total_cad}", _HEADING),
    ]

    _doc(output_path).build(story)
