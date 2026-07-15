import json
from pathlib import Path

from invoiceguardian.schemas.evaluation import EvaluationDataset

ANSWER_KEYS_PATH = Path(__file__).resolve().parent.parent / "answer_keys.json"


def _load_raw() -> dict[str, object]:
    return json.loads(ANSWER_KEYS_PATH.read_text())


def test_answer_keys_json_parses_into_evaluation_dataset() -> None:
    dataset = EvaluationDataset.model_validate(_load_raw())

    assert dataset.dataset_version == "v1.3-2026-07-15"
    assert dataset.schema_version == "1.2"
    assert dataset.extraction_field_count == 106
    assert len(dataset.scenarios) == 6
    assert len(dataset.extraction_manifest) == 106


def test_s1_scenario_has_one_deterministic_rate_mismatch_finding() -> None:
    dataset = EvaluationDataset.model_validate(_load_raw())
    s1 = next(s for s in dataset.scenarios if s.scenario_id == "S1")

    assert s1.expected_invoice_disposition == "EXCEPTIONS_FOUND"
    assert len(s1.expected_findings) == 1

    finding = s1.expected_findings[0]
    assert finding.finding_type == "RATE_MISMATCH"
    assert finding.basis == "deterministic"
    assert finding.invoice_line_id == "L1"
    assert finding.expected_values == {
        "billed_rate_cad": "175.00",
        "authorized_rate_cad": "150.00",
    }
    assert finding.evidence[0].kind == "supporting_quote"
    assert finding.evidence[0].quote == (
        "Senior Consultant services shall be billed at CAD $150.00 per hour."
    )


def test_s2_absence_of_authorization_evidence_shape() -> None:
    dataset = EvaluationDataset.model_validate(_load_raw())
    s2 = next(s for s in dataset.scenarios if s.scenario_id == "S2")
    finding = s2.expected_findings[0]

    absence = finding.evidence[0]
    assert absence.kind == "absence_of_authorization"
    assert absence.statement == (
        "No authorization matching this line item was found in the searched documents."
    )
    assert {s.document_id for s in absence.searched} == {"SOW-2026-03", "MSA-2026-014"}


def test_s3_and_s6_are_clean_with_no_findings() -> None:
    dataset = EvaluationDataset.model_validate(_load_raw())
    for scenario_id in ("S3", "S6"):
        scenario = next(s for s in dataset.scenarios if s.scenario_id == scenario_id)
        assert scenario.expected_findings == []
        assert scenario.expected_invoice_disposition == "CLEAN"
        assert scenario.trap == "false_positive_guard"


def test_s4_is_the_mandatory_escalation() -> None:
    dataset = EvaluationDataset.model_validate(_load_raw())
    s4 = next(s for s in dataset.scenarios if s.scenario_id == "S4")

    assert s4.expected_invoice_disposition == "ESCALATION_REQUIRED"
    finding = s4.expected_findings[0]
    assert finding.expected_disposition == "ESCALATE"
    assert finding.confidence_expectation == "ABSTAIN"


def test_s5_aggregate_cap_finding_is_invoice_scoped() -> None:
    dataset = EvaluationDataset.model_validate(_load_raw())
    s5 = next(s for s in dataset.scenarios if s.scenario_id == "S5")
    finding = s5.expected_findings[0]

    assert finding.finding_type == "AGGREGATE_CAP_EXCEEDED"
    assert finding.scope == "invoice"
    assert finding.invoice_line_id is None
    computed = next(e for e in finding.evidence if e.kind == "computed_total")
    assert computed.value_cad == "25750.00"
