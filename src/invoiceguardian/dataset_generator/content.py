"""Loads the machine-readable content the generator renders into PDFs.

Invoice line items, dates, totals, and shared-document facts (parties,
effective dates) come from `answer_keys.json` — already exact-value-correct
and derived line-for-line from scenario-spec.md §4 — rather than being
re-transcribed from the spec's prose a second time.
"""

from __future__ import annotations

import json
from pathlib import Path

from invoiceguardian.schemas.evaluation import EvaluationDataset

DEFAULT_ANSWER_KEYS_PATH = Path(__file__).resolve().parents[3] / "answer_keys.json"

MSA_DOCUMENT_ID = "MSA-2026-014"
SOW_DOCUMENT_ID = "SOW-2026-03"


def load_answer_keys(path: Path = DEFAULT_ANSWER_KEYS_PATH) -> EvaluationDataset:
    return EvaluationDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))


def msa_parties(dataset: EvaluationDataset) -> tuple[str, str]:
    """Returns (client, vendor), matching scenario-spec.md §2's cast table."""
    parties = dataset.documents[MSA_DOCUMENT_ID].parties
    if parties is None or len(parties) != 2:
        raise ValueError(f"expected exactly 2 parties on {MSA_DOCUMENT_ID}, got {parties!r}")
    client, vendor = parties
    return client, vendor
