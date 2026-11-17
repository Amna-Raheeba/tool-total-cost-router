# API

## CLI

```bash
python -m tool_total_cost_router learn      # learn profiles -> data/tool_profiles.json
python -m tool_total_cost_router caps       # per-tool optimal caps (default floor: 95% retention)
python -m tool_total_cost_router caps --threshold 0.99
python -m tool_total_cost_router route --task T051
python -m tool_total_cost_router demo       # one research task, all routers
python -m tool_total_cost_router evaluate   # 100-task head-to-head -> results/
python -m tool_total_cost_router models     # list tiers and prices
```

## Python API

```python
from tool_total_cost_router.profiles import learn_profiles, run_traces
from tool_total_cost_router.router import route, model_only_baseline, rank_plans
from tool_total_cost_router.simulator import simulate_task
from tool_total_cost_router.tasks import generate_tasks

tasks = generate_tasks()
profiles = learn_profiles(run_traces(tasks, ["calculator", "api_lookup",
    "database_lookup", "code_executor", "web_search", "document_reader"]))

task = tasks[50]
best = route(task, profiles)              # RankedPlan with .plan and .cost
baseline = model_only_baseline(task, profiles)
result = simulate_task(task, rank_plans(task, profiles), profiles, "total_cost")
result.success, result.total_cost_usd, result.total_tokens
```

### `route(task, profiles) -> RankedPlan`

Best (model, tool, cap) plan by expected $/resolved-task.

### `rank_plans(task, profiles) -> list[RankedPlan]`

Every feasible plan, sorted by $/resolved. Each entry has
`.plan` (`model`, `tool`, `cap_tokens`, `.label()`) and `.cost`
(an `AttemptCost` with `.total_usd`, `.p_attempt`,
`.cost_per_resolved_usd`, `.breakdown()`).

### `model_only_baseline(task, profiles) -> RankedPlan`

Predecessor logic: cheapest model whose capability covers the
difficulty, first-listed tool, no cap.

### `route_optimal_cap(task, profiles, threshold=0.95) -> RankedPlan`

Retention-safe routing: the best (model, tool) plan where each tool
is used only at its advisor-set optimal cap — the cheapest measured
cap preserving at least `threshold` of the facts
(`rank_plans_optimal_cap` enumerates them, ranked by $/resolved).
A tool whose curve never reaches the threshold is used uncapped.

### `optimal_caps(profiles, threshold=0.95) -> dict[str, int | None]`

One optimal cap per tool, each read from that tool's own measured
retention curve (`ToolProfile.optimal_cap`). `None` means uncapped.

### `simulate_task(task, ranked_plans, profiles, router_name, seed=20261117, max_attempts=3) -> TaskResult`

Deterministic execution. Retries walk the ranked list; the baseline
retries the same plan. `.records` holds one `AttemptRecord` per
attempt (plan, tool tokens, re-read tokens, cost, success, reason).

### `learn_profiles(traces) -> dict[str, ToolProfile]`

Aggregate traces into profiles. `ToolProfile.retained_at(cap)` reads
the measured retention curve (`None` → 1.0).

## Dashboard helpers

`dashboard/helpers.py` exposes `load_profiles()`, `load_summary()`,
`profile_table(profiles)`, `optimal_cap_table(profiles)` and
`route_task(task_id)` — pure functions, no Streamlit import, covered
by `tests/test_dashboard_helpers.py`. `route_task` now returns all
three routers (`total_cost`, `model_only`, `optimal_cap`).

The Streamlit app itself is covered by AppTest in
`tests/test_dashboard.py` (skipped in CI, where Streamlit is not
installed).
