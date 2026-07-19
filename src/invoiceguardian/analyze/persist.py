"""Persists AnalysisResults for the six canned scenarios as flat JSON files.

The review UI reads these — it never calls the LLM live (LIMITATIONS.md /
CLAUDE.md's public-demo protections: canned synthetic scenarios only, no
live model calls from the UI, zero API-key exposure at view time). This
module is the one place that bridges "run the real pipeline" and "serve a
static build artifact."
"""

from __future__ import annotations

from pathlib import Path

from invoiceguardian.analyze import DEFAULT_PDF_DIR, run_analysis
from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL
from invoiceguardian.schemas.runtime import AnalysisResult

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = REPO_ROOT / "data" / "scenario_runs"

ALL_INVOICE_IDS = [
    "INV-2026-061",
    "INV-2026-062",
    "INV-2026-063",
    "INV-2026-064",
    "INV-2026-065",
    "INV-2026-066",
]


def persist_all_results(
    output_dir: Path = DEFAULT_RESULTS_DIR,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    model: str = DEFAULT_MODEL,
) -> list[Path]:
    """Runs the real pipeline on all six invoices and writes one JSON file
    per result. Regenerate with `python -m invoiceguardian.analyze --all
    --persist`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for invoice_id in ALL_INVOICE_IDS:
        result = run_analysis(invoice_id, pdf_dir=pdf_dir, model=model)
        path = output_dir / f"{invoice_id}.json"
        path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def load_persisted_result(
    invoice_id: str, results_dir: Path = DEFAULT_RESULTS_DIR
) -> AnalysisResult:
    path = results_dir / f"{invoice_id}.json"
    return AnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))


def load_all_persisted_results(results_dir: Path = DEFAULT_RESULTS_DIR) -> list[AnalysisResult]:
    return [load_persisted_result(invoice_id, results_dir) for invoice_id in ALL_INVOICE_IDS]


def persisted_results_exist(results_dir: Path = DEFAULT_RESULTS_DIR) -> bool:
    return all((results_dir / f"{invoice_id}.json").exists() for invoice_id in ALL_INVOICE_IDS)


def _raise_missing(results_dir: Path) -> None:
    missing = [i for i in ALL_INVOICE_IDS if not (results_dir / f"{i}.json").exists()]
    raise FileNotFoundError(
        f"missing persisted scenario runs in {results_dir}: {missing}. "
        "Regenerate with `python -m invoiceguardian.analyze --all --persist`."
    )


def require_persisted_results(results_dir: Path = DEFAULT_RESULTS_DIR) -> None:
    if not persisted_results_exist(results_dir):
        _raise_missing(results_dir)


__all__ = [
    "ALL_INVOICE_IDS",
    "DEFAULT_RESULTS_DIR",
    "load_all_persisted_results",
    "load_persisted_result",
    "persist_all_results",
    "persisted_results_exist",
    "require_persisted_results",
]
