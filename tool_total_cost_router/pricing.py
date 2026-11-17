"""The deterministic cost ledger.

One formula prices every plan, router or baseline, so the comparison is
fair: the routers differ only in the plan they choose, never in how the
plan is priced.

    attempt_cost = model_input(prompt + tool_output_after_cap * re_reads)
                 + model_output(answer_tokens)
    $/resolved   = attempt_cost / p_attempt

The second line is exact for a retry-until-resolved loop: with success
probability p per attempt, the expected number of attempts is 1/p, so the
expected spend per resolved task is attempt_cost / p. (A finite retry
budget changes both the numerator and the denominator by the same
factor — see docs/metrics.md — so the ratio is unchanged.)
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import ModelSpec
from .profiles import ToolProfile


@dataclass(frozen=True)
class Plan:
    """One routing decision: which model, which tool, which output cap."""

    model: str
    tool: str
    cap_tokens: int | None  # None = no cap

    def label(self) -> str:
        cap = "uncapped" if self.cap_tokens is None else f"cap-{self.cap_tokens}"
        return f"{self.model} + {self.tool} [{cap}]"


@dataclass
class AttemptCost:
    plan: Plan
    prompt_tokens: int
    tool_tokens_after_cap: int
    re_read_tokens: int
    answer_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    p_attempt: float

    @property
    def total_usd(self) -> float:
        return self.input_cost_usd + self.output_cost_usd

    @property
    def cost_per_resolved_usd(self) -> float:
        return self.total_usd / max(self.p_attempt, 0.05)

    def breakdown(self) -> dict:
        return {
            "plan": self.plan.label(),
            "prompt_tokens": self.prompt_tokens,
            "tool_tokens_after_cap": self.tool_tokens_after_cap,
            "re_read_tokens": self.re_read_tokens,
            "answer_tokens": self.answer_tokens,
            "input_cost_usd": round(self.input_cost_usd, 6),
            "output_cost_usd": round(self.output_cost_usd, 6),
            "attempt_cost_usd": round(self.total_usd, 6),
            "p_attempt": round(self.p_attempt, 4),
            "cost_per_resolved_usd": round(self.cost_per_resolved_usd, 6),
        }


def price_attempt(
    plan: Plan,
    model: ModelSpec,
    profile: ToolProfile,
    prompt_tokens: int,
    answer_tokens: int,
    p_attempt: float,
) -> AttemptCost:
    """Price one attempt of a plan from the learned tool profile."""
    tool_tokens = profile.median_tokens
    if plan.cap_tokens is not None:
        tool_tokens = min(tool_tokens, float(plan.cap_tokens))
    tool_tokens_int = int(tool_tokens)
    re_read_tokens = tool_tokens_int * profile.re_reads
    input_tokens = prompt_tokens + re_read_tokens
    return AttemptCost(
        plan=plan,
        prompt_tokens=prompt_tokens,
        tool_tokens_after_cap=tool_tokens_int,
        re_read_tokens=re_read_tokens,
        answer_tokens=answer_tokens,
        input_cost_usd=model.input_cost(input_tokens),
        output_cost_usd=model.output_cost(answer_tokens),
        p_attempt=p_attempt,
    )
