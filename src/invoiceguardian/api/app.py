"""FastAPI serving layer for the review UI.

Serves the six persisted, canned scenario runs (LIMITATIONS.md: no
arbitrary PDF upload, no live LLM calls from the UI). Reads flat JSON files
written by `python -m invoiceguardian.analyze --all --persist` — never
calls the model. If a build of the Next.js static export exists, it is
mounted at `/` so the whole app is servable as one process (single
deployable unit, CLAUDE.md).

The static export is looked up in two places: repo-root `static/` (the
committed deployment artifact — see scripts/build_static_export.sh; the
deploy platform never needs Node, only Python) or `frontend/out/` (the raw
local `npm run build` output, for local single-process testing without
running the copy step).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from invoiceguardian.analyze.persist import (
    ALL_INVOICE_IDS,
    DEFAULT_RESULTS_DIR,
    load_persisted_result,
)
from invoiceguardian.api.middleware import RateLimitMiddleware, RequestSizeLimitMiddleware
from invoiceguardian.api.view import (
    ScenarioDetail,
    ScenarioSummary,
    build_scenario_detail,
    build_scenario_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
_STATIC_CANDIDATES = [REPO_ROOT / "static", REPO_ROOT / "frontend" / "out"]
FRONTEND_EXPORT_DIR = next((p for p in _STATIC_CANDIDATES if p.exists()), None)

app = FastAPI(title="InvoiceGuardian", version="0.1.0")

# Public-demo protections (CLAUDE.md): small request-size limits + basic
# rate limiting. Order matters — Starlette applies middleware in reverse
# registration order, so the size check runs before the rate-limit counter
# is incremented.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)

# Dev-only: `next dev` runs on a different origin than `uvicorn`. In the
# single-deployable-unit production wiring (static export mounted below),
# everything is same-origin and CORS is a no-op.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/scenarios")
def list_scenarios(results_dir: Path = DEFAULT_RESULTS_DIR) -> list[ScenarioSummary]:
    try:
        results = [load_persisted_result(i, results_dir) for i in ALL_INVOICE_IDS]
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Scenario runs not persisted yet: {exc}",
        ) from exc
    return [build_scenario_summary(r) for r in results]


@app.get("/api/scenarios/{invoice_id}")
def get_scenario(invoice_id: str, results_dir: Path = DEFAULT_RESULTS_DIR) -> ScenarioDetail:
    if invoice_id not in ALL_INVOICE_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {invoice_id}")
    try:
        result = load_persisted_result(invoice_id, results_dir)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Scenario run not persisted yet: {exc}",
        ) from exc
    return build_scenario_detail(result)


if FRONTEND_EXPORT_DIR is not None:
    app.mount("/", StaticFiles(directory=FRONTEND_EXPORT_DIR, html=True), name="frontend")
