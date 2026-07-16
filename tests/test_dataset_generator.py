"""Tests for the document generator (build order step 2).

Proves the mechanism the evaluator's exact-quote matching depends on: every
canonical clause from scenario-spec.md §3 survives PDF rendering and
pdfplumber extraction, whitespace-normalized, verbatim. Also proves every
invoice's numbers round-trip exactly against answer_keys.json.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber
import pytest

from invoiceguardian.dataset_generator.clauses import (
    DEFAULT_SPEC_PATH,
    load_contract_clauses,
    load_sow_clauses,
)
from invoiceguardian.dataset_generator.content import (
    DEFAULT_ANSWER_KEYS_PATH,
    load_answer_keys,
    msa_parties,
)
from invoiceguardian.dataset_generator.generate import generate_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_all_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return _normalize("\n".join(page.extract_text() or "" for page in pdf.pages))


def _page_texts(pdf_path: Path) -> list[str]:
    with pdfplumber.open(pdf_path) as pdf:
        return [_normalize(page.extract_text() or "") for page in pdf.pages]


@pytest.fixture(scope="module")
def generated_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("dataset_pdfs")
    generate_dataset(output_dir=output_dir)
    return output_dir


@pytest.fixture(scope="module")
def contract_clauses():
    return load_contract_clauses()


@pytest.fixture(scope="module")
def sow_clauses():
    return load_sow_clauses()


@pytest.fixture(scope="module")
def dataset():
    return load_answer_keys()


# --- Clause loader fidelity (independent of the generator itself) ----------


def test_contract_clauses_are_present_verbatim_in_the_spec_file(contract_clauses) -> None:
    spec_text = DEFAULT_SPEC_PATH.read_text(encoding="utf-8")
    for quote in contract_clauses.rate_card.values():
        assert f'"{quote}"' in spec_text
    for quote in (
        contract_clauses.monthly_cap,
        contract_clauses.required_reference,
        contract_clauses.authorization_principle,
        contract_clauses.term,
    ):
        assert f'"{quote}"' in spec_text


def test_sow_clauses_are_present_verbatim_in_the_spec_file(sow_clauses) -> None:
    spec_text = DEFAULT_SPEC_PATH.read_text(encoding="utf-8")
    assert f'"{sow_clauses.scope}"' in spec_text
    assert f'"{sow_clauses.period}"' in spec_text
    for quote in sow_clauses.role_hour_limits.values():
        assert f'"{quote}"' in spec_text


def test_contract_clauses_match_answer_keys_where_answer_keys_quotes_them(
    contract_clauses, dataset
) -> None:
    s1_quote = dataset.scenarios[0].expected_findings[0].evidence[0].quote
    assert s1_quote == contract_clauses.rate_card[next(iter(contract_clauses.rate_card))]

    s5 = next(s for s in dataset.scenarios if s.scenario_id == "S5")
    cap_quote = next(e for e in s5.expected_findings[0].evidence if e.kind == "supporting_quote")
    assert cap_quote.quote == contract_clauses.monthly_cap


def test_sow_scope_matches_answer_keys_extraction_manifest(sow_clauses, dataset) -> None:
    manifest_entry = next(
        e
        for e in dataset.extraction_manifest
        if e.field == "scope_text" and e.document_id == "SOW-2026-03"
    )
    assert manifest_entry.expected == sow_clauses.scope


# --- MSA / SOW PDF: canonical clause fidelity through rendering + extraction


def test_msa_pdf_contains_every_canonical_clause_verbatim(generated_dir, contract_clauses) -> None:
    text = _extract_all_text(generated_dir / "MSA-2026-014.pdf")
    for quote in contract_clauses.rate_card.values():
        assert quote in text
    assert contract_clauses.monthly_cap in text
    assert contract_clauses.required_reference in text
    assert contract_clauses.authorization_principle in text
    assert contract_clauses.term in text


def test_sow_pdf_contains_every_canonical_clause_verbatim(generated_dir, sow_clauses) -> None:
    text = _extract_all_text(generated_dir / "SOW-2026-03.pdf")
    assert sow_clauses.scope in text
    assert sow_clauses.period in text
    for quote in sow_clauses.role_hour_limits.values():
        assert quote in text


def test_msa_pdf_follows_the_section_3_4_page_target_guide(generated_dir) -> None:
    pages = _page_texts(generated_dir / "MSA-2026-014.pdf")
    assert len(pages) == 3
    assert "Section 1" in pages[0] and "Section 2" in pages[0]
    assert "Section 4" in pages[1]
    assert "Section 5" in pages[2]


def test_sow_pdf_follows_the_section_3_4_page_target_guide(generated_dir) -> None:
    pages = _page_texts(generated_dir / "SOW-2026-03.pdf")
    assert len(pages) == 2
    assert "Section 2" in pages[0] and "Section 3" in pages[0]
    assert "Section 4" in pages[1]


# --- Invoices: numeric/line-item fidelity against answer_keys.json ---------


@pytest.mark.parametrize("scenario_id", ["S1", "S2", "S3", "S4", "S5", "S6"])
def test_invoice_pdf_matches_answer_key_exactly(generated_dir, dataset, scenario_id) -> None:
    scenario = next(s for s in dataset.scenarios if s.scenario_id == scenario_id)
    pdf_path = generated_dir / f"{scenario.invoice_id}.pdf"
    assert pdf_path.exists()

    pages = _page_texts(pdf_path)
    assert len(pages) == 1
    text = pages[0]

    assert scenario.invoice_id in text
    assert scenario.invoice_date.isoformat() in text
    assert scenario.service_period_start.isoformat() in text
    assert scenario.service_period_end.isoformat() in text
    assert scenario.sow_reference in text
    assert scenario.invoice_total_cad in text

    for line in scenario.invoice_lines:
        assert line.line_id in text
        assert _normalize(line.description) in text
        assert str(line.hours) in text
        assert line.rate_cad in text
        assert line.amount_cad in text


def test_invoice_pdfs_deliberately_include_unmapped_service_descriptions(generated_dir) -> None:
    """S2 and S4 line descriptions don't cleanly map to SOW scope by design
    (the trap the scenarios are built to test) — generate them as written."""
    s2_text = _extract_all_text(generated_dir / "INV-2026-062.pdf")
    assert "Architecture Workshop Facilitation" in s2_text

    s4_text = _extract_all_text(generated_dir / "INV-2026-064.pdf")
    assert "ERP Rollout Advisory Support" in s4_text


# --- Header content: vendor/client sourced from answer_keys.json documents -


def test_invoice_header_uses_answer_keys_parties(generated_dir, dataset) -> None:
    client, vendor = msa_parties(dataset)
    text = _extract_all_text(generated_dir / "INV-2026-061.pdf")
    assert f"Vendor: {vendor}" in text
    assert f"Client: {client}" in text


# --- Output filenames --------------------------------------------------------


def test_output_filenames_match_document_ids(generated_dir, dataset) -> None:
    expected = {"MSA-2026-014.pdf", "SOW-2026-03.pdf"} | {
        f"{s.invoice_id}.pdf" for s in dataset.scenarios
    }
    actual = {p.name for p in generated_dir.glob("*.pdf")}
    assert actual == expected


# --- Determinism -------------------------------------------------------------


def test_generation_is_deterministic_in_text_content(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    run1 = tmp_path_factory.mktemp("run1")
    run2 = tmp_path_factory.mktemp("run2")
    generate_dataset(output_dir=run1)
    generate_dataset(output_dir=run2)

    for pdf_path in sorted(run1.glob("*.pdf")):
        text1 = _extract_all_text(pdf_path)
        text2 = _extract_all_text(run2 / pdf_path.name)
        assert text1 == text2


def test_default_answer_keys_and_spec_paths_resolve_inside_repo() -> None:
    assert DEFAULT_SPEC_PATH == REPO_ROOT / "scenario-spec.md"
    assert DEFAULT_ANSWER_KEYS_PATH == REPO_ROOT / "answer_keys.json"
    assert DEFAULT_SPEC_PATH.exists()
    assert DEFAULT_ANSWER_KEYS_PATH.exists()
