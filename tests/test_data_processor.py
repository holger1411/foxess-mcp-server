"""Tests for report processing — focus on the PV-vs-AC-yield derived field.

Background: the FoxESS `/device/report` field `generation` is the inverter's
AC yield, NOT PV module generation. On battery systems, DC-side battery charging
is missing from `generation`. We expose a documented approximation
`pv_generation_estimate_kwh = generation + charge_energy_total`.
"""

import pytest

from foxess_mcp_server.foxess.data_processor import DataProcessor


def _day_report_response():
    """A sunny-morning day where most PV charged the battery (generation undercounts)."""
    gen = [0.0] * 24
    gen[4] = 0.1
    gen[8] = 1.9  # AC yield total = 2.0 kWh
    charge = [0.0] * 24
    charge[7] = 0.6
    charge[9] = 2.3
    charge[10] = 0.7  # battery charge total = 3.6 kWh
    return {
        "errno": 0,
        "result": [
            {"variable": "generation", "values": gen, "unit": "kWh"},
            {"variable": "chargeEnergyToTal", "values": charge, "unit": "kWh"},
        ],
    }


def test_report_totals_include_pv_generation_estimate():
    out = DataProcessor().process_report_response(_day_report_response(), "day", 2026, 6, 2)
    totals = out["totals"]
    assert "pv_generation_estimate_kwh" in totals
    assert totals["pv_generation_estimate_kwh"] == pytest.approx(
        totals["generation"] + totals["charge_energy_total"]
    )
    # The whole point: the estimate is meaningfully higher than raw AC generation.
    assert totals["pv_generation_estimate_kwh"] > totals["generation"]


def test_report_summary_table_includes_per_period_pv_estimate():
    out = DataProcessor().process_report_response(_day_report_response(), "day", 2026, 6, 2)
    for row in out["summary_table"]:
        assert "pv_generation_estimate" in row
        assert row["pv_generation_estimate"] == pytest.approx(
            row.get("generation", 0) + row.get("charge_energy_total", 0)
        )


def test_report_does_not_drop_existing_fields():
    """Acceptance: no existing field/name is removed — only added."""
    out = DataProcessor().process_report_response(_day_report_response(), "day", 2026, 6, 2)
    for field in ("generation", "feedin", "grid_consumption", "charge_energy_total",
                  "discharge_energy_total"):
        # present when the API returned it; generation + charge are in the fixture
        if field in ("generation", "charge_energy_total"):
            assert field in out["totals"]
    assert "variables" in out and "summary_table" in out and "time_labels" in out
