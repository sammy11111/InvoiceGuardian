# InvoiceGuardian — Scenario Specification v1.4
Dataset version: `v1.3-2026-07-15` (unchanged since v1.3; this document revision aligns metric definitions only) · Answer-key schema: `1.2` · Prompt versions: recorded per run (see SCORING.md) · Owner: Sammy Ibrahim
Lifecycle: **DRAFT** → **PREREGISTERED** (state written into the artifacts and committed before implementation) → **FROZEN** (after PDF generation and rendered-page-reference verification, committed again). Current state: **PREREGISTERED, effective at initial repo commit**; any subsequent edit reverts to DRAFT. Formal benchmark runs occur only on the FROZEN dataset; earlier development smoke calls are never presented as benchmark runs.

**Product name (locked):** InvoiceGuardian — Service Invoice Exception Review.
**Purpose of this document:** the single source of truth for the synthetic evaluation dataset. Ground truth is defined here FIRST; documents are generated FROM this spec. The evaluator scores against the answer keys in `answer_keys.json`, which are derived line-for-line from this file.

---

## 1. Design rules

1. **Answer key precedes documents.** No document content exists that is not specified here. If Claude Code needs filler prose (headers, boilerplate, signatures), it may invent it freely, but **evidence quotes may only come from the Canonical Clauses in §3** — verbatim, character-for-character.
2. **All data is synthetic.** All parties, rates, and documents are fictional. The public demo states this explicitly (responsible-AI point, not a weakness).
3. **One shared contract + one shared SOW.** The baseline evaluation dataset contains six invoices (version per this document's header; expansion path is §8). This mirrors reality (one governing agreement, many invoices) and keeps generation cheap.
4. **Documents are digitally generated PDFs** (no OCR, no scans) rendered from the templates in §3–§4. Page/section references below assume the layout in §3.4; if rendering shifts a section to another page, regenerate the answer key page numbers from the rendered PDFs before freezing — section numbers and quotes are the stable identifiers, pages are recorded at freeze time.
5. **The system never decides payment, never declares fraud, never claims services were or were not delivered, never gives legal or accounting advice.** It reports consistency with the supplied commercial documents and routes everything through human approval.
6. **Monetary values are decimal strings in all data files and `Decimal` in all code**, quantized to 0.01. Money never passes through binary floating point. (Current values happen to be float-exact; the convention exists so that never has to be checked again.)

## 2. Cast and shared facts

| Entity | Value |
|---|---|
| Client | Maplecore Logistics Inc. ("Maplecore") |
| Vendor | Northbridge Consulting Ltd. ("Northbridge") |
| Master agreement | MSA-2026-014, effective March 1, 2026 – February 28, 2027 |
| Statement of Work | SOW-2026-03, service period April 1 – September 30, 2026 |
| Currency | CAD throughout |

**Invoice schedule (one invoice per calendar month — see note):**

| Scenario | Invoice | Service period | Invoice date |
|---|---|---|---|
| S1 | INV-2026-061 | April 1–30, 2026 | May 3, 2026 |
| S2 | INV-2026-062 | May 1–31, 2026 | June 3, 2026 |
| S3 | INV-2026-063 | June 1–30, 2026 | July 3, 2026 |
| S4 | INV-2026-064 | July 1–31, 2026 | August 3, 2026 |
| S5 | INV-2026-065 | August 1–31, 2026 | September 3, 2026 |
| S6 | INV-2026-066 | September 1–30, 2026 | October 3, 2026 |

The system analyzes one invoice per run (contract + SOW + one invoice). Assigning one invoice per calendar month makes the MSA §4.3 monthly-cap ground truth unambiguous under both the invoice-date and service-period readings of "invoiced in any calendar month": S5's month contains only S5, which breaches the cap on its own; every other month totals well under the cap.

## 3. Document templates

### 3.1 Contract — MSA-2026-014 (canonical clauses)

Evidence quotes must match these strings exactly.

- **§4.1 (rate card):**
  - "Senior Consultant services shall be billed at CAD $150.00 per hour."
  - "Consultant services shall be billed at CAD $110.00 per hour."
  - "Project Manager services shall be billed at CAD $135.00 per hour."
- **§4.3 (monthly cap):** "Aggregate fees invoiced in any calendar month shall not exceed CAD $25,000.00."
- **§5.2 (required reference):** "Each invoice must reference the applicable Statement of Work number."
- **§2.1 (authorization principle):** "Northbridge shall perform only those services described in an executed Statement of Work under this Agreement."
- **§1.2 (term):** "This Agreement is effective from March 1, 2026 through February 28, 2027."

### 3.2 SOW — SOW-2026-03 (canonical clauses)

- **§2 (scope):** "Northbridge shall provide implementation support for Maplecore's ERP rollout, data migration validation, and training documentation."
- **§3 (roles and monthly limits):**
  - "Senior Consultant: up to 100 hours per calendar month."
  - "Consultant: up to 80 hours per calendar month."
  - "Project Manager: up to 20 hours per calendar month."
- **§4 (period):** "Services under this Statement of Work shall be performed between April 1, 2026 and September 30, 2026."

### 3.3 Invoice layout (all six)

Header: vendor, client, invoice number, invoice date, service period, SOW reference (present unless a scenario says otherwise). Body: line items `line_id | description | hours | rate (CAD/hr) | amount`. Footer: total.

### 3.4 Rendering assumption for page references

Contract: §1–§2 page 1, §4 page 2, §5 page 3. SOW: §1–§4 on pages 1–2 (§2 and §3 on page 1, §4 on page 2). Invoices: single page. Record actual pages at freeze time per rule §1.4.

## 4. The six scenarios

Exception taxonomy v1: `RATE_MISMATCH`, `UNAUTHORIZED_SERVICE`, `SCOPE_AMBIGUITY`, `AGGREGATE_CAP_EXCEEDED`. Dispositions: `AUTO_EXCEPTION` (deterministic), `SEMANTIC_EXCEPTION`, `ESCALATE`, `CLEAN`. Every non-clean result terminates in a human-approval state; `expected_action` names the *drafted* next step, never an executed one.

### S1 — Exact rate mismatch (deterministic detection)
**Invoice INV-2026-061.** L1: "Senior Consultant — ERP implementation support" — 40 hrs @ **$175.00** = $7,000.00. L2: "Project Manager — oversight" — 10 hrs @ $135.00 = $1,350.00. Total $8,350.00. SOW referenced.
**Ground truth:** L1 fires `RATE_MISMATCH` (`AUTO_EXCEPTION`, basis deterministic): billed 175.00 ≠ contract 150.00. Evidence: MSA §4.1 Senior Consultant quote + invoice L1. Expected action: `DRAFT_VENDOR_CLARIFICATION`. L2 clean. **Tests:** deterministic check precision, exact-value extraction, evidence citation.

### S2 — Unauthorized service line (absence detection)
**Invoice INV-2026-062.** L1: "Architecture Workshop Facilitation" — 12 hrs @ $150.00 = $1,800.00. L2: "Consultant — data migration validation" — 30 hrs @ $110.00 = $3,300.00. Total $5,100.00. SOW referenced.
**Ground truth:** L1 fires `UNAUTHORIZED_SERVICE` (`SEMANTIC_EXCEPTION`, basis absence): no authorization for workshop facilitation in SOW §2/§3 or under MSA §2.1. Evidence kind `absence_of_authorization`: records the documents/sections searched (SOW §2, §3; MSA §2.1), quotes SOW §2 scope clause and MSA §2.1, and states no matching authorization was found. Expected action: `DRAFT_VENDOR_CLARIFICATION` (human review; never a fraud claim). L2 clean. **Tests:** absence representation, restraint in claim language.

### S3 — Semantic equivalent, valid (false-positive trap)
**Invoice INV-2026-063.** L1: "Sr. Consulting Services — ERP implementation" — 60 hrs @ $150.00 = $9,000.00. L2: "Project Manager — oversight" — 8 hrs @ $135.00 = $1,080.00. Total $10,080.00. SOW referenced.
**Ground truth:** NO findings. "Sr. Consulting Services" is semantically the contract's "Senior Consultant" role; rate, hours (≤100), dates all comply. Both lines `CLEAN`. **Tests:** semantic-matcher restraint; this scenario is the precision guard — any finding here is a false positive.

### S4 — Semantic near-match, invalid (mandatory escalation)
**Invoice INV-2026-064.** L1: "ERP Rollout Advisory Support" — 25 hrs @ $150.00 = $3,750.00. SOW referenced.
**Ground truth:** L1 → `SCOPE_AMBIGUITY`, disposition `ESCALATE`. The description is **plausibly related but insufficiently specified**: it overlaps the SOW §2 scope ("ERP rollout") yet "advisory support" may or may not be "implementation support" — the supplied documents cannot resolve the distinction. Correct behavior is escalation with both quotes side-by-side (SOW §2 + invoice L1), NOT a confident exception and NOT a clean pass. Expected action: `HUMAN_REVIEW`. **Tests:** abstention correctness. A confident `AUTO_EXCEPTION`/`SEMANTIC_EXCEPTION` here scores as an incorrect-confident answer; a clean pass scores as a miss. (Wording chosen so that escalation is the uniquely defensible disposition — a plainly-unauthorized phrase would make a confident exception reasonable and the disqualifying gate unfair.)

### S5 — Aggregate cap exceeded (cross-line deterministic logic)
**Invoice INV-2026-065.** L1: Senior Consultant — 95 hrs @ $150.00 = $14,250.00. L2: Consultant — 80 hrs @ $110.00 = $8,800.00. L3: Project Manager — 20 hrs @ $135.00 = $2,700.00. Total **$25,750.00**. SOW referenced.
**Ground truth:** every individual line is valid (rates match; hours within SOW §3 limits), but the invoice total exceeds the MSA §4.3 monthly cap of $25,000.00 by $750.00. Invoice-level `AGGREGATE_CAP_EXCEEDED` (`AUTO_EXCEPTION`, basis deterministic, aggregate). Evidence: MSA §4.3 quote + computed total. Expected action: `DRAFT_VENDOR_CLARIFICATION`. All three lines individually clean. **Tests:** aggregate checks defeat naive per-line validation; arithmetic in ordinary code.

### S6 — Clean invoice (negative case)
**Invoice INV-2026-066.** L1: Senior Consultant — 50 hrs @ $150.00 = $7,500.00. L2: Project Manager — 10 hrs @ $135.00 = $1,350.00. Total $8,850.00. SOW referenced.
**Ground truth:** NO findings. **Tests:** false-positive rate on clean invoices; required for a real precision number.

## 5. Evaluation-unit accounting (v1)

| Unit type | Count | Source |
|---|---|---|
| Planted exceptions (detectable) | 3 | S1, S2, S5 |
| Mandatory escalations | 1 | S4 |
| Clean invoices (negatives) | 2 | S3, S6 |
| Clean lines inside exception scenarios | 5 | S1 L2 · S2 L2 · S5 L1–L3 |
| Extraction fields (typed, per the manifest in answer_keys.json) | 106 exactly | all documents |

## 6. Metric definitions (bind to SCORING.md; finding-to-key matching follows the preregistered rules in SCORING.md exactly)

- **Exception detection precision** = key-matched detections ÷ all exceptions reported (a key match counts as a detection regardless of disposition; disposition accuracy is scored separately). Any finding on S3 or S6, on a clean line, or otherwise unmatched is a false positive. Precision functions as a hard gate and is reported prominently; it carries no weight in the selection score (see SCORING.md).
- **Exception detection recall** = key-matched detections ÷ 3.
- **Disposition accuracy** (observational) = matched findings with the correct disposition ÷ all matched findings. S4 is excluded from detection metrics and scored solely under abstention.
- **Grounding** is scored per the evidence-atom rules preregistered in SCORING.md: the hard gate requires each finding's minimum evidence-role set (an invoice-line reference alone never suffices) and zero fabricated citations; the weighted metric is **grounding completeness** = correct required evidence atoms ÷ all required atoms over matched findings. Quote atoms must exact-match a canonical clause (whitespace-normalized).
- **Abstention correctness** = S4 escalated → 1/1. A confident exception or a clean pass on S4 = incorrect-confident / miss respectively.
- **Extraction accuracy** = whitespace-collapsed exact matches over the 106-field manifest ÷ 106, per the normalization rules in answer_keys.json. Line IDs are deterministic parser metadata, never model-extracted, and sit outside the manifest.

## 7. Product requirement — operational trace

The trace is part of the product, not an implementation detail. Every analysis run MUST produce a human-readable operational trace containing: input document IDs with dataset, schema, and prompt versions; extracted typed facts with provenance; each deterministic rule executed and its result; each model call (model ID, effort setting, purpose) and its validated output; every finding with its full evidence; the disposition and approval state. The trace is a render of pipeline state, never chain-of-thought. Acceptance test: a reviewer can answer "how was this finding produced?" for S1 from the trace panel alone, and the demo's citation moment plays directly off it.

## 8. Expansion set (specified, deferred — build only after v1 baseline is green)

S7 conflicting source documents (MSA rate card $150 vs. SOW amendment $165 → `ESCALATE` with both quotes; best evidence-citation showcase). S8 split-line overcharge (one service split across two lines, each within limits, sum over an authorized quantity → aggregate `AUTO_EXCEPTION`; also the designated **candid failure case** if per-line logic misses it). S9 date-window violation (service dates outside SOW §4). S10 missing SOW reference (MSA §5.2). S11 currency mismatch (line billed in USD). S12 duplicate invoice number. Target after expansion: 10–12 scenarios, 25+ planted units, per R3.

## 9. Handoff notes for Claude Code

Build order tonight: runtime domain schemas plus separate evaluation schemas (only the evaluation schemas may mirror `answer_keys.json`; runtime objects never carry answer-key fields) → document generator from §3–§4 → parse → extract → the S1 deterministic rate check → one cited finding, end-to-end on S1 via CLI → S6 clean run producing zero findings. Then the evaluator. UI only after the evaluator emits real numbers.
