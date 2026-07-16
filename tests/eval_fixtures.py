"""Shared fixtures for evaluator tests.

Builds *constructed* `AnalysisResult`s / `BenchmarkRun`s directly from the
answer key — i.e. what a perfect pipeline would emit. These are explicitly
hand-built fixtures, not real pipeline output; the semantic checks (S2/S4/S5)
that would produce these findings live for real do not exist until build
step 6, so the evaluator can only be exercised against them via fixtures now.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from invoiceguardian.schemas.evaluation import (
    BenchmarkRun,
    EvaluationDataset,
    ExpectedAbsenceOfAuthorization,
    ExpectedComputedTotal,
    ExpectedEvidence,
    ExpectedFinding,
    ExpectedInvoiceLineRef,
    ExpectedSupportingQuote,
    ModelCallLogEntry,
    ModelConfig,
    ScenarioAnswerKey,
)
from invoiceguardian.schemas.runtime import (
    AbsenceOfAuthorizationEvidence,
    AbsenceQuote,
    ActionType,
    AnalysisResult,
    ApprovalState,
    ComputedTotalEvidence,
    DraftedAction,
    EvidenceReference,
    ExceptionFinding,
    ExceptionType,
    ExtractedFactRecord,
    FindingDisposition,
    InvoiceDisposition,
    InvoiceLineEvidence,
    ModelCallRecord,
    OperationalTrace,
    RunVersions,
    SearchedSection,
    SupportingQuoteEvidence,
)

MSA_DOCUMENT_ID = "MSA-2026-014"
SOW_DOCUMENT_ID = "SOW-2026-03"

_INVOICE_DISPOSITION = {
    "CLEAN": InvoiceDisposition.CLEAN,
    "EXCEPTIONS_FOUND": InvoiceDisposition.EXCEPTIONS_FOUND,
    "ESCALATION_REQUIRED": InvoiceDisposition.ESCALATION_REQUIRED,
}


def expected_evidence_to_runtime(atom: ExpectedEvidence) -> EvidenceReference:
    if isinstance(atom, ExpectedSupportingQuote):
        return SupportingQuoteEvidence(
            document_id=atom.document_id,
            section=atom.section,
            page=atom.page,
            quote=atom.quote,
        )
    if isinstance(atom, ExpectedInvoiceLineRef):
        return InvoiceLineEvidence(document_id=atom.document_id, line_id=atom.line_id)
    if isinstance(atom, ExpectedComputedTotal):
        return ComputedTotalEvidence(
            document_id=atom.document_id, value_cad=Decimal(atom.value_cad)
        )
    if isinstance(atom, ExpectedAbsenceOfAuthorization):
        return AbsenceOfAuthorizationEvidence(
            searched=[
                SearchedSection(document_id=s.document_id, sections=list(s.sections))
                for s in atom.searched
            ],
            quotes=[
                AbsenceQuote(
                    document_id=q.document_id, section=q.section, page=q.page, quote=q.quote
                )
                for q in atom.quotes
            ],
            statement=atom.statement,
        )
    raise TypeError(f"unhandled expected-evidence atom: {type(atom)!r}")


def expected_finding_to_runtime(finding: ExpectedFinding) -> ExceptionFinding:
    computed = (
        {k: Decimal(v) for k, v in finding.expected_values.items()}
        if finding.expected_values
        else None
    )
    return ExceptionFinding(
        finding_type=ExceptionType(finding.finding_type),
        basis=finding.basis,
        scope=finding.scope,
        invoice_line_id=finding.invoice_line_id,
        disposition=FindingDisposition(finding.expected_disposition),
        action=ActionType(finding.expected_action),
        evidence=[expected_evidence_to_runtime(a) for a in finding.evidence],
        computed_values=computed,
    )


def perfect_extracted_facts(
    dataset: EvaluationDataset, invoice_id: str
) -> list[ExtractedFactRecord]:
    """Manifest-perfect extracted facts for MSA + SOW + one invoice, taken
    straight from the answer-key manifest expected values."""
    wanted = {MSA_DOCUMENT_ID, SOW_DOCUMENT_ID, invoice_id}
    return [
        ExtractedFactRecord(
            document_id=entry.document_id, field=entry.field, value=str(entry.expected)
        )
        for entry in dataset.extraction_manifest
        if entry.document_id in wanted
    ]


def _approval_state(disposition: InvoiceDisposition) -> ApprovalState:
    if disposition is InvoiceDisposition.CLEAN:
        return ApprovalState.NO_ACTION_REQUIRED
    return ApprovalState.AWAITING_REVIEW


def build_perfect_result(
    dataset: EvaluationDataset,
    scenario: ScenarioAnswerKey,
    *,
    findings: list[ExceptionFinding] | None = None,
    extracted_facts: list[ExtractedFactRecord] | None = None,
) -> AnalysisResult:
    """A perfect AnalysisResult for one scenario. `findings`/`extracted_facts`
    overrides let tests inject deliberately-wrong predictions."""
    if findings is None:
        findings = [expected_finding_to_runtime(f) for f in scenario.expected_findings]
    disposition = _INVOICE_DISPOSITION[scenario.expected_invoice_disposition]
    approval_state = _approval_state(disposition)

    if extracted_facts is None:
        extracted_facts = perfect_extracted_facts(dataset, scenario.invoice_id)

    trace = OperationalTrace(
        invoice_id=scenario.invoice_id,
        versions=RunVersions(
            dataset_version=dataset.dataset_version,
            schema_version=dataset.schema_version,
            prompt_version="v1",
        ),
        input_document_ids=[MSA_DOCUMENT_ID, SOW_DOCUMENT_ID, scenario.invoice_id],
        extracted_facts=extracted_facts,
        deterministic_rules=[],
        model_calls=[
            ModelCallRecord(
                model_id="claude-sonnet-5",
                effort=None,
                purpose="INVOICE_EXTRACTION",
                schema_valid=True,
            )
        ],
        findings=findings,
        disposition=disposition,
        approval_state=approval_state,
    )

    drafted = (
        DraftedAction(action_type=findings[0].action, summary="draft; no communication sent")
        if findings
        else None
    )
    exception_line_ids = {f.invoice_line_id for f in findings}
    clean_line_ids = [
        line.line_id for line in scenario.invoice_lines if line.line_id not in exception_line_ids
    ]

    return AnalysisResult(
        invoice_id=scenario.invoice_id,
        disposition=disposition,
        findings=findings,
        clean_line_ids=clean_line_ids,
        approval_state=approval_state,
        drafted_action=drafted,
        trace=trace,
    )


def build_model_call_log(
    invoice_ids: list[str],
    *,
    first_pass_valid: bool = True,
    final_valid: bool = True,
    retry_count: int = 0,
    latency_ms: float = 1000.0,
) -> list[ModelCallLogEntry]:
    """MSA + SOW (shared) + one invoice op each — the run's operation log."""

    def entry(operation: str) -> ModelCallLogEntry:
        return ModelCallLogEntry(
            operation=operation,
            schema_valid_first_pass=first_pass_valid,
            retry_count=retry_count,
            schema_valid_final=final_valid,
            latency_ms=latency_ms,
            input_tokens=2000,
            output_tokens=500,
        )

    ops = [entry("MSA_EXTRACTION"), entry("SOW_EXTRACTION")]
    ops.extend(entry(f"INVOICE_EXTRACTION:{invoice_id}") for invoice_id in invoice_ids)
    return ops


