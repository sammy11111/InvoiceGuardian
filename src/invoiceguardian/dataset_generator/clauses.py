"""Canonical clause loader.

Per scenario-spec.md design rule §1.1: "evidence quotes may only come from
the Canonical Clauses in §3 — verbatim, character-for-character." This
module parses those clauses directly out of scenario-spec.md §3.1/§3.2
rather than hand-transcribing them, so there is exactly one physical source
of truth and no transcription-drift risk between the generator and the
eventual evidence-citation logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from invoiceguardian.schemas.runtime import ServiceRole

DEFAULT_SPEC_PATH = Path(__file__).resolve().parents[3] / "scenario-spec.md"

_QUOTE_RE = re.compile(r'"([^"]*)"')
_ROLE_ORDER = (ServiceRole.SENIOR_CONSULTANT, ServiceRole.CONSULTANT, ServiceRole.PROJECT_MANAGER)


@dataclass(frozen=True)
class ContractClauses:
    rate_card: dict[ServiceRole, str]
    monthly_cap: str
    required_reference: str
    authorization_principle: str
    term: str


@dataclass(frozen=True)
class SowClauses:
    scope: str
    role_hour_limits: dict[ServiceRole, str]
    period: str


def _section(markdown: str, start_heading: str, end_heading: str) -> str:
    start = markdown.index(start_heading)
    end = markdown.index(end_heading, start)
    return markdown[start:end]


def _quotes_after(section: str, label_pattern: str, count: int) -> list[str]:
    """Return the `count` quoted strings that follow the bullet labelled
    `label_pattern` (either inline on that bullet or on the indented
    sub-bullets immediately beneath it)."""
    match = re.search(label_pattern, section)
    if match is None:
        raise ValueError(f"canonical clause label not found in spec: {label_pattern!r}")
    quotes = _QUOTE_RE.findall(section[match.end() :])
    if len(quotes) < count:
        raise ValueError(f"expected {count} quotes after {label_pattern!r}, found {len(quotes)}")
    return quotes[:count]


def load_contract_clauses(spec_path: Path = DEFAULT_SPEC_PATH) -> ContractClauses:
    markdown = spec_path.read_text(encoding="utf-8")
    section = _section(markdown, "### 3.1 Contract", "### 3.2 SOW")

    rate_quotes = _quotes_after(section, r"§4\.1 \(rate card\)", 3)
    (monthly_cap,) = _quotes_after(section, r"§4\.3 \(monthly cap\)", 1)
    (required_reference,) = _quotes_after(section, r"§5\.2 \(required reference\)", 1)
    (authorization_principle,) = _quotes_after(section, r"§2\.1 \(authorization principle\)", 1)
    (term,) = _quotes_after(section, r"§1\.2 \(term\)", 1)

    return ContractClauses(
        rate_card=dict(zip(_ROLE_ORDER, rate_quotes, strict=True)),
        monthly_cap=monthly_cap,
        required_reference=required_reference,
        authorization_principle=authorization_principle,
        term=term,
    )


def load_sow_clauses(spec_path: Path = DEFAULT_SPEC_PATH) -> SowClauses:
    markdown = spec_path.read_text(encoding="utf-8")
    section = _section(markdown, "### 3.2 SOW", "### 3.3 Invoice layout")

    (scope,) = _quotes_after(section, r"§2 \(scope\)", 1)
    role_quotes = _quotes_after(section, r"§3 \(roles and monthly limits\)", 3)
    (period,) = _quotes_after(section, r"§4 \(period\)", 1)

    return SowClauses(
        scope=scope,
        role_hour_limits=dict(zip(_ROLE_ORDER, role_quotes, strict=True)),
        period=period,
    )
