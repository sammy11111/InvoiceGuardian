"""Loads the versioned extraction prompts.

Prompts live in versioned files, never inline strings (CLAUDE.md quality
bar). A prompt change bumps `PROMPT_VERSION`; every run records it (see
SCORING.md's prompt-freeze rule).
"""

from __future__ import annotations

from pathlib import Path

PROMPT_VERSION = "v1"

_DIR = Path(__file__).resolve().parent

CONTRACT_EXTRACTION_SYSTEM_PROMPT = (_DIR / f"contract_extraction_{PROMPT_VERSION}.md").read_text(
    encoding="utf-8"
)
SOW_EXTRACTION_SYSTEM_PROMPT = (_DIR / f"sow_extraction_{PROMPT_VERSION}.md").read_text(
    encoding="utf-8"
)
INVOICE_EXTRACTION_SYSTEM_PROMPT = (_DIR / f"invoice_extraction_{PROMPT_VERSION}.md").read_text(
    encoding="utf-8"
)
SEMANTIC_COMPARISON_SYSTEM_PROMPT = (_DIR / f"semantic_comparison_{PROMPT_VERSION}.md").read_text(
    encoding="utf-8"
)
