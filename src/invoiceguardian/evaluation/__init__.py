"""Deterministic evaluation harness.

Implements SCORING.md exactly: finding matching, the four metric families
(extraction, detection, grounding, abstention), the hard gates, and the
weighted score. The harness is ordinary code — "the LLM is never the
evaluator" (SCORING.md). It scores `BenchmarkRun`s (real pipeline output)
against the `EvaluationDataset` (answer_keys.json) and emits a
`MetricSummary` per arm.
"""
