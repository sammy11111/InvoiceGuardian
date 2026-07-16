"""Exact-prefix role resolution — ordinary code, not semantic matching.

Only resolves an invoice line description that literally starts with a
known role label (e.g. "Senior Consultant — ..."). Paraphrases ("Sr.
Consulting Services"), unrelated services ("Architecture Workshop
Facilitation"), and near-matches ("ERP Rollout Advisory Support") are left
unresolved (`None`) for the bounded semantic matching step, which is not
part of this deterministic check.
"""

from __future__ import annotations

from invoiceguardian.schemas.runtime import ServiceRole

ROLE_LABELS: dict[ServiceRole, str] = {
    ServiceRole.SENIOR_CONSULTANT: "Senior Consultant",
    ServiceRole.CONSULTANT: "Consultant",
    ServiceRole.PROJECT_MANAGER: "Project Manager",
}


def match_role_exact(description: str) -> ServiceRole | None:
    stripped = description.strip()
    for role, label in ROLE_LABELS.items():
        if stripped.startswith(label):
            return role
    return None
