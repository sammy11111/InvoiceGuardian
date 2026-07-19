"""Unit tests for the view-projection layer (src/invoiceguardian/api/view.py):
reconstructing structured invoice lines from the flat extracted_facts
key/value convention, and line-status classification."""

from __future__ import annotations

import pytest

from invoiceguardian.analyze.persist import load_persisted_result, persisted_results_exist
from invoiceguardian.api.view import build_scenario_detail, decision_mode_for

pytestmark = pytest.mark.skipif(
    not persisted_results_exist(),
    reason="scenario runs not persisted; run `python -m invoiceguardian.analyze --all --persist`",
)


def test_s5_reconstructs_three_lines_in_order_all_clean() -> None:
    result = load_persisted_result("INV-2026-065")
    detail = build_scenario_detail(result)

    assert [line.line_id for line in detail.lines] == ["L1", "L2", "L3"]
    assert all(line.status == "clean" for line in detail.lines)
    assert detail.lines[0].description == "Senior Consultant — ERP implementation support"
    assert detail.lines[0].hours == 95
    assert detail.lines[0].rate_cad == "150.00"
    assert detail.lines[0].amount_cad == "14250.00"


def test_s5_invoice_level_finding_is_separated_from_lines() -> None:
    result = load_persisted_result("INV-2026-065")
    detail = build_scenario_detail(result)

    assert len(detail.invoice_level_findings) == 1
    assert detail.invoice_level_findings[0].scope == "invoice"
    assert detail.invoice_level_findings[0].invoice_line_id is None
    # The invoice-level finding is not reflected as a line-scoped flag.
    assert all(line.status == "clean" for line in detail.lines)


def test_s1_line_with_rate_mismatch_is_flagged_other_line_clean() -> None:
    result = load_persisted_result("INV-2026-061")
    detail = build_scenario_detail(result)

    by_id = {line.line_id: line for line in detail.lines}
    assert by_id["L1"].status == "flagged"
    assert by_id["L2"].status == "clean"


def test_single_line_scenario_reconstructs_exactly_one_line() -> None:
    result = load_persisted_result("INV-2026-064")
    detail = build_scenario_detail(result)
    assert [line.line_id for line in detail.lines] == ["L1"]


def test_decision_mode_deterministic_vs_escalate_vs_model_assisted() -> None:
    s1 = build_scenario_detail(load_persisted_result("INV-2026-061"))
    assert decision_mode_for(s1.findings[0]) == "deterministic check"

    s5 = build_scenario_detail(load_persisted_result("INV-2026-065"))
    assert decision_mode_for(s5.findings[0]) == "deterministic check"

    # Whichever scenario currently carries an ESCALATE finding (S2 in this
    # frozen run) must report "human review required" — checked generically
    # so this doesn't hardcode the Fable-adjudicated S2/S4 divergence.
    for invoice_id in ["INV-2026-062", "INV-2026-063", "INV-2026-064"]:
        detail = build_scenario_detail(load_persisted_result(invoice_id))
        for finding in detail.findings:
            if finding.disposition.value == "ESCALATE":
                assert decision_mode_for(finding) == "human review required"
            else:
                assert decision_mode_for(finding) == "model-assisted match"
