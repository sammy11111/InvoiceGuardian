"""Orchestrates one typed-extraction model call per document.

Matches SCORING.md's required-operation manifest: one extraction operation
per shared document (MSA, SOW) and one per invoice.
"""

from __future__ import annotations

from pathlib import Path

from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL, call_tool_validated
from invoiceguardian.extraction.json_schema_utils import resolve_refs
from invoiceguardian.extraction.normalize import (
    normalize_contract,
    normalize_invoice,
    normalize_sow,
)
from invoiceguardian.extraction.prompts import (
    CONTRACT_EXTRACTION_SYSTEM_PROMPT,
    INVOICE_EXTRACTION_SYSTEM_PROMPT,
    SOW_EXTRACTION_SYSTEM_PROMPT,
)
from invoiceguardian.extraction.raw_schemas import (
    RawContractExtraction,
    RawInvoiceExtraction,
    RawSowExtraction,
)
from invoiceguardian.parsing.pdf_text import (
    extract_invoice_line_ids,
    format_pages_for_prompt,
    parse_pdf_pages,
)
from invoiceguardian.schemas.runtime import ContractTerms, Invoice, ModelCallRecord, StatementOfWork

_CONTRACT_SCHEMA = resolve_refs(RawContractExtraction.model_json_schema())
_SOW_SCHEMA = resolve_refs(RawSowExtraction.model_json_schema())
_INVOICE_SCHEMA = resolve_refs(RawInvoiceExtraction.model_json_schema())


def extract_contract(
    pdf_path: Path, document_id: str, model: str = DEFAULT_MODEL
) -> tuple[ContractTerms, ModelCallRecord]:
    pages = parse_pdf_pages(pdf_path)
    user_content = f"Document ID: {document_id}\n\n{format_pages_for_prompt(pages)}"
    raw, retried, _input_tokens, _output_tokens = call_tool_validated(
        model=model,
        system=CONTRACT_EXTRACTION_SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="extract_contract_terms",
        tool_description="Record the typed contract terms extracted from the supplied MSA text.",
        input_schema=_CONTRACT_SCHEMA,
        raw_model=RawContractExtraction,
    )
    contract = normalize_contract(raw)
    record = ModelCallRecord(
        model_id=model, effort=None, purpose="MSA_EXTRACTION", schema_valid=True, retried=retried
    )
    return contract, record


def extract_sow(
    pdf_path: Path, document_id: str, model: str = DEFAULT_MODEL
) -> tuple[StatementOfWork, ModelCallRecord]:
    pages = parse_pdf_pages(pdf_path)
    user_content = f"Document ID: {document_id}\n\n{format_pages_for_prompt(pages)}"
    raw, retried, _input_tokens, _output_tokens = call_tool_validated(
        model=model,
        system=SOW_EXTRACTION_SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="extract_sow_terms",
        tool_description=(
            "Record the typed Statement of Work terms extracted from the supplied SOW text."
        ),
        input_schema=_SOW_SCHEMA,
        raw_model=RawSowExtraction,
    )
    sow = normalize_sow(raw)
    record = ModelCallRecord(
        model_id=model, effort=None, purpose="SOW_EXTRACTION", schema_valid=True, retried=retried
    )
    return sow, record


def extract_invoice(pdf_path: Path, model: str = DEFAULT_MODEL) -> tuple[Invoice, ModelCallRecord]:
    pages = parse_pdf_pages(pdf_path)
    line_ids = extract_invoice_line_ids(pdf_path)
    user_content = (
        f"This invoice's line-item table has exactly {len(line_ids)} row(s) after the "
        f"header row. Return exactly {len(line_ids)} line item(s), one per row, in the "
        f"same top-to-bottom order as the table.\n\n{format_pages_for_prompt(pages)}"
    )
    raw, retried, _input_tokens, _output_tokens = call_tool_validated(
        model=model,
        system=INVOICE_EXTRACTION_SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="extract_invoice",
        tool_description=(
            "Record the typed invoice fields and line items extracted from the supplied "
            "invoice text."
        ),
        input_schema=_INVOICE_SCHEMA,
        raw_model=RawInvoiceExtraction,
    )
    invoice = normalize_invoice(raw, line_ids)
    record = ModelCallRecord(
        model_id=model,
        effort=None,
        purpose="INVOICE_EXTRACTION",
        schema_valid=True,
        retried=retried,
    )
    return invoice, record
