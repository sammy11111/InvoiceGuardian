"""Typed extraction with provenance — the pipeline's only model calls.

Per CLAUDE.md: "the LLM is used only for typed extraction and bounded
semantic comparison/ambiguity recognition." Deterministic logic (arithmetic,
dates, currency, rate checks) lives in `invoiceguardian.checks`, not here.
"""
