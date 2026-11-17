"""Notebook 02 — the full 100-task evaluation, reproduced.

Run:  python notebooks/02_evaluation.py

Runs all routers (total-cost, model-only, tool-only ablation, and
the retention-safe optimal-cap arm) over the 100 scripted tasks and
prints the comparison. Writes results/evaluation.csv,
results/evaluation_summary.json and results/evaluation_summary.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool_total_cost_router.evaluate import (
    compare,
    run_evaluation,
    write_csv,
    write_summary,
)
from tool_total_cost_router.profiles import learn_profiles, run_traces
from tool_total_cost_router.tasks import generate_tasks
from tool_total_cost_router.tools import BY_NAME as TOOLS_BY_NAME

ROOT = Path(__file__).resolve().parent.parent

tasks = generate_tasks()
profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
results = run_evaluation(tasks, profiles)
summary = compare(results)
write_csv(results, ROOT / "results" / "evaluation.csv")
write_summary(summary, ROOT / "results" / "evaluation_summary.json")
print(json.dumps(summary, indent=2))
