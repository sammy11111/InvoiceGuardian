"""Deterministic checks: ordinary Python, no model calls.

Implemented here: rate-mismatch checking (rate_check.py) and aggregate
monthly-cap checking (aggregate_cap.py). CLAUDE.md's deterministic-logic
principle names a broader category (dates, references, duplicates,
quantity limits) as the target for future checks of this kind — this
package does not implement those yet; see LIMITATIONS.md. Descriptions
that don't resolve to a role via an exact match are left unresolved here
— bounded semantic matching (S2/S3/S4) is a later build step, not part of
this package.
"""
