"""AppTest for the Streamlit dashboard.

Skipped when Streamlit is not installed (CI installs pytest only —
see .github/workflows/ci.yml). Locally, the bare venv has Streamlit,
so this runs there and in the parent's verification.
"""
from pathlib import Path

import pytest

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parent.parent / "dashboard" / "app.py"


def _app() -> AppTest:
    at = AppTest.from_file(str(APP))
    at.run()
    return at


def test_dashboard_runs_with_no_exceptions():
    at = _app()
    assert len(at.exception) == 0


def test_dashboard_has_four_tabs():
    at = _app()
    assert [t.label for t in at.tabs] == [
        "Overview",
        "Route a task",
        "Tool profiles",
        "Optimal caps",
    ]


def test_overview_shows_headline_metrics():
    at = _app()
    labels = {m.label: m.value for m in at.metric}
    assert labels["Total-cost $/resolved"] == "$0.000122"
    assert labels["Model-only $/resolved"] == "$0.002368"
    assert labels["Saving"] == "94.8%"


def test_optimal_caps_table_renders():
    at = _app()
    tables = [df.value for df in at.dataframe]
    caps = next(t for t in tables if "optimal_cap" in t.columns)
    assert len(caps) == 6
    assert set(caps["optimal_cap"]) == {144}
    assert (caps["retention_at_optimal"] >= 0.95).all()
    assert (caps["retention_one_cap_down"] < 0.95).all()


def test_route_a_task_button_runs_both_routers():
    at = _app()
    assert len(at.button) == 1
    at.button[0].click().run()
    assert len(at.exception) == 0
    # The routed result renders three subheaders, one per router.
    subheaders = [s.value for s in at.subheader]
    assert "Total-cost router" in subheaders
    assert "Model-only router" in subheaders
    assert "Optimal-cap router" in subheaders
