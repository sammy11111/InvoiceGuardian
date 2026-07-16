"""CLI: `python -m invoiceguardian.analyze <invoice_id> [--pdf-dir DIR] [--model MODEL]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from invoiceguardian.analyze import DEFAULT_PDF_DIR, run_analysis
from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m invoiceguardian.analyze")
    parser.add_argument("invoice_id", help='Invoice document ID, e.g. "INV-2026-061"')
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    result = run_analysis(args.invoice_id, pdf_dir=args.pdf_dir, model=args.model)
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
