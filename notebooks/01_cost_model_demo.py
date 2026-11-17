"""Notebook 01 — the cost model, worked by hand on one research task.

Run:  python notebooks/01_cost_model_demo.py

Shows, line by line, where the money goes for the model-only baseline
versus the total-cost router on the same task: the tool's output tokens,
how many times they re-enter the context, and what the output cap saves.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool_total_cost_router.profiles import learn_profiles, run_traces
from tool_total_cost_router.router import model_only_baseline, rank_plans
from tool_total_cost_router.tasks import generate_tasks
from tool_total_cost_router.tools import BY_NAME as TOOLS_BY_NAME

tasks = generate_tasks()
profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
task = next(t for t in tasks if t["type"] == "research" and t["difficulty"] == 2)

print(f"Task {task['id']}: {task['prompt']}\n")
for label, ranked in (
    ("model-only baseline", [model_only_baseline(task, profiles)]),
    ("total-cost router (top 3)", rank_plans(task, profiles)[:3]),
):
    print(label)
    for r in ranked:
        c = r.cost
        print(
            f"  {r.plan.label():42s} attempt=${c.total_usd:.6f} "
            f"(input ${c.input_cost_usd:.6f} = prompt {c.prompt_tokens} tok + "
            f"tool {c.tool_tokens_after_cap} tok x {profiles[r.plan.tool].re_reads} re-reads; "
            f"output ${c.output_cost_usd:.6f})  p={c.p_attempt:.3f}  "
            f"-> ${c.cost_per_resolved_usd:.6f}/resolved"
        )
    print()
print(
    "Reading: the baseline pays for ~1,700 tool tokens twice (two "
    "re-reads) at the balanced model's input price. The router either "
    "picks a terse tool or caps the verbose one at 128 tokens — the "
    "facts survive (retention 0.94) and the re-read bill collapses."
)
