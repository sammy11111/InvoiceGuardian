from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from invoiceguardian.schemas.runtime import (
    ActionType,
    AnalysisResult,
    ApprovalState,
    ComputedTotalEvidence,
    ContractTerms,
    DeterministicRuleResult,
    ExceptionFinding,
    ExceptionType,
    FindingDisposition,
    Invoice,
    InvoiceDisposition,
    InvoiceLine,
    InvoiceLineEvidence,
    MonthlyCap,
    OperationalTrace,
    RateCardEntry,
    RunVersions,
    ScopeClause,
    ServiceRole,
    SourceRef,
    StatementOfWork,
    SupportingQuoteEvidence,
)


def _msa() -> ContractTerms:
    return ContractTerms(
        document_id="MSA-2026-014",
        client_party="Maplecore Logistics Inc.",
        vendor_party="Northbridge Consulting Ltd.",
        effective_from=date(2026, 3, 1),
        effective_to=date(2027, 2, 28),
        currency="CAD",
        rate_card=[
            RateCardEntry(
                role=ServiceRole.SENIOR_CONSULTANT,
                rate_cad_per_hour=Decimal("150.00"),
                quote="Senior Consultant services shall be billed at CAD $150.00 per hour.",
                source=SourceRef(document_id="MSA-2026-014", section="4.1", page=2),
            ),
        ],
        monthly_cap=MonthlyCap(
            value_cad=Decimal("25000.00"),
            quote=(
                "Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00."
            ),
            source=SourceRef(document_id="MSA-2026-014", section="4.3", page=2),
        ),
        authorization_principle=ScopeClause(
            text=(
                "Northbridge shall perform only those services described in an "
                "executed Statement of Work under this Agreement."
            ),
            source=SourceRef(document_id="MSA-2026-014", section="2.1", page=1),
        ),
    )


def _sow() -> StatementOfWork:
    return StatementOfWork(
        document_id="SOW-2026-03",
        period_from=date(2026, 4, 1),
        period_to=date(2026, 9, 30),
        scope=ScopeClause(
            text=(
                "Northbridge shall provide implementation support for Maplecore's "
                "ERP rollout, data migration validation, and training documentation."
            ),
            source=SourceRef(document_id="SOW-2026-03", section="2", page=1),
        ),
        monthly_hour_limits=[],
    )


def test_contract_and_sow_construct_from_spec_clauses() -> None:
    msa = _msa()
    sow = _sow()
    assert msa.rate_card[0].rate_cad_per_hour == Decimal("150.00")
    assert sow.scope.text.startswith("Northbridge shall provide")


def test_s1_rate_mismatch_finding_round_trips() -> None:
    invoice = Invoice(
        invoice_id="INV-2026-061",
        invoice_date=date(2026, 5, 3),
        service_period_start=date(2026, 4, 1),
        service_period_end=date(2026, 4, 30),
        sow_reference="SOW-2026-03",
        currency="CAD",
        lines=[
            InvoiceLine(
                line_id="L1",
                description="Senior Consultant — ERP implementation support",
                hours=40,
                rate_cad=Decimal("175.00"),
                amount_cad=Decimal("7000.00"),
            ),
            InvoiceLine(
                line_id="L2",
                description="Project Manager — oversight",
                hours=10,
                rate_cad=Decimal("135.00"),
                amount_cad=Decimal("1350.00"),
            ),
        ],
        total_cad=Decimal("8350.00"),
    )

    finding = ExceptionFinding(
        finding_type=ExceptionType.RATE_MISMATCH,
        basis="deterministic",
        scope="line",
        invoice_line_id="L1",
        disposition=FindingDisposition.AUTO_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            SupportingQuoteEvidence(
                document_id="MSA-2026-014",
                section="4.1",
                page=2,
                quote="Senior Consultant services shall be billed at CAD $150.00 per hour.",
            ),
            InvoiceLineEvidence(document_id="INV-2026-061", line_id="L1"),
        ],
        computed_values={
            "billed_rate_cad": Decimal("175.00"),
            "authorized_rate_cad": Decimal("150.00"),
        },
    )

    trace = OperationalTrace(
        invoice_id=invoice.invoice_id,
        versions=RunVersions(
            dataset_version="v1.3-2026-07-15",
            schema_version="1.2",
            prompt_version="v1",
        ),
        input_document_ids=["MSA-2026-014", "SOW-2026-03", "INV-2026-061"],
        extracted_facts=[],
        deterministic_rules=[
            DeterministicRuleResult(
                rule_name="RATE_MISMATCH_CHECK",
                invoice_line_id="L1",
                passed=False,
                detail="billed 175.00 != contract 150.00",
            ),
        ],
        model_calls=[],
        findings=[finding],
        disposition=InvoiceDisposition.EXCEPTIONS_FOUND,
        approval_state=ApprovalState.AWAITING_REVIEW,
    )

    result = AnalysisResult(
        invoice_id=invoice.invoice_id,
        disposition=InvoiceDisposition.EXCEPTIONS_FOUND,
        findings=[finding],
        clean_line_ids=["L2"],
        approval_state=ApprovalState.AWAITING_REVIEW,
        drafted_action=None,
        trace=trace,
    )

    payload = result.model_dump_json()
    restored = AnalysisResult.model_validate_json(payload)
    assert restored == result
    assert restored.findings[0].evidence[0].kind == "supporting_quote"


def test_aggregate_cap_finding_is_invoice_scoped_with_no_line_id() -> None:
    computed_total = ComputedTotalEvidence(
        document_id="INV-2026-065", value_cad=Decimal("25750.00")
    )
    finding = ExceptionFinding(
        finding_type=ExceptionType.AGGREGATE_CAP_EXCEEDED,
        basis="deterministic",
        scope="invoice",
        invoice_line_id=None,
        disposition=FindingDisposition.AUTO_EXCEPTION,
        action=ActionType.DRAFT_VENDOR_CLARIFICATION,
        evidence=[
            SupportingQuoteEvidence(
                document_id="MSA-2026-014",
                section="4.3",
                page=2,
                quote=(
                    "Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00."
                ),
            ),
            computed_total,
        ],
        computed_values={
            "invoice_total_cad": Decimal("25750.00"),
            "cap_cad": Decimal("25000.00"),
            "excess_cad": Decimal("750.00"),
        },
    )
    assert finding.invoice_line_id is None
    assert computed_total.value_cad == Decimal("25750.00")


def test_runtime_models_reject_answer_key_fields() -> None:
    with pytest.raises(ValidationError):
        ExceptionFinding.model_validate(
            {
                "finding_type": ExceptionType.RATE_MISMATCH,
                "basis": "deterministic",
                "scope": "line",
                "invoice_line_id": "L1",
                "disposition": FindingDisposition.AUTO_EXCEPTION,
                "action": ActionType.DRAFT_VENDOR_CLARIFICATION,
                "evidence": [],
                "confidence_expectation": "HIGH",  # answer-key-only field, must be rejected
            }
        )


def test_runtime_module_does_not_import_evaluation() -> None:
    import ast
    import inspect

    import invoiceguardian.schemas.runtime as runtime_module

    tree = ast.parse(inspect.getsource(runtime_module))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not any("evaluation" in name for name in imported_modules)
