"""The total-cost router and the model-only baseline.

Joint router: enumerates every (model, tool, output-cap) plan the task
allows and ranks by expected $/resolved-task from the ledger, using the
learned per-tool profiles (median output size, re-reads, and the measured
retention curve). No LLM is consulted at routing time.

Model-only baseline: the predecessor's logic (llm-cost-optimized-router)
— cheapest model whose capability covers the difficulty, the task's
default (first-listed) tool, no output cap. It is priced by the *same*
ledger, so the comparison isolates the decision, not the accounting.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import BY_NAME as MODELS_BY_NAME, MODELS, base_success
from .pricing import AttemptCost, Plan, price_attempt
from .profiles import ToolProfile, optimal_caps
from .tasks import answer_tokens_for
from .tools import count_tokens

CAPS: tuple[int | None, ...] = (64, 128, 256, 512, 1024, 2048, None)


@dataclass
class RankedPlan:
    plan: Plan
    cost: AttemptCost

    @property
    def cost_per_resolved(self) -> float:
        return self.cost.cost_per_resolved_usd


def _estimate_p(model_name: str, difficulty: int, coverage: float, retained: float) -> float:
    model = MODELS_BY_NAME[model_name]
    return base_success(model, difficulty) * coverage * retained


def rank_plans(
    task: dict,
    profiles: dict[str, ToolProfile],
) -> list[RankedPlan]:
    """All feasible plans for a task, ranked by expected $/resolved-task."""
    prompt_tokens = count_tokens(task["prompt"])
    answer_tokens = answer_tokens_for(task["difficulty"])
    ranked: list[RankedPlan] = []
    for model in MODELS:
        for tool, coverage in task["tools"].items():
            profile = profiles[tool]
            for cap in CAPS:
                retained = profile.retained_at(cap)
                p = _estimate_p(model.name, task["difficulty"], coverage, retained)
                plan = Plan(model=model.name, tool=tool, cap_tokens=cap)
                cost = price_attempt(plan, model, profile, prompt_tokens, answer_tokens, p)
                ranked.append(RankedPlan(plan=plan, cost=cost))
    ranked.sort(key=lambda r: r.cost_per_resolved)
    return ranked


def route(task: dict, profiles: dict[str, ToolProfile]) -> RankedPlan:
    """The total-cost router's best plan for a task."""
    return rank_plans(task, profiles)[0]


def rank_plans_optimal_cap(
    task: dict,
    profiles: dict[str, ToolProfile],
    threshold: float = 0.95,
) -> list[RankedPlan]:
    """Retention-safe routing: one cap per tool, set by the advisor.

    Instead of enumerating every cap and letting $/resolved pick the
    cheapest — which can pick a cap that drops 6% of the facts because
    the re-read saving outweighs the lost success probability — each
    tool is used only at its optimal cap: the cheapest cap the advisor
    measured as preserving at least ``threshold`` of the facts
    (see ``profiles.ToolProfile.optimal_cap``). The router still
    chooses the model and the tool freely; only the cap is a policy,
    not an optimisation variable. A tool whose curve never reaches the
    threshold is used uncapped.
    """
    caps = optimal_caps(profiles, threshold)
    prompt_tokens = count_tokens(task["prompt"])
    answer_tokens = answer_tokens_for(task["difficulty"])
    ranked: list[RankedPlan] = []
    for model in MODELS:
        for tool, coverage in task["tools"].items():
            profile = profiles[tool]
            cap = caps[tool]
            retained = profile.retained_at(cap)
            p = _estimate_p(model.name, task["difficulty"], coverage, retained)
            plan = Plan(model=model.name, tool=tool, cap_tokens=cap)
            cost = price_attempt(plan, model, profile, prompt_tokens, answer_tokens, p)
            ranked.append(RankedPlan(plan=plan, cost=cost))
    ranked.sort(key=lambda r: r.cost_per_resolved)
    return ranked


def route_optimal_cap(
    task: dict,
    profiles: dict[str, ToolProfile],
    threshold: float = 0.95,
) -> RankedPlan:
    """The retention-safe router's best plan for a task."""
    return rank_plans_optimal_cap(task, profiles, threshold)[0]


def model_only_baseline(task: dict, profiles: dict[str, ToolProfile]) -> RankedPlan:
    """Predecessor-style routing: cheapest adequate model, default tool, no cap.

    This mirrors llm-cost-optimized-router's decide_tier: complexity
    (here: difficulty) picks the cheapest tier that can do the job. The
    tool is the task's first-listed (default) tool and its output is
    never capped — the router never sees the tool-output cost at all.
    """
    difficulty = task["difficulty"]
    adequate = [m for m in MODELS if m.capability >= difficulty]
    model = adequate[0] if adequate else MODELS[-1]
    tool = next(iter(task["tools"]))
    coverage = task["tools"][tool]
    profile = profiles[tool]
    prompt_tokens = count_tokens(task["prompt"])
    answer_tokens = answer_tokens_for(task["difficulty"])
    p = _estimate_p(model.name, difficulty, coverage, 1.0)
    plan = Plan(model=model.name, tool=tool, cap_tokens=None)
    cost = price_attempt(plan, model, profile, prompt_tokens, answer_tokens, p)
    return RankedPlan(plan=plan, cost=cost)
