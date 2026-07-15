# LIMITATIONS.md — InvoiceGuardian v1

An honest statement of what this system is and is not. These limits are deliberate scope decisions for an evaluated vertical slice, not oversights.

## Data and inputs
- All documents are synthetic and fictional. Real commercial documents were not used because publishing confidential contract and invoice data in a public demo would be irresponsible. Synthetic data with a pre-registered answer key is what makes the evaluation measurable.
- Digitally generated PDFs only. No OCR, no scanned documents, no handwriting.
- English only in the baseline. One evaluated bilingual (English/Arabic) case is a possible stretch item, not a shipped capability.
- One contract, one SOW, six invoices in dataset v1.3. Six further scenario families are specified but not yet built (spec section 8).

## Evaluation
- The evaluation is a known-answer synthetic benchmark, not a production distribution. Results demonstrate the pipeline's behavior on the specified exception families; they do not estimate real-world accuracy across arbitrary contracts.
- Sample sizes are small (3 planted exceptions, 1 mandatory escalation, 2 clean invoices). Hard gates are therefore expressed in counts, and single-unit differences between benchmark arms are treated as noise.
- The evaluation harness is deterministic code scoring against the answer keys. The LLM is never the evaluator.

## System behavior
- The system reports consistency of an invoice with the supplied contract and SOW. It does not decide whether to pay, does not declare fraud, does not determine whether services were actually delivered, and does not provide legal or accounting advice.
- Every external action is a draft requiring human approval. Nothing is ever sent, filed, or paid by the system.
- The model is used only for typed extraction and bounded semantic comparison. All arithmetic, date, cap, rate, and reference checks are ordinary code.
- Ambiguous scope questions are escalated to a human, by design. Escalation is scored as correct behavior, not a failure.
- The operational trace is a structured render of pipeline state (inputs, versions, rule results, model calls, evidence, disposition). It is not chain-of-thought and does not expose model reasoning.

## Engineering scope
- Single runtime model after benchmark selection; no routing, no consensus, no fine-tuning in v1.
- No authentication, no multi-user support, no persistent accounts. Demo scenarios and run history live in flat files.
- Single deployable unit on one host. Availability targets appropriate to a demo, not production.
- Generalization to other document types (purchase orders, change orders, amendments) is an extension path, not a tested capability.
