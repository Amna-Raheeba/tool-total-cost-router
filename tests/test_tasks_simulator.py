"""Tests for the task set and the deterministic simulator."""
import random

from tool_total_cost_router.evaluate import compare, run_evaluation, summarise
from tool_total_cost_router.profiles import learn_profiles, run_traces
from tool_total_cost_router.router import model_only_baseline, rank_plans
from tool_total_cost_router.simulator import simulate_task
from tool_total_cost_router.tasks import generate_tasks


def _profiles():
    tasks = generate_tasks()
    tools = ["calculator", "api_lookup", "database_lookup", "code_executor", "web_search", "document_reader"]
    return learn_profiles(run_traces(tasks, tools))


def test_task_set_shape():
    tasks = generate_tasks()
    assert len(tasks) == 100
    types = [t["type"] for t in tasks]
    for task_type in ("lookup", "compute", "research", "code"):
        assert types.count(task_type) == 25
    difficulties = [t["difficulty"] for t in tasks]
    assert difficulties.count(1) == 40
    assert difficulties.count(2) == 35
    assert difficulties.count(3) == 25
    assert len({t["id"] for t in tasks}) == 100
    for t in tasks:
        assert 2 <= len(t["facts"]) <= 4
        assert t["tools"]  # every task has at least one candidate tool


def test_task_generation_deterministic():
    assert generate_tasks() == generate_tasks()


def test_simulation_deterministic():
    profiles = _profiles()
    task = generate_tasks()[50]
    ranked = rank_plans(task, profiles)
    a = simulate_task(task, ranked, profiles, "total_cost")
    b = simulate_task(task, ranked, profiles, "total_cost")
    assert a == b


def test_simulation_retry_uses_next_plan():
    profiles = _profiles()
    task = generate_tasks()[50]
    ranked = rank_plans(task, profiles)
    result = simulate_task(task, ranked, profiles, "total_cost", max_attempts=3)
    assert result.attempts <= 3
    assert result.total_cost_usd > 0
    assert result.total_tokens > 0
    assert len(result.records) == result.attempts


def test_baseline_simulation_runs():
    profiles = _profiles()
    task = generate_tasks()[0]
    baseline = model_only_baseline(task, profiles)
    result = simulate_task(task, [baseline], profiles, "model_only")
    assert result.attempts >= 1


def test_evaluation_beats_baseline_and_is_deterministic():
    profiles = _profiles()
    tasks = generate_tasks()
    first = compare(run_evaluation(tasks, profiles))
    second = compare(run_evaluation(tasks, profiles))
    assert first == second
    assert first["saving_pct"] > 0  # total-cost router is cheaper per resolved task
    assert first["tool_effect_saving_pct"] > 0  # tool routing alone saves money
    assert first["total_cost"]["success_rate"] >= 0.95
    assert first["model_only"]["success_rate"] >= 0.95


def test_summarise_maths():
    profiles = _profiles()
    tasks = generate_tasks()
    results = run_evaluation(tasks, profiles)
    summary = summarise(results["total_cost"])
    assert summary["n_tasks"] == 100
    assert summary["resolved"] <= 100
    assert summary["cost_per_resolved_usd"] == round(
        summary["total_cost_usd"] / summary["resolved"], 6
    )
