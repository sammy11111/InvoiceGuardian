"""End-to-end orchestration for a single invoice: parse -> typed extraction
with provenance -> normalization -> deterministic checks (rate + aggregate
cap) -> bounded semantic comparison on unresolved lines -> evidence-cited
findings -> operational trace -> human-approval state.

All six scenarios run through this path. A full-dataset run performs the
fixed 11-operation manifest: 2 shared-document extractions (MSA, SOW), 6
invoice extractions, and 3 semantic-comparison operations (one per
unresolved line — S2-L1, S3-L1, S4-L1).
"""

from __future__ import annotations

from pathlib import Path

from invoiceguardian.checks.aggregate_cap import check_aggregate_cap
from invoiceguardian.checks.rate_check import check_rate_mismatches
from invoiceguardian.checks.role_matching import match_role_exact
from invoiceguardian.checks.semantic import build_semantic_finding
from invoiceguardian.dataset_generator.content import MSA_DOCUMENT_ID, SOW_DOCUMENT_ID
from invoiceguardian.dataset_generator.generate import DEFAULT_OUTPUT_DIR, generate_dataset
from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL
from invoiceguardian.extraction.extractor import extract_contract, extract_invoice, extract_sow
from invoiceguardian.extraction.prompts import PROMPT_VERSION
from invoiceguardian.extraction.semantic import classify_line
from invoiceguardian.schemas.runtime import (
    ActionType,
    AnalysisResult,
    ApprovalState,
    ContractTerms,
    DeterministicRuleResult,
    DraftedAction,
    ExceptionFinding,
    ExtractedFactRecord,
    FindingDisposition,
    Invoice,
    InvoiceDisposition,
    ModelCallRecord,
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


def _contract_fact_records(contract: ContractTerms) -> list[ExtractedFactRecord]:
    """Every MSA extraction field named exactly as in answer_keys.json's
    manifest, so the evaluator can score extraction accuracy field-by-field."""
    records = [
        ExtractedFactRecord(
            document_id=contract.document_id, field="client_party", value=contract.client_party
        ),
        ExtractedFactRecord(
            document_id=contract.document_id, field="vendor_party", value=contract.vendor_party
        ),
        ExtractedFactRecord(
            document_id=contract.document_id,
            field="effective_from",
            value=contract.effective_from.isoformat(),
        ),
        ExtractedFactRecord(
            document_id=contract.document_id,
            field="effective_to",
            value=contract.effective_to.isoformat(),
        ),
        ExtractedFactRecord(
            document_id=contract.document_id, field="currency", value=contract.currency
        ),
    ]
    records.extend(
        ExtractedFactRecord(
            document_id=contract.document_id,
            field=f"rate[{entry.role.value}]",
            value=str(entry.rate_cad_per_hour),
            source=entry.source,
        )
        for entry in contract.rate_card
    )
    records.append(
        ExtractedFactRecord(
            document_id=contract.document_id,
            field="monthly_cap_cad",
            value=str(contract.monthly_cap.value_cad),
            source=contract.monthly_cap.source,
        )
    )
    return records


def _sow_fact_records(sow: StatementOfWork) -> list[ExtractedFactRecord]:
    records = [
        ExtractedFactRecord(document_id=sow.document_id, field="sow_id", value=sow.document_id),
        ExtractedFactRecord(
            document_id=sow.document_id, field="period_from", value=sow.period_from.isoformat()
        ),
        ExtractedFactRecord(
            document_id=sow.document_id, field="period_to", value=sow.period_to.isoformat()
        ),
    ]
    records.extend(
        ExtractedFactRecord(
            document_id=sow.document_id,
            field=f"hour_limit[{entry.role.value}]",
            value=str(entry.max_hours_per_month),
            source=entry.source,
        )
        for entry in sow.monthly_hour_limits
    )
    records.append(
        ExtractedFactRecord(
            document_id=sow.document_id,
            field="scope_text",
            value=sow.scope.text,
            source=sow.scope.source,
        )
    )
    return records


def _invoice_fact_records(invoice: Invoice) -> list[ExtractedFactRecord]:
    doc = invoice.invoice_id
    records = [
        ExtractedFactRecord(document_id=doc, field="invoice_id", value=invoice.invoice_id),
        ExtractedFactRecord(
            document_id=doc, field="invoice_date", value=invoice.invoice_date.isoformat()
        ),
        ExtractedFactRecord(
            document_id=doc,
            field="service_period_start",
            value=invoice.service_period_start.isoformat(),
        ),
        ExtractedFactRecord(
            document_id=doc,
            field="service_period_end",
            value=invoice.service_period_end.isoformat(),
        ),
        ExtractedFactRecord(document_id=doc, field="sow_reference", value=invoice.sow_reference),
        ExtractedFactRecord(document_id=doc, field="currency", value=invoice.currency),
        ExtractedFactRecord(
            document_id=doc, field="invoice_total_cad", value=str(invoice.total_cad)
        ),
    ]
    for line in invoice.lines:
        records.append(
            ExtractedFactRecord(
                document_id=doc, field=f"line[{line.line_id}].description", value=line.description
            )
        )
        records.append(
            ExtractedFactRecord(
                document_id=doc, field=f"line[{line.line_id}].hours", value=str(line.hours)
            )
        )
        records.append(
            ExtractedFactRecord(
                document_id=doc, field=f"line[{line.line_id}].rate_cad", value=str(line.rate_cad)
            )
        )
        records.append(
            ExtractedFactRecord(
                document_id=doc,
                field=f"line[{line.line_id}].amount_cad",
                value=str(line.amount_cad),
            )
        )
    return records


def _extracted_fact_records(
    contract: ContractTerms, sow: StatementOfWork, invoice: Invoice
) -> list[ExtractedFactRecord]:
    return [
        *_contract_fact_records(contract),
        *_sow_fact_records(sow),
        *_invoice_fact_records(invoice),
    ]


def _run_semantic_path(
    invoice: Invoice, contract: ContractTerms, sow: StatementOfWork, model: str
) -> tuple[list[ExceptionFinding], list[DeterministicRuleResult], list[ModelCallRecord]]:
    """Bounded semantic comparison runs on unresolved descriptions only —
    lines where exact-prefix role matching fell through (CLAUDE.md). One
    model call per unresolved line."""
    findings: list[ExceptionFinding] = []
    rule_results: list[DeterministicRuleResult] = []
    model_calls: list[ModelCallRecord] = []

    for line in invoice.lines:
        if match_role_exact(line.description) is not None:
            continue  # resolved deterministically; never reaches the model
        classification, call = classify_line(
            line.description,
            contract,
            sow,
            invoice_id=invoice.invoice_id,
            line_id=line.line_id,
            model=model,
        )
        model_calls.append(call)
        finding, rule = build_semantic_finding(
            classification, line, invoice.invoice_id, contract, sow
        )
        rule_results.append(rule)
        if finding is not None:
            findings.append(finding)

    return findings, rule_results, model_calls


def _invoice_disposition(findings: list[ExceptionFinding]) -> InvoiceDisposition:
    """Precedence: unresolved ambiguity gates the whole invoice, so any
    ESCALATE finding forces ESCALATION_REQUIRED even alongside confident
    exceptions; otherwise any finding is EXCEPTIONS_FOUND; else CLEAN. (No v1
    scenario mixes escalation and confident exceptions — this defines the
    branch so it is never undefined.)"""
    if any(f.disposition is FindingDisposition.ESCALATE for f in findings):
        return InvoiceDisposition.ESCALATION_REQUIRED
    if findings:
        return InvoiceDisposition.EXCEPTIONS_FOUND
    return InvoiceDisposition.CLEAN


def _draft_summary(invoice_id: str, disposition: InvoiceDisposition) -> str:
    tail = (
        "This is a draft only — no communication has been sent. Human review and "
        "approval are required before any action is taken."
    )
    if disposition is InvoiceDisposition.ESCALATION_REQUIRED:
        return (
            f"Invoice {invoice_id} contains a line whose authorization could not be "
            f"resolved from the supplied contract and statement of work; it is routed "
            f"for human review. {tail}"
        )
    return (
        f"Invoice {invoice_id} has one or more exceptions relative to the supplied "
        f"contract and statement of work, listed above. {tail}"
    )


def _drafted_action(invoice_id: str, disposition: InvoiceDisposition) -> DraftedAction | None:
    if disposition is InvoiceDisposition.CLEAN:
        return None
    action_type = (
        ActionType.HUMAN_REVIEW
        if disposition is InvoiceDisposition.ESCALATION_REQUIRED
        else ActionType.DRAFT_VENDOR_CLARIFICATION
    )
    return DraftedAction(action_type=action_type, summary=_draft_summary(invoice_id, disposition))


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

    rate_findings, rate_rules = check_rate_mismatches(invoice, contract)
    cap_findings, cap_rules = check_aggregate_cap(invoice, contract)
    semantic_findings, semantic_rules, semantic_calls = _run_semantic_path(
        invoice, contract, sow, model
    )

    findings = [*rate_findings, *cap_findings, *semantic_findings]
    rule_results = [*rate_rules, *cap_rules, *semantic_rules]

    # Line-scoped findings mark their line; the invoice-scoped cap finding
    # (invoice_line_id=None) leaves every line clean by design.
    exception_line_ids = {f.invoice_line_id for f in findings if f.invoice_line_id is not None}
    clean_line_ids = [
        line.line_id for line in invoice.lines if line.line_id not in exception_line_ids
    ]

    disposition = _invoice_disposition(findings)
    approval_state = (
        ApprovalState.NO_ACTION_REQUIRED
        if disposition is InvoiceDisposition.CLEAN
        else ApprovalState.AWAITING_REVIEW
    )

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
        model_calls=[msa_call, sow_call, invoice_call, *semantic_calls],
        findings=findings,
        disposition=disposition,
        approval_state=approval_state,
    )

    return AnalysisResult(
        invoice_id=invoice.invoice_id,
        disposition=disposition,
        findings=findings,
        clean_line_ids=clean_line_ids,
        approval_state=approval_state,
        drafted_action=_drafted_action(invoice.invoice_id, disposition),
        trace=trace,
    )
