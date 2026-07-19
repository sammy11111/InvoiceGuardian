/**
 * Mirrors src/invoiceguardian/schemas/runtime.py and
 * src/invoiceguardian/api/view.py exactly — field names, enum values, and
 * evidence discriminated-union shapes must match the persisted JSON.
 */

export type InvoiceDisposition = "CLEAN" | "EXCEPTIONS_FOUND" | "ESCALATION_REQUIRED";
export type FindingDisposition = "AUTO_EXCEPTION" | "SEMANTIC_EXCEPTION" | "ESCALATE";
export type ActionType = "DRAFT_VENDOR_CLARIFICATION" | "HUMAN_REVIEW";
export type ApprovalState = "NO_ACTION_REQUIRED" | "AWAITING_REVIEW" | "APPROVED" | "REJECTED";
export type ExceptionType =
  | "RATE_MISMATCH"
  | "UNAUTHORIZED_SERVICE"
  | "SCOPE_AMBIGUITY"
  | "AGGREGATE_CAP_EXCEEDED";
export type FindingScope = "line" | "invoice";
export type LineStatus = "clean" | "flagged" | "escalated";
export type DecisionMode = "deterministic check" | "model-assisted match" | "human review required";

export interface SupportingQuoteEvidence {
  kind: "supporting_quote";
  document_id: string;
  section: string;
  page: number;
  quote: string;
}

export interface InvoiceLineEvidence {
  kind: "invoice_line";
  document_id: string;
  line_id: string;
}

export interface SearchedSection {
  document_id: string;
  sections: string[];
}

export interface AbsenceQuote {
  document_id: string;
  section: string;
  page: number;
  quote: string;
}

export interface AbsenceOfAuthorizationEvidence {
  kind: "absence_of_authorization";
  searched: SearchedSection[];
  quotes: AbsenceQuote[];
  statement: string;
}

export interface ComputedTotalEvidence {
  kind: "computed_total";
  document_id: string;
  value_cad: string;
}

export type EvidenceReference =
  | SupportingQuoteEvidence
  | InvoiceLineEvidence
  | AbsenceOfAuthorizationEvidence
  | ComputedTotalEvidence;

export interface ExceptionFinding {
  finding_type: ExceptionType;
  basis: "deterministic" | "semantic" | "absence";
  scope: FindingScope;
  invoice_line_id: string | null;
  disposition: FindingDisposition;
  action: ActionType;
  evidence: EvidenceReference[];
  computed_values: Record<string, string> | null;
}

export interface DraftedAction {
  action_type: ActionType;
  summary: string;
}

export interface SourceRef {
  document_id: string;
  section: string;
  page: number;
}

export interface ExtractedFactRecord {
  document_id: string;
  field: string;
  value: string;
  source: SourceRef | null;
}

export interface DeterministicRuleResult {
  rule_name: string;
  invoice_line_id: string | null;
  passed: boolean;
  detail: string | null;
}

export interface ModelCallRecord {
  model_id: string;
  effort: string | null;
  purpose: string;
  schema_valid: boolean;
  retried: boolean;
}

export interface RunVersions {
  dataset_version: string;
  schema_version: string;
  prompt_version: string;
}

export interface OperationalTrace {
  invoice_id: string;
  versions: RunVersions;
  input_document_ids: string[];
  extracted_facts: ExtractedFactRecord[];
  deterministic_rules: DeterministicRuleResult[];
  model_calls: ModelCallRecord[];
  findings: ExceptionFinding[];
  disposition: InvoiceDisposition;
  approval_state: ApprovalState;
}

export interface ScenarioSummary {
  invoice_id: string;
  scenario_label: string;
  invoice_date: string;
  service_period_start: string;
  service_period_end: string;
  sow_reference: string;
  currency: string;
  invoice_total_cad: string;
  disposition: InvoiceDisposition;
}

export interface InvoiceLineView {
  line_id: string;
  description: string;
  hours: number;
  rate_cad: string;
  amount_cad: string;
  status: LineStatus;
}

export interface ScenarioDetail {
  summary: ScenarioSummary;
  lines: InvoiceLineView[];
  invoice_level_findings: ExceptionFinding[];
  findings: ExceptionFinding[];
  approval_state: ApprovalState;
  drafted_action: DraftedAction | null;
  trace: OperationalTrace;
}
