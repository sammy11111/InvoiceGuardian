"""Boot smoke test for the FastAPI serving layer (build step 7): the app
starts and the scenario list renders from the persisted JSON files — no
live model calls involved."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from invoiceguardian.analyze.persist import persisted_results_exist
from invoiceguardian.api.app import app

pytestmark = pytest.mark.skipif(
    not persisted_results_exist(),
    reason="scenario runs not persisted; run `python -m invoiceguardian.analyze --all --persist`",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_scenarios_returns_all_six(client: TestClient) -> None:
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 6
    assert {s["scenario_label"] for s in body} == {"S1", "S2", "S3", "S4", "S5", "S6"}


def test_get_scenario_detail_matches_summary(client: TestClient) -> None:
    response = client.get("/api/scenarios/INV-2026-061")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["invoice_id"] == "INV-2026-061"
    assert body["summary"]["scenario_label"] == "S1"
    assert len(body["lines"]) == 2


def test_get_unknown_scenario_is_404(client: TestClient) -> None:
    response = client.get("/api/scenarios/INV-2026-099")
    assert response.status_code == 404


def test_s5_invoice_level_finding_has_no_line_id(client: TestClient) -> None:
    response = client.get("/api/scenarios/INV-2026-065")
    body = response.json()
    assert len(body["invoice_level_findings"]) == 1
    assert body["invoice_level_findings"][0]["invoice_line_id"] is None
    assert all(line["status"] == "clean" for line in body["lines"])
