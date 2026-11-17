"""Model tiers and their prices.

Prices are labelled estimates for the three tiers of the predecessor
project (llm-cost-optimized-router: flash-lite / flash / pro class),
stated in USD per 1M tokens. They are parameters of the cost model, not
claims about any vendor's live price list — see docs/metrics.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """One model tier."""

    name: str
    tier: str  # "cheap" | "balanced" | "premium"
    capability: int  # 1, 2 or 3 — the hardest task difficulty it handles well
    input_price_per_mtok: float  # USD per 1M input tokens
    output_price_per_mtok: float  # USD per 1M output tokens

    def input_cost(self, tokens: int) -> float:
        return tokens / 1_000_000 * self.input_price_per_mtok

    def output_cost(self, tokens: int) -> float:
        return tokens / 1_000_000 * self.output_price_per_mtok


MODELS: tuple[ModelSpec, ...] = (
    ModelSpec("flash-lite", "cheap", 1, 0.10, 0.40),
    ModelSpec("flash", "balanced", 2, 0.50, 1.50),
    ModelSpec("pro", "premium", 3, 2.50, 10.00),
)

BY_NAME = {m.name: m for m in MODELS}

# Base per-attempt success probability of a model tier on a task of a
# given difficulty, before tool coverage and information retention are
# applied. These are simulation parameters (documented in
# docs/experiment_log.md), chosen so that a cheap model is clearly
# adequate for easy tasks and clearly weak for hard ones.
BASE_SUCCESS = {
    # difficulty: {capability: p}
    1: {1: 0.97, 2: 0.99, 3: 0.995},
    2: {1: 0.82, 2: 0.96, 3: 0.99},
    3: {1: 0.65, 2: 0.87, 3: 0.97},
}


def base_success(model: ModelSpec, difficulty: int) -> float:
    return BASE_SUCCESS[difficulty][model.capability]
