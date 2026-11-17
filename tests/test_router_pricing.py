"""Tests for the ledger and both routers."""
from tool_total_cost_router.models import BY_NAME
from tool_total_cost_router.pricing import Plan, price_attempt
from tool_total_cost_router.profiles import ToolProfile, learn_profiles, run_traces
from tool_total_cost_router.router import model_only_baseline, rank_plans, route
from tool_total_cost_router.tasks import generate_tasks


def _profiles():
    tasks = generate_tasks()
    tools = ["calculator", "api_lookup", "database_lookup", "code_executor", "web_search", "document_reader"]
    return learn_profiles(run_traces(tasks, tools))


def _task(task_type="research", difficulty=2):
    tasks = generate_tasks()
    return next(t for t in tasks if t["type"] == task_type and t["difficulty"] == difficulty)


def test_price_attempt_maths():
    model = BY_NAME["flash"]
    profile = ToolProfile("web_search", 1800, 2400, 0.2, 2, 0.02, 100, {64: 0.4, 128: 0.9, 256: 1.0, 512: 1.0, 1024: 1.0, 2048: 1.0})
    plan = Plan("flash", "web_search", None)
    cost = price_attempt(plan, model, profile, prompt_tokens=20, answer_tokens=200, p_attempt=0.9)
    # Input = 20 prompt + 1800*2 re-read = 3620 tokens at $0.50/M.
    assert cost.re_read_tokens == 3600
    assert abs(cost.input_cost_usd - 3620 / 1e6 * 0.50) < 1e-9
    assert abs(cost.output_cost_usd - 200 / 1e6 * 1.50) < 1e-9
    assert abs(cost.cost_per_resolved_usd - cost.total_usd / 0.9) < 1e-9


def test_price_attempt_cap_reduces_re_reads():
    model = BY_NAME["flash"]
    profile = ToolProfile("document_reader", 5500, 7500, 0.24, 3, 0.02, 100, {64: 0.4, 128: 0.9, 256: 1.0, 512: 1.0, 1024: 1.0, 2048: 1.0})
    uncapped = price_attempt(Plan("flash", "document_reader", None), model, profile, 20, 200, 0.9)
    capped = price_attempt(Plan("flash", "document_reader", 256), model, profile, 20, 200, 0.9)
    assert capped.tool_tokens_after_cap == 256
    assert capped.re_read_tokens == 768
    assert capped.total_usd < uncapped.total_usd


def test_rank_plans_sorted_by_cost_per_resolved():
    profiles = _profiles()
    ranked = rank_plans(_task(), profiles)
    costs = [r.cost_per_resolved for r in ranked]
    assert costs == sorted(costs)
    assert len(ranked) == 3 * 4 * 7  # models x tools x caps


def test_route_beats_baseline_on_research_task():
    profiles = _profiles()
    task = _task("research", 2)
    best = route(task, profiles)
    baseline = model_only_baseline(task, profiles)
    assert best.cost_per_resolved < baseline.cost_per_resolved


def test_baseline_is_model_only():
    profiles = _profiles()
    task = _task("research", 3)
    baseline = model_only_baseline(task, profiles)
    assert baseline.plan.model == "pro"  # cheapest adequate tier for difficulty 3
    assert baseline.plan.tool == "web_search"  # first-listed default tool
    assert baseline.plan.cap_tokens is None  # never capped


def test_baseline_uses_cheapest_adequate_model():
    profiles = _profiles()
    assert model_only_baseline(_task("lookup", 1), profiles).plan.model == "flash-lite"
    assert model_only_baseline(_task("lookup", 2), profiles).plan.model == "flash"


def test_router_prefers_terse_tool_for_research():
    profiles = _profiles()
    best = route(_task("research", 1), profiles)
    # A terse tool (or a hard cap on a verbose one) must win: the verbose
    # uncapped plan is never the cheapest way to finish a research task.
    assert not (best.plan.tool == "web_search" and best.plan.cap_tokens is None)
