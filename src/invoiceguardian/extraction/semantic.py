"""The bounded semantic-comparison operation (one model call per unresolved
invoice line).

This is the architecture's single semantic component. It performs a
schema-constrained three-way classification (EQUIVALENT / NOT_AUTHORIZED /
AMBIGUOUS) of a line description against the cached authorized-scope
material — not free reasoning. The deterministic layer (checks.semantic)
turns the classification into a finding; the model never writes evidence
structures.
"""

from __future__ import annotations

from invoiceguardian.checks.role_matching import ROLE_LABELS
from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL, call_tool_validated
from invoiceguardian.extraction.json_schema_utils import resolve_refs
from invoiceguardian.extraction.prompts import SEMANTIC_COMPARISON_SYSTEM_PROMPT
from invoiceguardian.extraction.raw_schemas import RawSemanticClassification
from invoiceguardian.schemas.runtime import ContractTerms, ModelCallRecord, StatementOfWork

_SEMANTIC_SCHEMA = resolve_refs(RawSemanticClassification.model_json_schema())


def semantic_operation_id(invoice_id: str, line_id: str) -> str:
    """Distinct operation identity for the manifest / operation log."""
    return f"SEMANTIC_COMPARISON:{invoice_id}-{line_id}"


def _scope_material(contract: ContractTerms, sow: StatementOfWork) -> str:
    roles = "\n".join(f"- {ROLE_LABELS[entry.role]}" for entry in sow.monthly_hour_limits)
    return (
        "[Statement of Work — Scope of services]\n"
        f"{sow.scope.text}\n\n"
        "[Statement of Work — Authorized roles]\n"
        f"{roles}\n\n"
        "[Master Services Agreement — Authorization principle]\n"
        f"{contract.authorization_principle.text}"
    )


def classify_line(
    description: str,
    contract: ContractTerms,
    sow: StatementOfWork,
    *,
    invoice_id: str,
    line_id: str,
    model: str = DEFAULT_MODEL,
) -> tuple[RawSemanticClassification, ModelCallRecord]:
    user_content = f'Invoice line description:\n"{description}"\n\n{_scope_material(contract, sow)}'
    raw, retried, _input_tokens, _output_tokens = call_tool_validated(
        model=model,
        system=SEMANTIC_COMPARISON_SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="classify_service_authorization",
        tool_description=(
            "Record the three-way authorization classification for one invoice line "
            "description against the supplied authorized-scope material."
        ),
        input_schema=_SEMANTIC_SCHEMA,
        raw_model=RawSemanticClassification,
    )
    record = ModelCallRecord(
        model_id=model,
        effort=None,
        purpose=semantic_operation_id(invoice_id, line_id),
        schema_valid=True,
        retried=retried,
    )
    return raw, record
