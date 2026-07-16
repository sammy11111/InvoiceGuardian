"""Evidence atoms, grounding completeness, and the unsupported-finding
hard gate — preregistered in SCORING.md.

Minimum evidence-role set (hard gate) per finding type:
    RATE_MISMATCH          governing rate quote + invoice-line reference
    UNAUTHORIZED_SERVICE   governing scope/authorization evidence
                           + searched-section set with no-match statement
                           + invoice-line reference
    SCOPE_AMBIGUITY        governing scope quote + invoice-line reference
    AGGREGATE_CAP_EXCEEDED governing cap quote + computed invoice total

An invoice-line reference alone never satisfies a gate by itself. A quote
atom must exact-match a canonical clause (whitespace-normalized); a quote not
present in the supplied documents is a fabricated citation. Per design rule
§1.1, legitimate evidence quotes may come only from the canonical clauses,
so the canonical clause set is the authoritative "supplied-document" quote
surface for fabrication detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from invoiceguardian.dataset_generator.clauses import load_contract_clauses, load_sow_clauses
from invoiceguardian.schemas.evaluation import (
    ExpectedAbsenceOfAuthorization,
    ExpectedComputedTotal,
    ExpectedFinding,
    ExpectedInvoiceLineRef,
    ExpectedSupportingQuote,
)
from invoiceguardian.schemas.runtime import (
    AbsenceOfAuthorizationEvidence,
    ComputedTotalEvidence,
    ExceptionFinding,
    InvoiceLineEvidence,
    SupportingQuoteEvidence,
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def canonical_quote_set() -> frozenset[str]:
    """All canonical clauses (whitespace-normalized), the legitimate quote
    surface per design rule §1.1."""
    contract = load_contract_clauses()
    sow = load_sow_clauses()
    quotes = [
        *contract.rate_card.values(),
        contract.monthly_cap,
        contract.required_reference,
        contract.authorization_principle,
        contract.term,
        sow.scope,
        *sow.role_hour_limits.values(),
        sow.period,
    ]
    return frozenset(_collapse(q) for q in quotes)


def is_fabricated_quote(quote: str) -> bool:
    return _collapse(quote) not in canonical_quote_set()


# --- Fabrication (hard gate 1, applied to every finding) --------------------


def has_fabricated_citation(finding: ExceptionFinding) -> bool:
    """A quote (supporting or absence-of-authorization) not present in the
    supplied documents. Applied to every predicted finding, matched or not
    ("zero fabricated citations anywhere", SCORING.md)."""
    for e in finding.evidence:
        if isinstance(e, SupportingQuoteEvidence) and is_fabricated_quote(e.quote):
            return True
        if isinstance(e, AbsenceOfAuthorizationEvidence):
            if any(is_fabricated_quote(q.quote) for q in e.quotes):
                return True
    return False


# --- Evidence-atom satisfaction (grounding completeness + matched gate 1) ----
#
# An atom is satisfied only if it matches the answer key's atom including its
# source metadata: a supporting quote must match document_id + section +
# whitespace-collapsed quote text (page is observational — not part of
# SCORING.md's atom definition); an invoice-line reference must match
# document_id + line_id; a computed total must match document_id + exact
# Decimal value. This is what makes a RATE_MISMATCH citing the monthly-cap
# clause fail its governing-rate-quote atom rather than passing on any quote.


def _decimal_equal(a: str | Decimal, b: str | Decimal) -> bool:
    try:
        cents = Decimal("0.01")
        return Decimal(a).quantize(cents) == Decimal(b).quantize(cents)
    except InvalidOperation:
        return False


def _supporting_quote_satisfied(
    finding: ExceptionFinding, required: ExpectedSupportingQuote
) -> bool:
    target = _collapse(required.quote)
    return any(
        isinstance(e, SupportingQuoteEvidence)
        and e.document_id == required.document_id
        and e.section == required.section
        and _collapse(e.quote) == target
        and not is_fabricated_quote(e.quote)
        for e in finding.evidence
    )


def _invoice_line_satisfied(finding: ExceptionFinding, required: ExpectedInvoiceLineRef) -> bool:
    return any(
        isinstance(e, InvoiceLineEvidence)
        and e.document_id == required.document_id
        and e.line_id == required.line_id
        for e in finding.evidence
    )


def _computed_total_satisfied(finding: ExceptionFinding, required: ExpectedComputedTotal) -> bool:
    return any(
        isinstance(e, ComputedTotalEvidence)
        and e.document_id == required.document_id
        and _decimal_equal(e.value_cad, required.value_cad)
        for e in finding.evidence
    )


def _absence_satisfied(finding: ExceptionFinding, required: ExpectedAbsenceOfAuthorization) -> bool:
    required_sections = {(s.document_id, sec) for s in required.searched for sec in s.sections}
    required_quotes = {_collapse(q.quote) for q in required.quotes}
    for e in finding.evidence:
        if not isinstance(e, AbsenceOfAuthorizationEvidence):
            continue
        got_sections = {(s.document_id, sec) for s in e.searched for sec in s.sections}
        got_quotes = {_collapse(q.quote) for q in e.quotes}
        has_statement = bool(e.statement.strip())
        no_fabrication = all(not is_fabricated_quote(q.quote) for q in e.quotes)
        if (
            required_sections.issubset(got_sections)
            and required_quotes.issubset(got_quotes)
            and has_statement
            and no_fabrication
        ):
            return True
    return False


@dataclass(frozen=True)
class GroundingScore:
    """Per-matched-finding atom tally. The evaluator macro-averages these —
    each finding's own correct/required ratio, averaged over matched findings.
    Macro and micro (pooled atoms) coincide on dataset v1.3 because every
    matched finding has exactly 2 required atoms; they can diverge only once
    findings differ in atom count."""

    correct_atoms: int
    required_atoms: int

    @property
    def completeness(self) -> float:
        return self.correct_atoms / self.required_atoms if self.required_atoms else 1.0


def grounding_for_pair(predicted: ExceptionFinding, expected: ExpectedFinding) -> GroundingScore:
    """Correct required evidence atoms ÷ all required atoms for one matched
    finding. The answer key's evidence list defines the required atoms."""
    correct = 0
    total = 0
    for atom in expected.evidence:
        total += 1
        if isinstance(atom, ExpectedSupportingQuote):
            ok = _supporting_quote_satisfied(predicted, atom)
        elif isinstance(atom, ExpectedInvoiceLineRef):
            ok = _invoice_line_satisfied(predicted, atom)
        elif isinstance(atom, ExpectedComputedTotal):
            ok = _computed_total_satisfied(predicted, atom)
        elif isinstance(atom, ExpectedAbsenceOfAuthorization):
            ok = _absence_satisfied(predicted, atom)
        else:  # pragma: no cover - exhaustive over the discriminated union
            ok = False
        if ok:
            correct += 1
    return GroundingScore(correct_atoms=correct, required_atoms=total)


def matched_finding_is_supported(predicted: ExceptionFinding, expected: ExpectedFinding) -> bool:
    """Hard gate 1 for a matched finding: it must satisfy every required
    evidence atom the answer key defines (grounding completeness == 1.0) and
    carry no fabricated citation. This is stricter than a by-kind minimum —
    a RATE_MISMATCH that cites the monthly-cap clause instead of the governing
    rate quote fails here even though it does carry *a* supporting quote."""
    if has_fabricated_citation(predicted):
        return False
    return grounding_for_pair(predicted, expected).completeness == 1.0
