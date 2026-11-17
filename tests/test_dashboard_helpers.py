"""Tests for the dashboard helpers (pure functions, no Streamlit)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))

from helpers import (
    load_profiles,
    load_summary,
    optimal_cap_table,
    profile_table,
    route_task,
)


def test_load_profiles():
    profiles = load_profiles()
    assert set(profiles) == {
        "calculator", "api_lookup", "database_lookup",
        "code_executor", "web_search", "document_reader",
    }


def test_profile_table_sorted_by_size():
    rows = profile_table(load_profiles())
    assert len(rows) == 6
    sizes = [r["median_tokens"] for r in rows]
    assert sizes == sorted(sizes)
    assert rows[0]["tool"] == "calculator"
    assert rows[-1]["tool"] == "document_reader"


def test_load_summary_has_both_routers():
    summary = load_summary()
    assert summary["saving_pct"] > 0
    assert summary["tool_effect_saving_pct"] > 0
    assert summary["total_cost"]["n_tasks"] == 100


def test_route_task_returns_both_routers():
    result = route_task("T051")
    assert result["task"]["id"] == "T051"
    assert "plan" in result["total_cost"]
    assert "plan" in result["model_only"]
    assert len(result["total_cost"]["top_plans"]) == 5
    costs = [p["cost_per_resolved_usd"] for p in result["total_cost"]["top_plans"]]
    assert costs == sorted(costs)


def test_optimal_cap_table():
    rows = optimal_cap_table(load_profiles())
    assert len(rows) == 6
    for row in rows:
        assert row["optimal_cap"] == 144  # measured: every tool crosses 0.95 at 144
        assert row["retention_at_optimal"] >= 0.95
        assert row["retention_one_cap_down"] < 0.95
    tools = [r["tool"] for r in rows]
    assert tools[0] == "calculator"
    assert tools[-1] == "document_reader"


def test_route_task_returns_optimal_cap_router():
    result = route_task("T051")
    assert "plan" in result["optimal_cap"]
    assert "cap-144" in result["optimal_cap"]["plan"]


def test_load_summary_has_optimal_cap_arm():
    summary = load_summary()
    assert "optimal_cap" in summary
    assert summary["optimal_cap"]["n_tasks"] == 100
    assert "optimal_cap_saving_pct" in summary
