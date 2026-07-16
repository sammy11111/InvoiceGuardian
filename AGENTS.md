# InvoiceGuardian — engineering rules for Codex

Product: **InvoiceGuardian — Service Invoice Exception Review** (name locked; do not rename).
Source of truth: `scenario-spec.md` + `answer_keys.json` (dataset v1.3-2026-07-15; the authoritative dataset version is always the one declared inside answer_keys.json) + `SCORING.md`. If code and spec disagree, the spec wins; flag the conflict, do not silently adapt the spec.

## Stack (locked)
- Python 3.12, FastAPI, Pydantic v2, httpx, pytest, ruff, pyright, uv.
- PDF parsing: pdfplumber (or PyMuPDF if coordinates are needed); digitally generated PDFs only. No OCR.
- Frontend: Next.js + TypeScript + Tailwind + shadcn/ui, generated last, capped at one evening.
- Storage: JSON files (SQLite only if genuinely needed).
- Deployment: single deployable unit. Replit if the 30-minute spike passes (health endpoint, static route, one secret, public HTTPS, restart persistence); otherwise combined app on Railway/Render. Deploy Friday night. Never deploy Sunday.
- Public demo protections: canned synthetic scenarios only (no arbitrary public PDF upload in v1), API keys server-side only, small request-size limits, basic rate limiting. Uploaded documents, if ever enabled, are untrusted input.

## Hard prohibitions
- No vector database. No RAG framework. No LangChain, LangGraph, CrewAI, or multi-agent orchestration.
- No autonomous external actions: nothing is ever sent, paid, or filed by the system. Draft + human approval only.
- No fraud language, no payment decisions, no claims that services were or were not delivered, no legal or accounting advice — in code, UI copy, prompts, or docs.
- No fine-tuning. No multi-model consensus/routing in v1. One runtime model, selected per SCORING.md.
- Deterministic logic (arithmetic, dates, currency equality, rate checks, caps, quantity limits, references, duplicates) stays in ordinary Python. The LLM is used only for typed extraction and bounded semantic comparison/ambiguity recognition.

## Architecture (locked pipeline)
parse → typed extraction with provenance → normalization → deterministic checks → bounded semantic matching (unresolved descriptions only) → evidence-cited findings → ambiguity/abstention → human approval state → drafted action.
- The MSA and SOW are extracted once per session/arm, validated, and cached as typed objects; invoices are analyzed incrementally against the cache. The identical caching policy applies to every benchmark arm (see SCORING.md).
- Invoice line IDs are deterministic parser metadata: assigned from table rows during parsing, validated by parser tests, never model-extracted, excluded from the 106-field extraction denominator.
- The three baseline semantic-comparison operations (S2-L1 authorization, S3-L1 equivalence, S4-L1 ambiguity) are invoked by the deterministic normalizer per the spec; they are part of SCORING.md's fixed 11-operation manifest and must execute in every arm.
- Every finding carries evidence: document ID, section, page, verbatim canonical quote (or the absence-of-authorization structure for S2-type findings).
- Every pipeline run emits an operational trace (inputs, extracted facts, rule results, model calls, evidence, decision state). The trace is an auditable log render — never chain-of-thought.

## Quality bar
- All code testable and tested. Test-first repair: when a bug or failing scenario is found, first write or update the failing test, then fix the implementation.
- Reproducibility: every eval or benchmark run records dataset_version, answer-key schema_version, and prompt_version. Prompts live in versioned files, never inline strings.
- **Two schema families, strictly separated.** Runtime domain schemas (ContractTerms, StatementOfWork, Invoice, InvoiceLine, EvidenceReference, ExceptionFinding, AnalysisResult, OperationalTrace) never contain answer-key fields (`expected_findings`, `difficulty`, `why_this_exists`, `trap`, `scoring_note`, `confidence_expectation`). Evaluation schemas (EvaluationDataset, ScenarioAnswerKey, ExpectedFinding, ExpectedEvidence, BenchmarkRun, MetricSummary) may mirror answer_keys.json. Ground truth never leaks into production objects.
- Monetary values: decimal strings in data files, `Decimal` in code, quantized to 0.01. Never through float.
- Run ruff + pyright + pytest before declaring any task complete.
- Prefer the simplest implementation that satisfies the current scenario set. Reject speculative abstractions.

## Model settings for Codex sessions (assistant layer)
- Routine implementation, tests, UI, docs: Sonnet 5, effort high (default). Never low.
- Difficult contained implementation / moderate debugging: Opus 4.8, effort high.
- Cross-cutting architecture, severe multi-stage bugs, major refactors, final repo review: Opus 4.8, effort xhigh (deliberately, not by default).
- Consequential ambiguity (spec conflicts, eval failure analysis, final critique): escalate to Fable 5.
Runtime model selection is separate and governed exclusively by SCORING.md.

## Build order (do not reorder)
1. Runtime domain schemas + separate evaluation schemas (see Quality bar)
2. Document generator from scenario-spec.md §3–§4 (canonical clauses verbatim)
3. Parse → extract → S1 deterministic rate check → one cited finding, end-to-end via CLI
4. S6 clean run producing zero findings
5. Evaluation harness emitting all four metric families
6. Remaining checks (S2, S4 semantic path, S5 aggregate)
7. Minimal review UI (left: invoice lines/status; right: finding + source + quote + decision mode — deterministic check / model-assisted match / human review required; drawer: trace + approval actions). No "confidence" display in v1. Not a chatbot.
8. Deployment spike → deploy
9. Benchmark per SCORING.md (Phase A then Phase B)
10. Video, deck, submission text
11. Exactly one stretch (n8n webhook OR one evaluated bilingual case), only if 1–10 are complete
