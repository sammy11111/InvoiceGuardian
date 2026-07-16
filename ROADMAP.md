# InvoiceGuardian — Roadmap

## Real-World Validation: Path and Readiness

**Current status.** InvoiceGuardian's reported results come from a pre-registered synthetic benchmark — six scenarios with answer keys committed before implementation. This is a deliberate choice, not a gap of convenience: synthetic data with a locked answer key is what makes the evaluation *measurable and reproducible* in a public setting, where real commercial contracts can't be published. The benchmark demonstrates the pipeline's behavior on specified exception types; it does not, on its own, estimate accuracy across the full distribution of real-world contracts.

**The infrastructure is already built for real data.** The evaluation harness is deterministic code that scores any pipeline output against an answer key — it is agnostic to whether the documents are synthetic or real. Every metric family (detection, grounding, extraction, abstention), every hard gate, and the weighted score apply unchanged to a real-world corpus. The only missing ingredient is a labeled real-world dataset. The measurement machinery is done; the validation is a data problem, not an engineering one.

**How real-world validation would proceed:**

1. **Secure a real corpus under NDA.** Partner with a company that processes service invoices against contracts and will share anonymized documents. Anonymization (party names, identifying figures) preserves the structure the pipeline reasons over while protecting confidentiality.

2. **Establish ground truth.** A contracts or finance professional labels a held-out set — the correct findings, dispositions, and escalations per invoice. This labeling is the expensive, rate-limiting step of any real validation effort, and it is what turns a pile of documents into a scoreable benchmark.

3. **Run and report against the same rubric.** Feed the labeled corpus through the existing pipeline and evaluator. Report the same four metric families, with the same commitment to disclosing unflattering results, that govern the synthetic benchmark. Because the harness is already answer-key-driven, this step is turnkey.

4. **Report distribution, not just point accuracy.** Break results down by contract type, exception family, and — critically — abstention calibration: how often the system correctly escalates genuine ambiguity versus over- or under-escalating. Real contracts contain more ambiguity than synthetic ones, so the escalation boundary (already probed by the S4 scenario) is where real-world performance will most need measurement.

**Intermediate step.** Before real data, the pre-specified expansion set (S7–S12: conflicting source documents, split-line overcharges, date-window violations, missing references, currency mismatches, duplicate invoices) broadens synthetic coverage to 25+ planted exceptions across 10–12 scenarios — strengthening the measured claim without requiring confidential data.
<!-- FRIDAY UPDATE: if S7/S8 are built as the step-9 dataset-expansion branch, change "pre-specified" to "partially built (S7/S8 implemented; S9–S12 specified)" here and in any README reference. -->

**The honest bottom line.** Real-world validation is a post-benchmark milestone requiring a design partner and professional labeling, not an engineering sprint. What this project demonstrates is that the *hard part is finished*: a rigorous, deterministic, pre-registered measurement system that will accept real labeled data the day it exists.
