"""Command-line interface: learn profiles, route, demo, evaluate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .evaluate import (
    compare,
    run_evaluation,
    summarise,
    write_csv,
    write_summary,
    write_summary_md,
)
from .models import MODELS
from .profiles import (
    learn_profiles,
    optimal_caps,
    profiles_from_json,
    profiles_to_json,
    run_traces,
)
from .router import model_only_baseline, rank_plans, rank_plans_optimal_cap
from .simulator import simulate_task
from .tasks import generate_tasks, load_tasks
from .tools import BY_NAME as TOOLS_BY_NAME

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"


def _load_profiles(path: Path):
    if path.exists():
        return profiles_from_json(path.read_text(encoding="utf-8"))
    tasks = load_tasks(DATA / "tasks.jsonl")
    traces = run_traces(tasks, list(TOOLS_BY_NAME))
    return learn_profiles(traces)


def cmd_learn(args: argparse.Namespace) -> int:
    tasks = load_tasks(DATA / "tasks.jsonl")
    traces = run_traces(tasks, list(TOOLS_BY_NAME))
    profiles = learn_profiles(traces)
    out = DATA / "tool_profiles.json"
    out.write_text(profiles_to_json(profiles), encoding="utf-8")
    for name, profile in sorted(profiles.items()):
        print(
            f"{name:18s} median={profile.median_tokens:7.0f} tok  "
            f"p90={profile.p90_tokens:7.0f}  compressibility={profile.compressibility:.2f}  "
            f"re_reads={profile.re_reads}  retry={profile.retry_rate:.2f}"
        )
    print(f"wrote {out} ({len(traces)} traces)")
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    profiles = _load_profiles(DATA / "tool_profiles.json")
    tasks = load_tasks(DATA / "tasks.jsonl")
    task = next((t for t in tasks if t["id"] == args.task), tasks[0])
    ranked = rank_plans(task, profiles)
    baseline = model_only_baseline(task, profiles)
    print(f"task {task['id']} [{task['type']}, difficulty {task['difficulty']}]")
    print(f"prompt: {task['prompt']}")
    print("\nTop 5 total-cost plans:")
    for r in ranked[:5]:
        print(f"  ${r.cost_per_resolved:.6f}/resolved  {r.plan.label()}  p={r.cost.p_attempt:.3f}")
    print(f"\nModel-only baseline: ${baseline.cost_per_resolved:.6f}/resolved  {baseline.plan.label()}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """One task, all routers, side by side — the 30-second story."""
    profiles = _load_profiles(DATA / "tool_profiles.json")
    tasks = load_tasks(DATA / "tasks.jsonl")
    task = next((t for t in tasks if t["type"] == "research"), tasks[0])
    ranked = rank_plans(task, profiles)
    baseline = model_only_baseline(task, profiles)
    safe_ranked = rank_plans_optimal_cap(task, profiles)
    tc = simulate_task(task, ranked, profiles, "total_cost")
    mo = simulate_task(task, [baseline], profiles, "model_only")
    oc = simulate_task(task, safe_ranked, profiles, "optimal_cap")
    print(f"task {task['id']}: {task['prompt']}")
    print(f"total-cost router : {tc.final_plan} -> success={tc.success} "
          f"attempts={tc.attempts} cost=${tc.total_cost_usd:.6f} tokens={tc.total_tokens}")
    print(f"model-only router : {mo.final_plan} -> success={mo.success} "
          f"attempts={mo.attempts} cost=${mo.total_cost_usd:.6f} tokens={mo.total_tokens}")
    print(f"optimal-cap router: {oc.final_plan} -> success={oc.success} "
          f"attempts={oc.attempts} cost=${oc.total_cost_usd:.6f} tokens={oc.total_tokens}")
    print("\nThe model-only router picks the cheapest adequate model and "
          "never sees the tool bill: a verbose tool's output re-enters "
          "the context on every turn. The total-cost router prices that "
          "return journey and picks (model, tool, cap) jointly. The "
          "optimal-cap router goes one step further: it only uses each "
          "tool at the cheapest cap measured to preserve >= 95% of the "
          "facts, so it never trades facts for dollars.")
    return 0


def cmd_caps(args: argparse.Namespace) -> int:
    """Print the per-tool optimal-cap advisor table."""
    profiles = _load_profiles(DATA / "tool_profiles.json")
    caps = optimal_caps(profiles, args.threshold)
    print(f"Optimal caps — cheapest measured cap preserving "
          f">= {args.threshold:.0%} of facts:\n")
    print(f"{'tool':18s} {'optimal cap':>11s} {'retention':>10s} {'median tok':>11s}")
    for name in sorted(profiles, key=lambda n: profiles[n].median_tokens):
        profile = profiles[name]
        cap = caps[name]
        retained = profile.retained_at(cap)
        cap_label = "uncapped" if cap is None else str(cap)
        print(f"{name:18s} {cap_label:>11s} {retained:>10.3f} {profile.median_tokens:>11.0f}")
    print("\nCaps come from each tool's own measured retention-vs-cap curve "
          "(see profiles.py); no cap is recommended that was not measured "
          "as safe. A tool whose curve never reaches the threshold is used "
          "uncapped.")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    profiles = _load_profiles(DATA / "tool_profiles.json")
    tasks = load_tasks(DATA / "tasks.jsonl")
    results = run_evaluation(tasks, profiles)
    summary = compare(results)
    write_csv(results, RESULTS / "evaluation.csv")
    write_summary(summary, RESULTS / "evaluation_summary.json")
    write_summary_md(summary, RESULTS / "evaluation_summary.md")
    print(json.dumps(summary, indent=2))
    return 0


def cmd_models(_args: argparse.Namespace) -> int:
    for m in MODELS:
        print(f"{m.name:12s} tier={m.tier:9s} capability={m.capability}  "
              f"in=${m.input_price_per_mtok}/M  out=${m.output_price_per_mtok}/M")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tool-total-cost-router",
        description="Route (model, tool, output-cap) jointly by total $/resolved-task.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("learn", help="Learn tool profiles from mocked traces").set_defaults(func=cmd_learn)
    p = sub.add_parser("route", help="Show ranked plans for one task")
    p.add_argument("--task", default=None)
    p.set_defaults(func=cmd_route)
    sub.add_parser("demo", help="One research task, all routers side by side").set_defaults(func=cmd_demo)
    sub.add_parser("evaluate", help="Run the 100-task head-to-head evaluation").set_defaults(func=cmd_evaluate)
    sub.add_parser("models", help="List the model tiers and prices").set_defaults(func=cmd_models)
    p = sub.add_parser("caps", help="Show the per-tool optimal-cap advisor table")
    p.add_argument("--threshold", type=float, default=0.95,
                   help="Minimum retained-fact fraction (default 0.95)")
    p.set_defaults(func=cmd_caps)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
