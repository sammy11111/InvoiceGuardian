"""End-to-end orchestration for a single invoice: parse -> typed extraction
with provenance -> normalization -> deterministic checks -> evidence-cited
findings -> operational trace -> human-approval state.

This is a vertical slice (step 3 of the build order): only the S1
deterministic rate check runs here. S2/S4's semantic paths, S5's aggregate
cap, and the full evaluator are later build steps.
"""

from __future__ import annotations

from pathlib import Path

from invoiceguardian.checks.rate_check import check_rate_mismatches
from invoiceguardian.dataset_generator.content import MSA_DOCUMENT_ID, SOW_DOCUMENT_ID
from invoiceguardian.dataset_generator.generate import DEFAULT_OUTPUT_DIR, generate_dataset
from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL
from invoiceguardian.extraction.extractor import extract_contract, extract_invoice, extract_sow
from invoiceguardian.extraction.prompts import PROMPT_VERSION
from invoiceguardian.schemas.runtime import (
    ActionType,
    AnalysisResult,
    ApprovalState,
    ContractTerms,
    DraftedAction,
    ExtractedFactRecord,
    Invoice,
    InvoiceDisposition,
    OperationalTrace,
    RunVersions,
    StatementOfWork,
)

DEFAULT_PDF_DIR = DEFAULT_OUTPUT_DIR

# This v1 product only ever analyzes the six canned synthetic scenarios
# (LIMITATIONS.md: "canned synthetic scenarios only, no arbitrary public PDF
# upload in v1") — dataset_version and answer_key_schema_version are stable
# constants until a new dataset is frozen.
DATASET_VERSION = "v1.3-2026-07-15"
ANSWER_KEY_SCHEMA_VERSION = "1.2"


def _extracted_fact_records(
    contract: ContractTerms, sow: StatementOfWork, invoice: Invoice
) -> list[ExtractedFactRecord]:
    records = [
        ExtractedFactRecord(
            document_id=contract.document_id,
            field=f"rate[{entry.role.value}]",
            value=str(entry.rate_cad_per_hour),
            source=entry.source,
        )
        for entry in contract.rate_card
    ]
    records.append(
        ExtractedFactRecord(
            document_id=contract.document_id,
            field="monthly_cap_cad",
            value=str(contract.monthly_cap.value_cad),
            source=contract.monthly_cap.source,
        )
    )
    records.append(
        ExtractedFactRecord(
            document_id=sow.document_id,
            field="scope_text",
            value=sow.scope.text,
            source=sow.scope.source,
        )
    )
    records.extend(
        ExtractedFactRecord(
            document_id=sow.document_id,
            field=f"hour_limit[{entry.role.value}]",
            value=str(entry.max_hours_per_month),
            source=entry.source,
        )
        for entry in sow.monthly_hour_limits
    )
    for line in invoice.lines:
        records.append(
            ExtractedFactRecord(
                document_id=invoice.invoice_id,
                field=f"line[{line.line_id}].description",
                value=line.description,
            )
        )
        records.append(
            ExtractedFactRecord(
                document_id=invoice.invoice_id,
                field=f"line[{line.line_id}].rate_cad",
                value=str(line.rate_cad),
            )
        )
    return records


def _draft_summary(invoice_id: str, finding_count: int) -> str:
    plural = "s" if finding_count != 1 else ""
    return (
        f"{finding_count} rate-mismatch exception{plural} found on invoice {invoice_id}: "
        "the billed rate differs from the MSA rate card for the line(s) listed above. "
        "This is a draft only — no communication has been sent. Human review and "
        "approval are required before any vendor clarification is sent."
    )


def run_analysis(
    invoice_id: str,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    model: str = DEFAULT_MODEL,
) -> AnalysisResult:
    required = {f"{MSA_DOCUMENT_ID}.pdf", f"{SOW_DOCUMENT_ID}.pdf", f"{invoice_id}.pdf"}
    if not pdf_dir.exists() or not required.issubset({p.name for p in pdf_dir.glob("*.pdf")}):
        generate_dataset(output_dir=pdf_dir)

    contract, msa_call = extract_contract(
        pdf_dir / f"{MSA_DOCUMENT_ID}.pdf", MSA_DOCUMENT_ID, model=model
    )
    sow, sow_call = extract_sow(pdf_dir / f"{SOW_DOCUMENT_ID}.pdf", SOW_DOCUMENT_ID, model=model)
    invoice, invoice_call = extract_invoice(pdf_dir / f"{invoice_id}.pdf", model=model)

    findings, rule_results = check_rate_mismatches(invoice, contract)
    exception_line_ids = {f.invoice_line_id for f in findings}
    clean_line_ids = [
        line.line_id for line in invoice.lines if line.line_id not in exception_line_ids
    ]

    disposition = InvoiceDisposition.EXCEPTIONS_FOUND if findings else InvoiceDisposition.CLEAN
    approval_state = ApprovalState.AWAITING_REVIEW if findings else ApprovalState.NO_ACTION_REQUIRED

    trace = OperationalTrace(
        invoice_id=invoice.invoice_id,
        versions=RunVersions(
            dataset_version=DATASET_VERSION,
            schema_version=ANSWER_KEY_SCHEMA_VERSION,
            prompt_version=PROMPT_VERSION,
        ),
        input_document_ids=[MSA_DOCUMENT_ID, SOW_DOCUMENT_ID, invoice_id],
        extracted_facts=_extracted_fact_records(contract, sow, invoice),
        deterministic_rules=rule_results,
        model_calls=[msa_call, sow_call, invoice_call],
        findings=findings,
        disposition=disposition,
        approval_state=approval_state,
    )

    drafted_action = (
        DraftedAction(
            action_type=ActionType.DRAFT_VENDOR_CLARIFICATION,
            summary=_draft_summary(invoice.invoice_id, len(findings)),
        )
        if findings
        else None
    )

    return AnalysisResult(
        invoice_id=invoice.invoice_id,
        disposition=disposition,
        findings=findings,
        clean_line_ids=clean_line_ids,
        approval_state=approval_state,
        drafted_action=drafted_action,
        trace=trace,
    )
