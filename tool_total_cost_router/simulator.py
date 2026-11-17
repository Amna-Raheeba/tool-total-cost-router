"""Deterministic execution of a routing plan on a task.

The simulator is the ground truth the evaluation measures. It runs the
mocked tool for real (generating real text), applies the plan's output
cap with the extractive summariser, measures the retained-fact fraction
from the actual text, and draws success from the resulting probability
with a seeded RNG — so every run is reproducible from its seed.

Retries: on failure the router tries its next-ranked plan; the baseline
retries the same plan. At most ``max_attempts`` attempts per task.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .models import BY_NAME as MODELS_BY_NAME, base_success
from .profiles import ToolProfile, extractive_keep, keywords, retained_facts
from .router import RankedPlan
from .tasks import answer_tokens_for
from .tools import ToolOutput, call_tool, count_tokens


@dataclass
class AttemptRecord:
    plan_label: str
    tool_tokens: int
    re_read_tokens: int
    cost_usd: float
    success: bool
    reason: str


@dataclass
class TaskResult:
    task_id: str
    task_type: str
    difficulty: int
    router: str
    success: bool
    attempts: int
    total_cost_usd: float
    total_tokens: int
    final_plan: str
    records: list[AttemptRecord] = field(default_factory=list)


def _run_attempt(
    task: dict,
    ranked: RankedPlan,
    profiles: dict[str, ToolProfile],
    rng: random.Random,
) -> AttemptRecord:
    plan = ranked.plan
    model = MODELS_BY_NAME[plan.model]
    profile = profiles[plan.tool]
    prompt_tokens = count_tokens(task["prompt"])
    answer_tokens = answer_tokens_for(task["difficulty"])
    keys = keywords(task["prompt"])

    out: ToolOutput = call_tool(plan.tool, task["facts"], rng)
    if out.error:
        # The tool errored: the model still spent prompt + answer tokens.
        cost = model.input_cost(prompt_tokens) + model.output_cost(answer_tokens)
        return AttemptRecord(
            plan_label=plan.label(),
            tool_tokens=0,
            re_read_tokens=0,
            cost_usd=cost,
            success=False,
            reason="tool_error",
        )

    # Coverage draw: does this tool actually return the needed facts?
    if rng.random() >= task["tools"][plan.tool]:
        out = ToolOutput(
            tool=out.tool,
            sentences=[s for s in out.sentences if not s.startswith("FACT:")],
            facts_present=0,
            facts_total=out.facts_total,
        )

    kept = extractive_keep(out.sentences, keys, plan.cap_tokens)
    kept_text = " ".join(kept)
    tool_tokens = count_tokens(kept_text)
    retained = retained_facts(
        ToolOutput(tool=out.tool, sentences=kept, facts_total=out.facts_total), keys, None
    )
    re_read_tokens = tool_tokens * profile.re_reads
    input_tokens = prompt_tokens + re_read_tokens
    cost = model.input_cost(input_tokens) + model.output_cost(answer_tokens)
    p = base_success(model, task["difficulty"]) * retained
    success = rng.random() < p
    reason = "ok" if success else ("missing_facts" if retained < 1.0 else "model_error")
    return AttemptRecord(
        plan_label=plan.label(),
        tool_tokens=tool_tokens,
        re_read_tokens=re_read_tokens,
        cost_usd=cost,
        success=success,
        reason=reason,
    )


def simulate_task(
    task: dict,
    ranked_plans: list[RankedPlan],
    profiles: dict[str, ToolProfile],
    router_name: str,
    seed: int = 20261117,
    max_attempts: int = 3,
) -> TaskResult:
    """Execute a task under a ranked plan list (retries walk the list)."""
    rng = random.Random(f"{seed}:{router_name}:{task['id']}")
    records: list[AttemptRecord] = []
    success = False
    attempts = 0
    for i in range(max_attempts):
        ranked = ranked_plans[min(i, len(ranked_plans) - 1)]
        record = _run_attempt(task, ranked, profiles, rng)
        records.append(record)
        attempts += 1
        if record.success:
            success = True
            break
    total_cost = sum(r.cost_usd for r in records)
    total_tokens = sum(
        r.tool_tokens + r.re_read_tokens for r in records
    ) + attempts * (
        count_tokens(task["prompt"]) + answer_tokens_for(task["difficulty"])
    )
    return TaskResult(
        task_id=task["id"],
        task_type=task["type"],
        difficulty=task["difficulty"],
        router=router_name,
        success=success,
        attempts=attempts,
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        final_plan=records[-1].plan_label if records else "none",
        records=records,
    )