def build_model_call_log_from_results(
    results: list[AnalysisResult],
) -> list[ModelCallLogEntry]:
    """Derive a run's required-operation log from real AnalysisResults' traces.

    Shared-document extractions (MSA, SOW) repeat across each invoice's trace
    and are deduped to one entry each; invoice extractions and semantic
    comparisons carry per-invoice / per-line operation identities. Latency and
    tokens are left at zero — capturing those into the log is step-9 wiring.
    """
    entries: list[ModelCallLogEntry] = []
    seen_shared: set[str] = set()
    for result in results:
        for call in result.trace.model_calls:
            purpose = call.purpose
            if purpose in ("MSA_EXTRACTION", "SOW_EXTRACTION"):
                if purpose in seen_shared:
                    continue
                seen_shared.add(purpose)
                operation = purpose
            elif purpose == "INVOICE_EXTRACTION":
                operation = f"INVOICE_EXTRACTION:{result.invoice_id}"
            else:  # already a distinct identity, e.g. SEMANTIC_COMPARISON:<inv>-<line>
                operation = purpose
            entries.append(
                ModelCallLogEntry(
                    operation=operation,
                    schema_valid_first_pass=call.schema_valid,
                    retry_count=1 if call.retried else 0,
                    schema_valid_final=call.schema_valid,
                    latency_ms=0.0,
                    input_tokens=0,
                    output_tokens=0,
                )
            )
    return entries


def build_run(
    dataset: EvaluationDataset,
    *,
    run_id: str = "run-1",
    results: list[AnalysisResult],
    model_call_log: list[ModelCallLogEntry] | None = None,
    replicate_index: int = 0,
) -> BenchmarkRun:
    if model_call_log is None:
        model_call_log = build_model_call_log([r.invoice_id for r in results])
    return BenchmarkRun(
        run_id=run_id,
        phase="A",
        arm_label="claude-sonnet-5",
        model=ModelConfig(
            model_id="claude-sonnet-5", effort="high", thinking_mode="adaptive", temperature=None
        ),
        prompt_version="v1",
        prompt_hash="test-hash",
        dataset_version=dataset.dataset_version,
        answer_key_schema_version=dataset.schema_version,
        replicate_index=replicate_index,
        timestamp=datetime(2026, 7, 15, 12, 0, 0),
        analysis_results=results,
        model_call_log=model_call_log,
    )


def perfect_run(
    dataset: EvaluationDataset,
    *,
    run_id: str = "run-perfect",
    scenario_ids: list[str] | None = None,
) -> BenchmarkRun:
    """A full-dataset run where every scenario is scored exactly per the
    answer key — the reference 'perfect arm'."""
    scenarios = dataset.scenarios
    if scenario_ids is not None:
        scenarios = [s for s in scenarios if s.scenario_id in scenario_ids]
    results = [build_perfect_result(dataset, s) for s in scenarios]
    return build_run(dataset, run_id=run_id, results=results)
