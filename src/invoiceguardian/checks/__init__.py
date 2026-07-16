"""Deterministic checks: ordinary Python, no model calls.

Per CLAUDE.md: "Deterministic logic (arithmetic, dates, currency equality,
rate checks, caps, quantity limits, references, duplicates) stays in
ordinary Python." Descriptions that don't resolve to a role via an exact
match are left unresolved here — bounded semantic matching (S2/S3/S4) is a
later build step, not part of this package.
"""
