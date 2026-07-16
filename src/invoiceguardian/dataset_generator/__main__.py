"""CLI entry point: `python -m invoiceguardian.dataset_generator [output_dir]`."""

from __future__ import annotations

import sys
from pathlib import Path

from invoiceguardian.dataset_generator.generate import DEFAULT_OUTPUT_DIR, generate_dataset


def main(argv: list[str]) -> int:
    output_dir = Path(argv[0]) if argv else DEFAULT_OUTPUT_DIR
    paths = generate_dataset(output_dir=output_dir)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
