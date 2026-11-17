"""Dashboard helpers: pure functions, no Streamlit import.

Kept separate from app.py so the logic is unit-tested (see
tests/test_dashboard_helpers.py) and the dashboard is a thin view over
the real pipeline, not a second implementation of it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Usable from the repo root and from inside dashboard/ alike.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tool_total_cost_router.evaluate import compare, run_evaluation  # noqa: E402
from tool_total_cost_router.profiles import (  # noqa: E402
    learn_profiles,
    optimal_caps,
    profiles_from_json,
    run_traces,
)
from tool_total_cost_router.router import (  # noqa: E402
    model_only_baseline,
    rank_plans,
    rank_plans_optimal_cap,
)
from tool_total_cost_router.simulator import simulate_task  # noqa: E402
from tool_total_cost_router.tasks import load_tasks  # noqa: E402
from tool_total_cost_router.tools import BY_NAME as TOOLS_BY_NAME  # noqa: E402

ROOT = _ROOT


def load_profiles() -> dict:
    """Load learned profiles from data/, learning them if missing."""
    path = ROOT / "data" / "tool_profiles.json"
    if path.exists():
        return profiles_from_json(path.read_text(encoding="utf-8"))
    tasks = load_tasks(ROOT / "data" / "tasks.jsonl")
    return learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))


def load_summary() -> dict:
    """Load the evaluation summary, running it if the file is missing."""
    path = ROOT / "results" / "evaluation_summary.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    profiles = load_profiles()
    tasks = load_tasks(ROOT / "data" / "tasks.jsonl")
    return compare(run_evaluation(tasks, profiles))


def profile_table(profiles: dict) -> list[dict]:
    """One row per tool: the numbers the router actually prices on."""
    rows = []
    for name, p in sorted(profiles.items(), key=lambda kv: kv[1].median_tokens):
        rows.append(
            {
                "tool": name,
                "median_tokens": round(p.median_tokens),
                "p90_tokens": round(p.p90_tokens),
                "compressibility": round(p.compressibility, 2),
                "re_reads": p.re_reads,
                "retry_rate": round(p.retry_rate, 2),
                "retention@128": round(p.retained_at(128), 2),
                "retention@256": round(p.retained_at(256), 2),
            }
        )
    return rows


def optimal_cap_table(profiles: dict, threshold: float = 0.95) -> list[dict]:
    """One row per tool: the advisor's optimal cap and what it buys.

    The optimal cap is the cheapest measured cap preserving at least
    ``threshold`` of the facts (see profiles.ToolProfile.optimal_cap).
    The table also shows retention at the next cap down, so the reader
    can see the cliff the advisor is standing on.
    """
    caps = optimal_caps(profiles, threshold)
    rows = []
    for name, p in sorted(profiles.items(), key=lambda kv: kv[1].median_tokens):
        cap = caps[name]
        lower = [c for c in sorted(p.retention) if cap is not None and c < cap]
        rows.append(
            {
                "tool": name,
                "optimal_cap": "uncapped" if cap is None else cap,
                "retention_at_optimal": round(p.retained_at(cap), 3),
                "retention_one_cap_down": (
                    round(p.retained_at(lower[-1]), 3) if lower else None
                ),
                "median_tokens": round(p.median_tokens),
                "re_reads": p.re_reads,
            }
        )
    return rows


def route_task(task_id: str) -> dict:
    """Route one task with all routers and simulate each, JSON-safe."""
    profiles = load_profiles()
    tasks = load_tasks(ROOT / "data" / "tasks.jsonl")
    task = next((t for t in tasks if t["id"] == task_id), tasks[0])
    ranked = rank_plans(task, profiles)
    baseline = model_only_baseline(task, profiles)
    safe_ranked = rank_plans_optimal_cap(task, profiles)
    tc = simulate_task(task, ranked, profiles, "total_cost")
    mo = simulate_task(task, [baseline], profiles, "model_only")
    oc = simulate_task(task, safe_ranked, profiles, "optimal_cap")
    return {
        "task": task,
        "total_cost": {
            "plan": tc.final_plan,
            "success": tc.success,
            "attempts": tc.attempts,
            "cost_usd": round(tc.total_cost_usd, 6),
            "tokens": tc.total_tokens,
            "top_plans": [
                {
                    "plan": r.plan.label(),
                    "cost_per_resolved_usd": round(r.cost_per_resolved, 6),
                    "p_attempt": round(r.cost.p_attempt, 3),
                }
                for r in ranked[:5]
            ],
        },
        "model_only": {
            "plan": mo.final_plan,
            "success": mo.success,
            "attempts": mo.attempts,
            "cost_usd": round(mo.total_cost_usd, 6),
            "tokens": mo.total_tokens,
        },
        "optimal_cap": {
            "plan": oc.final_plan,
            "success": oc.success,
            "attempts": oc.attempts,
            "cost_usd": round(oc.total_cost_usd, 6),
            "tokens": oc.total_tokens,
        },
    }
