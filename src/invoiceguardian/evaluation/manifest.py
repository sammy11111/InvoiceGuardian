"""Extraction accuracy over the 106-field manifest.

Per SCORING.md/answer_keys.json: whitespace-collapsed exact matches over the
manifest ÷ 106, using each field's declared normalization rule. Extracted
values are read from `OperationalTrace.extracted_facts` (keyed by
document_id + field), which the pipeline populates with exactly the manifest
field names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from invoiceguardian.schemas.evaluation import EvaluationDataset
from invoiceguardian.schemas.runtime import AnalysisResult


def _collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _matches(normalization: str, extracted: str, expected: str) -> bool:
    """Applies a manifest field's normalization rule, then compares."""
    try:
        if normalization == "iso_date":
            from datetime import date

            return date.fromisoformat(extracted.strip()) == date.fromisoformat(expected.strip())
        if normalization == "decimal_2dp":
            cents = Decimal("0.01")
            return Decimal(extracted).quantize(cents) == Decimal(expected).quantize(cents)
        if normalization == "iso_currency":
            return extracted.strip().upper() == expected.strip().upper()
        if normalization == "integer":
            return int(extracted.strip()) == int(expected.strip())
        if normalization == "identifier_trim":
            return extracted.strip() == expected.strip()
        if normalization in ("whitespace_collapse", "whitespace_collapse_exact"):
            return _collapse(extracted) == _collapse(expected)
    except (ValueError, InvalidOperation):
        return False
    raise ValueError(f"unknown normalization rule: {normalization!r}")


@dataclass(frozen=True)
class FieldResult:
    document_id: str
    field: str
    covered: bool
    correct: bool


@dataclass(frozen=True)
class ExtractionScore:
    correct: int
    manifest_total: int  # always 106 for dataset v1.3
    covered: int  # manifest fields whose document appears in the run
    field_results: tuple[FieldResult, ...]

    @property
    def accuracy_over_manifest(self) -> float:
        """The official SCORING.md metric: correct ÷ 106."""
        return self.correct / self.manifest_total if self.manifest_total else 0.0

    @property
    def accuracy_over_covered(self) -> float:
        """Correct ÷ covered — the honest score for a partial run that does
        not include all six invoices (e.g. an S1/S6-only mechanism run)."""
        return self.correct / self.covered if self.covered else 0.0


def _facts_lookup(analysis_results: list[AnalysisResult]) -> dict[tuple[str, str], str]:
    """Builds a (document_id, field) -> value map from every run trace.

    The MSA/SOW facts repeat across each invoice's trace; later writes of the
    same key simply overwrite with an identical value.
    """
    lookup: dict[tuple[str, str], str] = {}
    for result in analysis_results:
        for fact in result.trace.extracted_facts:
            lookup[(fact.document_id, fact.field)] = fact.value
    return lookup


def score_extraction(
    dataset: EvaluationDataset, analysis_results: list[AnalysisResult]
) -> ExtractionScore:
    lookup = _facts_lookup(analysis_results)
    present_documents = {doc for doc, _field in lookup}

    correct = 0
    covered = 0
    field_results: list[FieldResult] = []
    for entry in dataset.extraction_manifest:
        key = (entry.document_id, entry.field)
        is_covered = entry.document_id in present_documents
        extracted = lookup.get(key)
        is_correct = extracted is not None and _matches(
            entry.normalization, extracted, str(entry.expected)
        )
        if is_covered:
            covered += 1
        if is_correct:
            correct += 1
        field_results.append(
            FieldResult(
                document_id=entry.document_id,
                field=entry.field,
                covered=is_covered,
                correct=is_correct,
            )
        )

    return ExtractionScore(
        correct=correct,
        manifest_total=dataset.extraction_field_count,
        covered=covered,
        field_results=tuple(field_results),
    )
