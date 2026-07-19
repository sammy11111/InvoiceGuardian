"""Exports pre-computed view JSON for the frontend's static build.

The Next.js static export reads these files directly at build time (Node
`fs`, no HTTP round trip) rather than reimplementing the view-projection
logic in TypeScript — `api.view`'s `build_scenario_summary` /
`build_scenario_detail` are the single implementation; FastAPI's live
`/api/scenarios` endpoints compute from the same functions. This module
just writes their output to disk alongside the raw `AnalysisResult`s.
"""

from __future__ import annotations

import json
from pathlib import Path

from invoiceguardian.analyze.persist import (
    ALL_INVOICE_IDS,
    DEFAULT_RESULTS_DIR,
    load_persisted_result,
)
from invoiceguardian.api.view import build_scenario_detail, build_scenario_summary

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_VIEWS_DIR = REPO_ROOT / "data" / "scenario_views"


def persist_all_views(
    output_dir: Path = DEFAULT_VIEWS_DIR,
    results_dir: Path = DEFAULT_RESULTS_DIR,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    summaries = []
    for invoice_id in ALL_INVOICE_IDS:
        result = load_persisted_result(invoice_id, results_dir)
        detail = build_scenario_detail(result)
        summaries.append(build_scenario_summary(result))

        detail_path = output_dir / f"{invoice_id}.json"
        detail_path.write_text(detail.model_dump_json(indent=2) + "\n", encoding="utf-8")
        paths.append(detail_path)

    index_path = output_dir / "_index.json"
    index_payload = [json.loads(s.model_dump_json()) for s in summaries]
    index_path.write_text(json.dumps(index_payload, indent=2) + "\n", encoding="utf-8")
    paths.append(index_path)
    return paths


__all__ = ["DEFAULT_VIEWS_DIR", "persist_all_views"]
