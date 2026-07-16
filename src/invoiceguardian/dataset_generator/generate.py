"""Top-level orchestration: generates all 8 dataset PDFs into a directory."""

from __future__ import annotations

from pathlib import Path

from invoiceguardian.dataset_generator.clauses import (
    DEFAULT_SPEC_PATH,
    load_contract_clauses,
    load_sow_clauses,
)
from invoiceguardian.dataset_generator.content import (
    DEFAULT_ANSWER_KEYS_PATH,
    MSA_DOCUMENT_ID,
    SOW_DOCUMENT_ID,
    load_answer_keys,
    msa_parties,
)
from invoiceguardian.dataset_generator.pdf import build_invoice_pdf, build_msa_pdf, build_sow_pdf

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "dataset" / "pdfs"


def generate_dataset(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    spec_path: Path = DEFAULT_SPEC_PATH,
    answer_keys_path: Path = DEFAULT_ANSWER_KEYS_PATH,
) -> list[Path]:
    """Generates MSA-2026-014.pdf, SOW-2026-03.pdf, and the six invoice PDFs.
    Deterministic: identical inputs (spec + answer keys) always produce
    identical rendered text content."""
    dataset = load_answer_keys(answer_keys_path)
    contract_clauses = load_contract_clauses(spec_path)
    sow_clauses = load_sow_clauses(spec_path)
    client, vendor = msa_parties(dataset)

    msa_meta = dataset.documents[MSA_DOCUMENT_ID]
    sow_meta = dataset.documents[SOW_DOCUMENT_ID]
    if msa_meta.effective_from is None or msa_meta.effective_to is None:
        raise ValueError(f"{MSA_DOCUMENT_ID} is missing effective_from/effective_to")
    if sow_meta.period_from is None or sow_meta.period_to is None:
        raise ValueError(f"{SOW_DOCUMENT_ID} is missing period_from/period_to")

    output_paths: list[Path] = []

    msa_path = output_dir / f"{MSA_DOCUMENT_ID}.pdf"
    build_msa_pdf(
        msa_path,
        contract_clauses,
        document_id=MSA_DOCUMENT_ID,
        client=client,
        vendor=vendor,
        effective_from=msa_meta.effective_from.isoformat(),
        effective_to=msa_meta.effective_to.isoformat(),
    )
    output_paths.append(msa_path)

    sow_path = output_dir / f"{SOW_DOCUMENT_ID}.pdf"
    build_sow_pdf(
        sow_path,
        sow_clauses,
        document_id=SOW_DOCUMENT_ID,
        msa_document_id=MSA_DOCUMENT_ID,
        client=client,
        vendor=vendor,
        period_from=sow_meta.period_from.isoformat(),
        period_to=sow_meta.period_to.isoformat(),
    )
    output_paths.append(sow_path)

    for scenario in dataset.scenarios:
        invoice_path = output_dir / f"{scenario.invoice_id}.pdf"
        build_invoice_pdf(invoice_path, scenario, vendor=vendor, client=client)
        output_paths.append(invoice_path)

    return output_paths
