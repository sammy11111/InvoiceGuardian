"""CLI:
python -m invoiceguardian.analyze <invoice_id> [--pdf-dir DIR] [--model MODEL]
python -m invoiceguardian.analyze --all --persist [--results-dir DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from invoiceguardian.analyze import DEFAULT_PDF_DIR, run_analysis
from invoiceguardian.analyze.persist import DEFAULT_RESULTS_DIR, persist_all_results
from invoiceguardian.api.export import DEFAULT_VIEWS_DIR, persist_all_views
from invoiceguardian.extraction.anthropic_client import DEFAULT_MODEL


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m invoiceguardian.analyze")
    parser.add_argument("invoice_id", nargs="?", help='Invoice document ID, e.g. "INV-2026-061"')
    parser.add_argument(
        "--all", action="store_true", help="Run every canned scenario (requires --persist)"
    )
    parser.add_argument(
        "--persist", action="store_true", help="Write results as JSON instead of printing one"
    )
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--views-dir", type=Path, default=DEFAULT_VIEWS_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--verbose", action="store_true", help="Print pipeline stage progress to stdout"
    )
    args = parser.parse_args(argv)

    if args.all:
        if not args.persist:
            parser.error("--all requires --persist")
        paths = persist_all_results(
            output_dir=args.results_dir, pdf_dir=args.pdf_dir, model=args.model
        )
        paths += persist_all_views(output_dir=args.views_dir, results_dir=args.results_dir)
        for path in paths:
            print(path)
        return 0

    if not args.invoice_id:
        parser.error("invoice_id is required unless --all is given")

    result = run_analysis(
        args.invoice_id, pdf_dir=args.pdf_dir, model=args.model, verbose=args.verbose
    )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
