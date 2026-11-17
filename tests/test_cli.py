"""Tests for the CLI entry points (run against the real data files)."""
import json
from pathlib import Path

import pytest

from tool_total_cost_router.cli import main

ROOT = Path(__file__).resolve().parent.parent


def test_cli_models(capsys):
    assert main(["models"]) == 0
    out = capsys.readouterr().out
    assert "flash-lite" in out and "flash" in out and "pro" in out


def test_cli_demo(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "total-cost router" in out
    assert "model-only router" in out
    assert "optimal-cap router" in out


def test_cli_route(capsys):
    assert main(["route", "--task", "T051"]) == 0
    out = capsys.readouterr().out
    assert "T051" in out
    assert "Model-only baseline" in out


def test_cli_learn_writes_profiles(tmp_path, monkeypatch, capsys):
    # Learn against a temp data dir so the real profiles file is untouched.
    import tool_total_cost_router.cli as cli

    data = tmp_path / "data"
    data.mkdir()
    (data / "tasks.jsonl").write_text(
        (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(cli, "DATA", data)
    assert main(["learn"]) == 0
    profiles = json.loads((data / "tool_profiles.json").read_text(encoding="utf-8"))
    assert set(profiles) == {
        "calculator", "api_lookup", "database_lookup",
        "code_executor", "web_search", "document_reader",
    }


def test_evaluation_summary_file_matches_cli_output():
    summary = json.loads((ROOT / "results" / "evaluation_summary.json").read_text(encoding="utf-8"))
    assert summary["saving_pct"] > 0
    assert summary["tool_effect_saving_pct"] > 0
    assert summary["total_cost"]["n_tasks"] == 100
    assert summary["optimal_cap"]["n_tasks"] == 100
    assert summary["optimal_cap_saving_pct"] > 0


@pytest.mark.skipif(
    not (ROOT / "results" / "evaluation.csv").exists(), reason="evaluation not run yet"
)
def test_evaluation_csv_shape():
    lines = (ROOT / "results" / "evaluation.csv").read_text(encoding="utf-8").strip().split("\n")
    assert lines[0].startswith("task_id,type,difficulty,router")
    assert len(lines) == 1 + 400  # 100 tasks x 4 routers
    routers = {line.split(",")[3] for line in lines[1:]}
    assert routers == {"total_cost", "model_only", "tool_only", "optimal_cap"}


def test_cli_caps(capsys):
    assert main(["caps"]) == 0
    out = capsys.readouterr().out
    assert "Optimal caps" in out
    assert "144" in out  # every tool's advised cap on this dataset
    assert "calculator" in out and "document_reader" in out
