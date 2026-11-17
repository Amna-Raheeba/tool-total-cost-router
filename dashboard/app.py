"""Streamlit dashboard over the real total-cost routing pipeline.

Every tab calls the same router, profiles and simulator the library,
CLI and evaluation use — not a mock.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from helpers import (
    load_profiles,
    load_summary,
    optimal_cap_table,
    profile_table,
    route_task,
)
from tool_total_cost_router.tasks import load_tasks

ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Tool Total-Cost Router", layout="wide")
st.title("Tool Total-Cost Router")
st.write(
    "Model-only routers pick the cheapest model. This one prices the "
    "whole agent loop: model tokens + tool-output tokens re-injected "
    "into context + retry cost — and picks (model, tool, output-cap) "
    "jointly by expected $/resolved-task."
)

summary = load_summary()
profiles = load_profiles()
tasks = load_tasks(ROOT / "data" / "tasks.jsonl")

tab_overview, tab_route, tab_profiles, tab_caps = st.tabs(
    ["Overview", "Route a task", "Tool profiles", "Optimal caps"]
)

with tab_overview:
    tc, mo = summary["total_cost"], summary["model_only"]
    oc = summary.get("optimal_cap")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total-cost $/resolved", f"${tc['cost_per_resolved_usd']:.6f}")
    c2.metric("Model-only $/resolved", f"${mo['cost_per_resolved_usd']:.6f}")
    c3.metric("Saving", f"{summary['saving_pct']}%")
    c4.metric("Tool effect alone", f"{summary['tool_effect_saving_pct']}%")
    st.write(
        f"Success rate: total-cost **{tc['success_rate']:.0%}** vs "
        f"model-only **{mo['success_rate']:.0%}** over {tc['n_tasks']} tasks. "
        f"Mean tokens/task: **{tc['mean_tokens_per_task']}** vs "
        f"**{mo['mean_tokens_per_task']}**."
    )
    if oc is not None:
        st.write(
            f"Optimal-cap (retention-safe) routing: "
            f"**${oc['cost_per_resolved_usd']:.6f}**/resolved, success "
            f"**{oc['success_rate']:.0%}** — "
            f"{summary['optimal_cap_saving_pct']}% cheaper than model-only, "
            f"success delta vs the unconstrained router "
            f"{summary['optimal_cap_success_delta']:+.2f}, cost delta "
            f"{summary['optimal_cap_cost_delta_pct']:+.1f}%."
        )
    st.subheader("Cost per resolved task by task type")
    rows = []
    for task_type in sorted(tc["by_type"]):
        rows.append(
            {
                "type": task_type,
                "total_cost $/resolved": tc["by_type"][task_type]["cost_per_resolved_usd"],
                "model_only $/resolved": mo["by_type"][task_type]["cost_per_resolved_usd"],
                "success (total-cost)": tc["by_type"][task_type]["success_rate"],
            }
        )
    st.dataframe(rows, width="stretch")

with tab_route:
    task_id = st.selectbox(
        "Task",
        [t["id"] for t in tasks],
        format_func=lambda tid: f"{tid} — {next(t for t in tasks if t['id'] == tid)['prompt'][:70]}…",
    )
    if st.button("Route this task"):
        result = route_task(task_id)
        st.write(f"**Prompt:** {result['task']['prompt']}")
        a, b, c = st.columns(3)
        a.subheader("Total-cost router")
        a.write(result["total_cost"])
        b.subheader("Model-only router")
        b.write(result["model_only"])
        c.subheader("Optimal-cap router")
        c.write(result["optimal_cap"])
        st.subheader("Top 5 total-cost plans")
        st.dataframe(result["total_cost"]["top_plans"], width="stretch")

with tab_profiles:
    st.write(
        "Per-tool output-cost profiles learned offline from 600 mocked "
        "traces. The router prices on these numbers."
    )
    st.dataframe(profile_table(profiles), width="stretch")

with tab_caps:
    st.write(
        "The per-tool optimal-cap advisor: for each tool, the cheapest "
        "output cap the measured retention-vs-cap curve shows preserving "
        "at least 95% of the facts. The optimal-cap router uses each "
        "tool only at its advised cap, so it never trades facts for "
        "dollars. 'Retention one cap down' shows the cliff the advisor "
        "is standing on."
    )
    st.dataframe(optimal_cap_table(profiles), width="stretch")
