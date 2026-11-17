"""Tests for the per-tool optimal-cap advisor and retention-safe routing."""
from tool_total_cost_router.evaluate import compare, run_evaluation
from tool_total_cost_router.profiles import (
    ToolProfile,
    learn_profiles,
    optimal_caps,
    run_traces,
)
from tool_total_cost_router.router import (
    rank_plans_optimal_cap,
    route_optimal_cap,
)
from tool_total_cost_router.tasks import generate_tasks
from tool_total_cost_router.tools import BY_NAME as TOOLS_BY_NAME


def _profile(retention):
    return ToolProfile(
        tool="test_tool",
        median_tokens=500.0,
        p90_tokens=900.0,
        compressibility=0.2,
        re_reads=2,
        retry_rate=0.0,
        n_traces=10,
        retention=dict(retention),
    )


def test_optimal_cap_cheapest_clearing_threshold():
    p = _profile({64: 0.40, 128: 0.90, 144: 0.96, 256: 1.0})
    assert p.optimal_cap(0.95) == 144
    assert p.optimal_cap(0.99) == 256
    assert p.optimal_cap(0.40) == 64


def test_optimal_cap_none_when_threshold_unreachable():
    p = _profile({64: 0.40, 128: 0.90, 256: 0.93})
    assert p.optimal_cap(0.95) is None
    assert p.retained_at(None) == 1.0  # uncapped keeps everything


def test_optimal_caps_reads_each_tools_own_curve():
    tasks = generate_tasks()
    profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
    caps = optimal_caps(profiles)
    assert set(caps) == set(profiles)
    for tool, cap in caps.items():
        assert cap is not None, f"{tool}: no cap reaches 0.95 retention"
        assert profiles[tool].retained_at(cap) >= 0.95
        lower = [c for c in sorted(profiles[tool].retention) if c < cap]
        # The advisor takes the *cheapest* clearing cap: one step down
        # must fall below the floor (or there is no step down).
        assert not lower or profiles[tool].retained_at(lower[-1]) < 0.95


def test_optimal_cap_is_144_on_this_dataset():
    # All six mocked tools share the same fact sentences (2-4 facts of
    # ~35 tokens), so every tool's curve crosses 0.95 at the same cap.
    # The advisor is per-tool by construction; on this dataset the
    # answers coincide, and the test pins that honest fact.
    tasks = generate_tasks()
    profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
    caps = optimal_caps(profiles)
    assert set(caps.values()) == {144}


def test_optimal_cap_router_uses_only_advised_caps():
    tasks = generate_tasks()
    profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
    caps = optimal_caps(profiles)
    task = tasks[0]
    ranked = rank_plans_optimal_cap(task, profiles)
    assert ranked  # every (model, tool) pair still offered
    for r in ranked:
        assert r.plan.cap_tokens == caps[r.plan.tool]
    # Cheapest-first ordering is preserved.
    costs = [r.cost_per_resolved for r in ranked]
    assert costs == sorted(costs)
    best = route_optimal_cap(task, profiles)
    assert best.plan == ranked[0].plan


def test_optimal_cap_router_beats_128_on_retention():
    # The unconstrained router may pick cap-128 plans (retention 0.94);
    # the retention-safe router never goes below its advised cap, so its
    # worst plan retains at least 95% of the facts.
    tasks = generate_tasks()
    profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
    task = next(t for t in tasks if t["difficulty"] == 3)
    for r in rank_plans_optimal_cap(task, profiles):
        assert profiles[r.plan.tool].retained_at(r.plan.cap_tokens) >= 0.95


def test_evaluation_has_optimal_cap_arm():
    tasks = generate_tasks()
    profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
    results = run_evaluation(tasks, profiles)
    assert set(results) == {"total_cost", "model_only", "tool_only", "optimal_cap"}
    assert len(results["optimal_cap"]) == 100
    summary = compare(results)
    oc = summary["optimal_cap"]
    assert oc["n_tasks"] == 100
    assert 0.0 < oc["success_rate"] <= 1.0
    assert oc["cost_per_resolved_usd"] is not None
    assert "optimal_cap_saving_pct" in summary
    assert "optimal_cap_success_delta" in summary
    assert "optimal_cap_cost_delta_pct" in summary


def test_write_summary_md_includes_optimal_cap():
    from pathlib import Path

    from tool_total_cost_router.evaluate import write_summary_md

    tasks = generate_tasks()
    profiles = learn_profiles(run_traces(tasks, list(TOOLS_BY_NAME)))
    summary = compare(run_evaluation(tasks, profiles))
    out = Path(__file__).resolve().parent / "_tmp_summary.md"
    try:
        write_summary_md(summary, out)
        text = out.read_text(encoding="utf-8")
        assert "Optimal-cap (retention-safe)" in text
        assert "Head-to-head saving" in text
    finally:
        out.unlink(missing_ok=True)
