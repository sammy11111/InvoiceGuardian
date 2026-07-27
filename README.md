# InvoiceGuardian

InvoiceGuardian checks a service invoice against its governing contract and Statement of Work, and produces evidence-cited exception findings — every finding is a draft requiring human approval, never an automated payment or fraud determination.

**Live demo:** https://web-production-8e619.up.railway.app

## Evaluation methodology

This project is built around one claim: the evaluation was designed before the system that would be evaluated existed, and the grading logic never touches the model it's grading.

**Preregistration.** Commit [`28dad57`](https://github.com/sammy11111/InvoiceGuardian/commit/28dad57d9c8e22ff5973b7d227cf7ebd5e4d303e) (2026-07-15 19:19:18) added the scenario specification, the answer keys, and the scoring rules (`scenario-spec.md`, `answer_keys.json`, `SCORING.md`) — zero implementation code. The evaluator itself wasn't written until commit [`7849045`](https://github.com/sammy11111/InvoiceGuardian/commit/78490453f8579b1791b23a2b723178e816ea806e) (2026-07-15 23:08:46), **3h49m later**. The scoring rules could not have been shaped around what the code turned out to do, because the code didn't exist yet. That ordering is in the commit log, not a claim about intent.

**The evaluator is deterministic.** `src/invoiceguardian/evaluation/evaluator.py` imports `statistics`, `dataclasses`, `decimal`, and this project's own `evaluation`/`schemas` modules. Nothing else. There is no reference anywhere in the file to the Anthropic client, a model name, or an API key. It scores an already-produced pipeline result against `answer_keys.json` with plain comparisons — grading is not itself a judgment call made by a model.

**137 tests**, counted directly with `pytest --collect-only`, across 21 files:
- schema validation (`test_runtime_schema.py`, `test_evaluation_schema.py`, `test_json_schema_utils.py`)
- deterministic checks (`test_rate_check.py`, `test_aggregate_cap.py`, `test_role_matching.py`, `test_normalize.py`, `test_semantic_assembly.py`)
- the evaluator and its hard gates (`test_evaluation_gates.py`, `test_evaluation_scoring.py`, `test_evaluation_addenda.py`, `test_evaluation_real_s1_s6.py`)
- the pipeline end-to-end against the real model (`test_analyze_s1_s6_e2e.py`, `test_analyze_semantic_e2e.py`, `test_analyze_disposition.py`)
- synthetic dataset generation (`test_dataset_generator.py`)
- the serving API (`test_api.py`, `test_api_view.py`, `test_api_middleware.py`)
- the Anthropic client's retry policy (`test_anthropic_client_retry.py`)

## A documented model failure

`SCORING.md:112` commits, in advance, to a specific standard: *"No metric is omitted because it is unflattering. At least one genuine failure is analyzed in the write-up."*

Scenario S4 is that failure. Its invoice line ("ERP Rollout Advisory Support") is deliberately worded to be ambiguous against the supplied contract and SOW — the correct behavior is an AMBIGUOUS classification, which escalates the finding to human review rather than resolving it automatically. Under the frozen classification prompt, the model instead classifies it as a confident match. That's a miss: the system should abstain and didn't.

This isn't a bug that got quietly patched around. It's encoded as a permanent test — `tests/test_evaluation_gates.py:221`, `test_s4_confident_exception_fails_gate_3` — which builds exactly this confident-instead-of-ambiguous output and asserts the evaluator scores it as `abstention == "incorrect_confident"` and fails hard gate 3. The gate that catches this behavior is itself under test. Loosening the gate to let S4 pass would break the test suite; the failure stays visible by construction, not by discipline that could lapse.

The reason to publish this rather than pick a different scenario for the demo: an evaluation methodology that only ever reports passing results isn't verifiable as a methodology — it's a highlight reel. A gate that can catch and hold its own system's failure is the evidence that the harness does what it claims to do.

## Architecture

Parsing, arithmetic, rate comparison, and cap checks are ordinary Python — deterministic, no model call. The model is used for exactly two things: typed extraction of contract/SOW/invoice fields, and classifying one invoice line's authorization status when deterministic exact-match role lookup fails. Every model call is schema-constrained tool use, not free text. An AMBIGUOUS classification always resolves to `ESCALATE`, which routes the finding to `awaiting_review` — a human decision point, not an automated resolution.

## Scope and limitations

- Deterministic checks cover contract rate mismatches and aggregate monthly spending caps (`checks/rate_check.py`, `checks/aggregate_cap.py`). There is no check that an invoice's stated total is arithmetically consistent with its own line items, and no date-validity checking — service periods and contract effective dates are extracted and recorded, never compared against each other. Both are extension work, not shipped.
- The live demo serves six pre-computed, persisted results (`data/scenario_runs/`, `data/scenario_views/`) through the FastAPI backend. It does not call the model at request time. No `ANTHROPIC_API_KEY` is set on the deployment — confirmed on the Railway service's own environment variables. Nothing you click on the live demo triggers live inference.
- All contract, SOW, and invoice documents are synthetic, generated by `src/invoiceguardian/dataset_generator`. No real commercial data is used anywhere in this repository.
- Built solo, under hackathon time constraints (Kanz AI Training Hackathon, July 2026). That shaped scope directly: one contract and one SOW against six invoices rather than a larger benchmark, digitally-generated PDFs only (no OCR, no scanned documents), no arbitrary document upload, a single runtime model rather than multi-model routing or consensus.

## Running locally

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
```

Model calls (extraction and semantic comparison) need an Anthropic API key. Create a `.env` file at the repo root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Run the test suite:

```bash
uv run pytest
```

Run the pipeline on one invoice:

```bash
uv run python -m invoiceguardian.analyze INV-2026-061
```

Run every scenario and persist results (what the live demo serves):

```bash
uv run python -m invoiceguardian.analyze --all --persist
```

The evaluator has no separate CLI — it's exercised through its test suite:

```bash
uv run pytest tests/test_evaluation_gates.py tests/test_evaluation_scoring.py tests/test_evaluation_real_s1_s6.py
```

`test_evaluation_real_s1_s6.py` runs the pipeline against the real model and is skipped automatically if `ANTHROPIC_API_KEY` isn't set.

Serve the API locally:

```bash
uv run uvicorn invoiceguardian.api.app:app --reload
```
