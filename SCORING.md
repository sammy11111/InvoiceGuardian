# SCORING.md — Pre-registered model-selection policy (v1.4)
Committed BEFORE any benchmark run. Dataset: `v1.3-2026-07-15` (answer_keys.json, schema 1.2, 106-field extraction manifest — dataset unchanged by this policy revision).
Lifecycle: DRAFT → PREREGISTERED (state written into the artifacts and committed before implementation) → FROZEN (after PDF generation and rendered-page verification, committed again). Formal benchmark runs occur only on the FROZEN dataset. Development smoke calls may occur earlier but are never reported or presented as benchmark runs.
Purpose: the runtime model for InvoiceGuardian is selected by this policy, not by preference. Committed before results exist so the selection is provably not post-hoc.

## Experiment design

**Phase A — model comparison.** Each candidate model is evaluated at its **recommended high-quality production setting** (no claim of equal reasoning compute across vendors; effort/reasoning knobs are not calibrated to a common budget). Held fixed across all candidates: documents, prompts, schemas, parsing, deterministic logic, evaluation data and keys, retry policy, output validation, caching protocol, and sampling parameters where comparable.

**Phase B — effort ablation (winner only).** Compare the winner at high vs. medium effort on quality, latency, and token cost, under the same replication policy as Phase A. Deploy one model, one setting. If the selected model does not support an effort control, Phase B is skipped and the reason is recorded.

**Replication policy (preregistered).** Each required model arm receives **three independent complete runs** on the frozen dataset. Hard gates must pass in all three runs. Weighted metrics are averaged across the three runs and the observed range is reported. Optional arms follow the same policy if included. If the schedule cannot support three, run two complete replicates and describe the result verbatim as "a preliminary repeated comparison." A one-shot run may inform development but never decides the production model while being presented as stable evidence.

**Prompt freeze (preregistered).** All runtime prompts are frozen and committed before the first Phase A run. Any prompt change after that point invalidates every earlier arm result and requires all candidate arms to be rerun from the beginning. No model-specific prompt tuning.

**Dataset-scale branch (preregistered).** If the pipeline is green by Friday evening (July 17), scenarios S7 (conflicting source documents) and S8 (split-line aggregate violation) are added as dataset v1.4 and Phase A runs on the expanded set (≥8 scenarios, ≥5 detectable exception units). If not, Phase A runs on the six-scenario baseline and is described, verbatim, as "a preliminary controlled comparison on the baseline evaluation set" — no claim of generally superior model performance is made from six scenarios. The dataset version in use is recorded in every run log; expansion after Phase A begins is prohibited. The replication policy applies in either branch.

## Candidates and configurations (log the true config per run)

| Arm | Model | Config to record |
|---|---|---|
| Required | claude-sonnet-5 | effort: high (default); thinking: adaptive |
| Required | claude-fable-5 | effort: high; thinking: adaptive (always on) |
| Optional cost/speed baseline (untuned) | claude-haiku-4-5-20251001 (pinned snapshot, not the alias) | effort: n/a (unsupported); extended thinking config as used |
| Optional, gated | gpt-5.6-sol | reasoning: high; gated on: API access works immediately, adapter already built, baseline deployed, demo and submission safe |

Per-run log: model ID, effort/reasoning setting, thinking mode, temperature/sampling, prompt_version + prompt hash, dataset_version, answer-key schema_version, replicate index, timestamp. Prompts live in versioned files; a prompt change bumps prompt_version (see prompt freeze above).

## Shared-document protocol and the fixed operation manifest (identical across all arms)

For each run: extract and validate the MSA once; extract and validate the SOW once; cache both typed outputs; extract each of the six invoices once; execute the three preregistered semantic-comparison operations. The identical caching policy applies to every arm.

**Required-operation manifest (frozen):**
- 2 shared-document extraction operations (MSA, SOW)
- 6 invoice extraction operations
- 3 required semantic-comparison operations: S2-L1 (authorization/scope), S3-L1 (semantic equivalence), S4-L1 (ambiguity classification) — invoked by the deterministic normalizer per the spec, so they execute in every arm by construction

**= 11 required model operations per benchmark run.** This fixed manifest is the denominator for schema validity and first-pass validity. Any additional model call is logged as an extra operation and counts toward cost and latency, but never alters the preregistered denominator.

**Line IDs:** invoice line IDs are deterministic parser metadata (assigned from table rows during parsing, validated by parser tests). They are never model-extracted and are excluded from the 106-field extraction denominator.

**Latency and cost accounting:** report separately (a) document-set initialization latency (MSA + SOW), (b) incremental invoice-analysis latency per invoice (median across all invoices and replicates primary; mean reported), (c) cold end-to-end latency (initialization + first invoice). Cost per invoice amortizes initialization across the six invoices; initialization cost is also reported on its own line so nothing is hidden.

## Finding matching (preregistered — the evaluator implements exactly this)

