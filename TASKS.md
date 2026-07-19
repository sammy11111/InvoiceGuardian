# TASKS

## Step 10 — write-up

- **"One genuine failure analyzed" section (SCORING.md reporting commitment) = the S4 semantic-path divergence.** Under the frozen neutral classification prompt, claude-sonnet-5 stably collapses S4 ("ERP Rollout Advisory Support") to EQUIVALENT 4/4 → clean pass → abstention miss, hard gate 3 fails. Fable 5 adjudicated it: prompt is neutral, this is genuine model behavior, not tuned away. Secondary finding — S4's spec premise that escalation is the uniquely defensible disposition is overstated; conditional trigger for a reworded S4 in a future dataset version is if BOTH required arms (sonnet-5 + fable-5) fail S4 identically in Phase A. Full adjudication chain is in the InvoiceGuardian planning chat.

- **Write-up's engineering-integrity angle:** the evaluator (the grader) was independently reviewed twice and both passes found real gaps — Codex caught 10 scoring/gate issues (S4 dual-disposition, missing-scenario-as-FN, etc.), a coverage check caught 2 untested live-logic paths (zero-prediction precision convention, gate-1 fabrication on false positives). The component that grades everything was gated harder than the rest, and it kept rewarding scrutiny.

- **Demo snapshot:** S2 landed ESCALATE this run; S2 is inherently unstable (3/4 AMBIGUOUS vs 1/4 NOT_AUTHORIZED per step-6 testing) — this is a real captured output, not the only possible one.

### Kanz submission requirements (from the grading rubric)

- Grader is an AI agent reading only: project story (problem / solution / how built / who benefits / future vision), resume PDF, demo video, hero image + 2 screenshots. It never reads the repo — all engineering rigor must be narrated in the story text and shown in the video.
- Rubric: Originality 20 / Technical Depth 30 / Impact 30 / Presentation 20. Gold ≥85.
- Video must show the tool actively working; the citation moment (finding + verbatim source quote on screen) is the centerpiece. No live working demo = flagged.
- Real screenshots only — AI-generated concept images are auto-detected and penalized.
- Impact needs explicit quantification in the story (AP review hours, cost of missed overcharges) — current docs argue rigor, not dollar impact.
- Resume must explicitly list the skills this project demonstrates (Python, FastAPI, Pydantic, prompt engineering, LLM evaluation design, agentic workflows) — skills score as Verified/Applied only if they appear in BOTH resume and project.
- "Future vision" field = ROADMAP.md content.
- Note: the rubric's required media list has no deck — reallocate any deck time to video + story text.

### Employer challenge track

- Confirmed (Day 1 keynote transcript, Kanz speaker, 11:45:21–11:45:36 GMT+3, July 15 2026): two employers submitted challenges to the hackathon. The top 10 submissions closest to each challenge get shown directly to that employer for an interview or conversation, separate from the general judging/prize track.
- Assumed, not confirmed: the two employers are Sucafina and Booking.com — inferred from a garbled transcript line ("Sci-fi booking.com, some VCs, CME, Siren Analytics") cross-referenced against Kanz's public Success Stories page (TELUS, Sucafina, Booking.com, Alefb). Do not treat as fact.
- **Open item, blocking:** actual challenge content for either company is unknown. Find the challenge brief (portal, Telegram, session chat, or a later day's recap/transcript) before finalizing the project story text (step 10) — it determines whether InvoiceGuardian is even a relevant match for either challenge.
- Do not let this item slip to step 10 by default — it should resolve as soon as the brief surfaces, independent of build progress.
