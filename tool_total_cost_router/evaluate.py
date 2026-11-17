"""Head-to-head evaluation: total-cost router vs model-only baseline.

Both routers run the same 100 scripted tasks through the same
simulator with the same seed. Every number reported comes from these
runs; nothing is estimated after the fact.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .profiles import ToolProfile
from .router import model_only_baseline, rank_plans, rank_plans_optimal_cap
from .simulator import TaskResult, simulate_task


def run_evaluation(
    tasks: list[dict],
    profiles: dict[str, ToolProfile],
    seed: int = 20261117,
    max_attempts: int = 3,
) -> dict[str, list[TaskResult]]:
    """Run all tasks under every router. Returns results keyed by router."""
    results: dict[str, list[TaskResult]] = {
        "total_cost": [],
        "model_only": [],
        "tool_only": [],
        "optimal_cap": [],
    }
    for task in tasks:
        ranked = rank_plans(task, profiles)
        results["total_cost"].append(
            simulate_task(task, ranked, profiles, "total_cost", seed, max_attempts)
        )
        baseline = model_only_baseline(task, profiles)
        results["model_only"].append(
            simulate_task(task, [baseline], profiles, "model_only", seed, max_attempts)
        )
        # Ablation: same model tier as the baseline, optimise only the
        # tool and the output cap. This isolates the novel contribution
        # (tool-output routing) from plain model-tier arbitrage.
        same_model = [r for r in ranked if r.plan.model == baseline.plan.model]
        results["tool_only"].append(
            simulate_task(task, same_model, profiles, "tool_only", seed, max_attempts)
        )
        # Retention-safe arm: each tool used only at its advisor-set
        # optimal cap (cheapest cap preserving >= 95% of facts).
        safe_ranked = rank_plans_optimal_cap(task, profiles)
        results["optimal_cap"].append(
            simulate_task(task, safe_ranked, profiles, "optimal_cap", seed, max_attempts)
        )
    return results


def summarise(results: list[TaskResult]) -> dict:
    n = len(results)
    resolved = [r for r in results if r.success]
    total_cost = sum(r.total_cost_usd for r in results)
    by_type: dict[str, dict] = {}
    for r in results:
        bucket = by_type.setdefault(r.task_type, {"n": 0, "resolved": 0, "cost": 0.0})
        bucket["n"] += 1
        bucket["resolved"] += 1 if r.success else 0
        bucket["cost"] += r.total_cost_usd
    return {
        "n_tasks": n,
        "resolved": len(resolved),
        "success_rate": round(len(resolved) / n, 4) if n else 0.0,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_resolved_usd": round(total_cost / len(resolved), 6) if resolved else None,
        "mean_tokens_per_task": round(sum(r.total_tokens for r in results) / n, 1) if n else 0.0,
        "mean_attempts": round(sum(r.attempts for r in results) / n, 2) if n else 0.0,
        "by_type": {
            k: {
                "n": v["n"],
                "success_rate": round(v["resolved"] / v["n"], 4),
                "cost_per_resolved_usd": round(v["cost"] / v["resolved"], 6) if v["resolved"] else None,
            }
            for k, v in sorted(by_type.items())
        },
    }


def compare(results: dict[str, list[TaskResult]]) -> dict:
    """Summary for all routers plus the head-to-head deltas."""
    a = summarise(results["total_cost"])
    b = summarise(results["model_only"])
    c = summarise(results["tool_only"])
    out = {"total_cost": a, "model_only": b, "tool_only": c}
    if "optimal_cap" in results:
        out["optimal_cap"] = summarise(results["optimal_cap"])
    if a["cost_per_resolved_usd"] and b["cost_per_resolved_usd"]:
        out["saving_per_resolved_usd"] = round(b["cost_per_resolved_usd"] - a["cost_per_resolved_usd"], 6)
        out["saving_pct"] = round(
            100 * (b["cost_per_resolved_usd"] - a["cost_per_resolved_usd"]) / b["cost_per_resolved_usd"], 1
        )
    if c["cost_per_resolved_usd"] and b["cost_per_resolved_usd"]:
        # Tool-output routing alone (model tier held fixed).
        out["tool_effect_saving_pct"] = round(
            100 * (b["cost_per_resolved_usd"] - c["cost_per_resolved_usd"]) / b["cost_per_resolved_usd"], 1
        )
    out["success_rate_delta"] = round(a["success_rate"] - b["success_rate"], 4)
    if "optimal_cap" in out and out["optimal_cap"]["cost_per_resolved_usd"] and b["cost_per_resolved_usd"]:
        # Retention-safe routing vs the model-only baseline, and vs the
        # unconstrained total-cost router (cost of the retention guarantee).
        oc = out["optimal_cap"]
        out["optimal_cap_saving_pct"] = round(
            100 * (b["cost_per_resolved_usd"] - oc["cost_per_resolved_usd"]) / b["cost_per_resolved_usd"], 1
        )
        out["optimal_cap_success_delta"] = round(oc["success_rate"] - a["success_rate"], 4)
        out["optimal_cap_cost_delta_pct"] = round(
            100 * (oc["cost_per_resolved_usd"] - a["cost_per_resolved_usd"]) / a["cost_per_resolved_usd"], 1
        )
    return out


def write_csv(results: dict[str, list[TaskResult]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["task_id", "type", "difficulty", "router", "success", "attempts",
             "total_cost_usd", "total_tokens", "final_plan"]
        )
        for router, rows in results.items():
            for r in rows:
                writer.writerow([
                    r.task_id, r.task_type, r.difficulty, router,
                    int(r.success), r.attempts,
                    f"{r.total_cost_usd:.6f}", r.total_tokens, r.final_plan,
                ])


def write_summary(summary: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_summary_md(summary: dict, path: str | Path) -> None:
    """Render the Markdown summary from the same summary dict.

    The .md was hand-written in v0.1.0 and could drift from the JSON;
    it is now generated, so `evaluate` reproduces both files.
    """
    def dollars(v):
        return f"${v:.6f}" if v is not None else "—"

    tc, mo = summary["total_cost"], summary["model_only"]
    lines = [
        "# Evaluation Summary — 100 scripted tasks (seed 20261117)",
        "",
        "| Router | $/resolved-task | Success rate | Mean tokens/task | Mean attempts |",
        "|---|---|---|---|---|",
        f"| **Total-cost (joint)** | **{dollars(tc['cost_per_resolved_usd'])}** | {tc['success_rate']:.2f} ({tc['resolved']}/{tc['n_tasks']}) | {tc['mean_tokens_per_task']} | {tc['mean_attempts']} |",
        f"| Model-only baseline | {dollars(mo['cost_per_resolved_usd'])} | {mo['success_rate']:.2f} ({mo['resolved']}/{mo['n_tasks']}) | {mo['mean_tokens_per_task']} | {mo['mean_attempts']} |",
    ]
    if "tool_only" in summary:
        to = summary["tool_only"]
        lines.append(
            f"| Tool-only ablation | {dollars(to['cost_per_resolved_usd'])} | {to['success_rate']:.2f} ({to['resolved']}/{to['n_tasks']}) | {to['mean_tokens_per_task']} | {to['mean_attempts']} |"
        )
    if "optimal_cap" in summary:
        oc = summary["optimal_cap"]
        lines.append(
            f"| Optimal-cap (retention-safe) | {dollars(oc['cost_per_resolved_usd'])} | {oc['success_rate']:.2f} ({oc['resolved']}/{oc['n_tasks']}) | {oc['mean_tokens_per_task']} | {oc['mean_attempts']} |"
        )
    lines += [
        "",
        f"- **Head-to-head saving: {summary.get('saving_pct', '—')}%** ({dollars(summary.get('saving_per_resolved_usd'))} per resolved task).",
        f"- **Tool effect alone (model tier held fixed): {summary.get('tool_effect_saving_pct', '—')}%.**",
    ]
    if "optimal_cap" in summary:
        lines.append(
            f"- **Optimal-cap routing: {summary.get('optimal_cap_saving_pct', '—')}% cheaper than model-only**, "
            f"success-rate delta vs the unconstrained router: {summary.get('optimal_cap_success_delta', '—'):+.2f}, "
            f"cost delta vs the unconstrained router: {summary.get('optimal_cap_cost_delta_pct', '—'):+.1f}%."
        )
    lines += [
        f"- Success-rate delta: {summary.get('success_rate_delta', '—'):+.2f}.",
        "",
        "Per-type $/resolved (total-cost vs model-only):",
        "",
        "| Type | Total-cost | Model-only |",
        "|---|---|---|",
    ]
    for task_type in sorted(tc["by_type"]):
        lines.append(
            f"| {task_type} | {dollars(tc['by_type'][task_type]['cost_per_resolved_usd'])} "
            f"| {dollars(mo['by_type'][task_type]['cost_per_resolved_usd'])} |"
        )
    lines += [
        "",
        "The effect is largest on research tasks, where the baseline's default",
        "tool (web search, ~1,700 tokens, re-read twice) dominates the bill.",
        "Full per-task rows: `results/evaluation.csv`.",
        "Reproduce: `python -m tool_total_cost_router evaluate`.",
        "",
    ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