- **Match key:** `(finding_type, scope, invoice_line_id)`, where invoice-scope findings carry `invoice_line_id = null` and match on `(finding_type, scope, invoice_id)`.
- Matching is 1:1 within a scenario: a predicted finding matches at most one expected finding and vice versa.
- **Detection true positive: a key match, regardless of disposition.** Detection precision and recall are computed on key matches (conventional definitions).
- **Disposition accuracy** (observational) = matched findings with the correct disposition ÷ all matched findings. Disposition errors are logged per finding.
- Any predicted finding that fails to key-match an expected finding is a **false positive** — including any finding on S3 or S6, any finding on a clean line, duplicates beyond the first match, wrong-type findings, and invented invoice-scope findings.
- Missing expected findings are **false negatives**.
- **S4 is excluded from detection precision/recall entirely**; it is scored solely under the abstention metric (ESCALATE = correct; any confident exception = incorrect_confident; clean pass = abstention miss). S4's disposition is hard-gated because the disposition is the point of the scenario.
- `expected_values` are compared for matched findings and reported observationally as value accuracy; mismatches do not change detection status.
- **Zero-prediction convention:** if a model reports zero exceptions while the dataset contains expected exceptions, detection precision is defined as 0.

## Evidence atoms and grounding (preregistered)

Evidence is scored only for key-matched findings. An **evidence atom** is one of: a source quote (document + section + verbatim canonical quote, whitespace-normalized), an invoice-line reference, a searched-section set (must include every document + section listed in the key), an explicit no-match statement (semantic presence required, not verbatim), or a computed value (exact Decimal match). The answer key defines the required atoms per finding.

**Minimum evidence-role set (hard gate) per finding type:**

| Finding type | Minimum hard-gate evidence |
|---|---|
| RATE_MISMATCH | governing rate quote + invoice-line reference |
| UNAUTHORIZED_SERVICE | governing scope/authorization evidence + searched-section set with no-match statement + invoice-line reference |
| SCOPE_AMBIGUITY | governing scope quote + invoice-line reference |
| AGGREGATE_CAP_EXCEEDED | governing cap quote + computed invoice total |

- **Hard-gate definition (unsupported finding):** a finding missing its minimum evidence-role set, or containing any fabricated citation (a quote not present in the supplied documents). An invoice-line reference alone proves only that the line exists; it never satisfies the gate by itself.
- **Weighted grounding completeness** = correct required atoms ÷ all required atoms, averaged over matched findings. This remains the discriminating metric.
- Extra evidence is permitted only when it references a real supplied source and does not contradict the finding; a fabricated extra citation renders the finding unsupported.

## Hard gates (any failure in any replicate disqualifies the arm regardless of other scores)

1. Zero unsupported findings, per the minimum evidence-role sets above (zero fabricated citations anywhere).
2. **Schema validity:** 100% of the 11 required model operations produce schema-valid output within at most one retry.
3. S4 must be ESCALATED. A confident exception or a clean pass on S4 disqualifies.
4. **Detection precision gate, stated in counts:** zero false-positive findings across the dataset.

If no arm passes all hard gates, no selection claim is made; the least-violating arm may be deployed with the gate failure disclosed explicitly in the write-up.

## Retry policy (fixed across all arms)

Retry only after a parse or schema-validation failure — never because a semantic answer is wrong. One retry maximum, using the same fixed repair prompt for every model. Retry tokens, latency, and cost are included in the arm's totals. Refusals count as schema failures unless caused by a documented provider infrastructure error.

## Weighted score (among arms passing all gates; averaged across replicates)

- Exception detection recall: 40%
- Grounding completeness (evidence atoms): 30%
- Extraction accuracy (whitespace-collapsed exact match over the 106-field manifest, per the normalization rules in answer_keys.json): 20%
- First-pass schema validity (first-pass valid operations ÷ 11, before any retry): 5%
- Normalized latency: 5%, computed as `latency_score = 100 × fastest_passing_median_incremental_latency ÷ candidate_median_incremental_latency`, capped at 100.

**Detection precision carries no weight**: it is enforced as a hard gate and reported prominently; weighting it again would double-count a quantity that is ~constant among passing arms. Disposition accuracy and value accuracy are reported observationally.

Tie-break order: latency, then token cost. Small-N caveat: single-unit differences between arms are within noise; if two arms tie within one evaluation unit on every metric, select the cheaper/faster arm and say so in the write-up.

## Observational metrics (reported, never gated)

For every arm: detection precision (per replicate and averaged); disposition accuracy; first-pass schema validity per replicate; initialization, incremental, and cold latency; average model token usage and estimated API cost per invoice (with initialization amortization stated); value accuracy on matched findings; performance by scenario difficulty; cross-replicate range on every weighted metric.

## Evaluator statement

The evaluation harness is deterministic: metrics are computed by ordinary code against the answer keys. The LLM is never the evaluator.

## Exclusion conditions

A run may be excluded and re-executed only for infrastructure failure (network error, provider 5xx, timeout unrelated to output). Excluded runs are logged with reason. Output-quality failures are never excluded.

## Reporting commitment

All four metric families (extraction, detection, grounding, abstention) are reported for the selected model regardless of results, plus disposition accuracy and replicate ranges. No metric is omitted because it is unflattering. At least one genuine failure is analyzed in the write-up.
