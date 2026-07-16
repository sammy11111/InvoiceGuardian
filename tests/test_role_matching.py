import pytest

from invoiceguardian.checks.role_matching import match_role_exact
from invoiceguardian.schemas.runtime import ServiceRole


@pytest.mark.parametrize(
    ("description", "expected_role"),
    [
        ("Senior Consultant — ERP implementation support", ServiceRole.SENIOR_CONSULTANT),
        ("Consultant — data migration validation", ServiceRole.CONSULTANT),
        ("Project Manager — oversight", ServiceRole.PROJECT_MANAGER),
    ],
)
def test_match_role_exact_resolves_known_role_prefixes(description, expected_role) -> None:
    assert match_role_exact(description) == expected_role


@pytest.mark.parametrize(
    "description",
    [
        "Architecture Workshop Facilitation",  # S2: unauthorized, no role prefix
        "Sr. Consulting Services — ERP implementation",  # S3: paraphrase, not exact
        "ERP Rollout Advisory Support",  # S4: near-match, deliberately ambiguous
    ],
)
def test_match_role_exact_leaves_non_exact_descriptions_unresolved(description) -> None:
    assert match_role_exact(description) is None
