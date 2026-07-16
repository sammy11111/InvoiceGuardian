"""Finding matching, preregistered in SCORING.md — implemented exactly.

- Match key: (finding_type, scope, invoice_line_id); invoice-scope findings
  carry invoice_line_id = None.
- 1:1 within a scenario: a predicted finding matches at most one expected
  finding and vice versa (greedy, in predicted order).
- Unmatched predicted findings are false positives (this includes any
  finding on a clean scenario/line, wrong-type findings, and duplicate
  matches beyond the first).
- Unmatched expected findings are false negatives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from invoiceguardian.schemas.evaluation import ExpectedFinding
from invoiceguardian.schemas.runtime import ExceptionFinding

MatchKey = tuple[str, str, str | None]


def predicted_key(finding: ExceptionFinding, invoice_id: str) -> MatchKey:
    # SCORING.md: (finding_type, scope, invoice_line_id) for line-scope
    # findings; invoice-scope findings match on (finding_type, scope,
    # invoice_id) with invoice_line_id = null.
    discriminator = finding.invoice_line_id if finding.scope == "line" else invoice_id
    return (finding.finding_type.value, finding.scope, discriminator)


def expected_key(finding: ExpectedFinding, invoice_id: str) -> MatchKey:
    discriminator = finding.invoice_line_id if finding.scope == "line" else invoice_id
    return (finding.finding_type, finding.scope, discriminator)


@dataclass(frozen=True)
class MatchedPair:
    predicted: ExceptionFinding
    expected: ExpectedFinding


@dataclass(frozen=True)
class ScenarioMatch:
    scenario_id: str
    invoice_id: str
    matched: list[MatchedPair] = field(default_factory=list)
    false_positives: list[ExceptionFinding] = field(default_factory=list)
    false_negatives: list[ExpectedFinding] = field(default_factory=list)


def match_scenario(
    scenario_id: str,
    invoice_id: str,
    predicted: list[ExceptionFinding],
    expected: list[ExpectedFinding],
) -> ScenarioMatch:
    used_expected: set[int] = set()
    matched: list[MatchedPair] = []
    false_positives: list[ExceptionFinding] = []

    for pred in predicted:
        pkey = predicted_key(pred, invoice_id)
        match_index: int | None = None
        for index, exp in enumerate(expected):
            if index in used_expected:
                continue
            if expected_key(exp, invoice_id) == pkey:
                match_index = index
                break
        if match_index is None:
            false_positives.append(pred)
        else:
            used_expected.add(match_index)
            matched.append(MatchedPair(predicted=pred, expected=expected[match_index]))

    false_negatives = [exp for index, exp in enumerate(expected) if index not in used_expected]

    return ScenarioMatch(
        scenario_id=scenario_id,
        invoice_id=invoice_id,
        matched=matched,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )
