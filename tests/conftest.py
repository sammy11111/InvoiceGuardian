"""Puts the repo root on sys.path so tests can import top-level scripts/
utilities (e.g. scripts/demo_explained_classification.py) as regular
modules — the same code that runs as `uv run python scripts/...`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
