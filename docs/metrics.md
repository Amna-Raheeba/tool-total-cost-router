# Metrics

All metrics are computed from the 100-task simulation runs in
`results/evaluation.csv`. Nothing is estimated after the fact.

## Primary metrics

| Metric | Definition |
|---|---|
| `$/resolved-task` | Total spend ÷ tasks resolved. The headline number. |
| `success_rate` | Resolved ÷ attempted (100 tasks). |
| `tokens/task` | Mean total tokens (prompt + tool output + re-reads + answers) per task. |
| `mean_attempts` | Mean attempts per task (max 3). |

## The $/resolved formula

With per-attempt success probability `p`, a retry-until-resolved loop
needs `1/p` attempts on average, so expected spend per resolved task
is `attempt_cost / p`. With a finite retry budget of `n` attempts the
expected spend is `attempt_cost × (1 − (1−p)ⁿ) / p` and the resolution
probability is `1 − (1−p)ⁿ`; their ratio is again `attempt_cost / p`.
The budget therefore does not bias the comparison — it only caps the
worst case. The simulator enforces `max_attempts = 3`.

## Prices

Model prices are labelled estimates for the three tiers of the
predecessor project (flash-lite / flash / pro class), in USD per 1M
tokens: cheap $0.10 in / $0.40 out; balanced $0.50 / $1.50; premium
$2.50 / $10.00. They are parameters of the cost model, not claims
about any vendor's live price list. Mocked tools are free — their cost
is context tokens, not API fees.

## The ablation arm

The head-to-head saving mixes two effects: model-tier arbitrage (the
predecessor's own finding) and tool-output routing (this project's
novel contribution). The `tool_only` arm isolates the second: same
model tier as the baseline, optimise only tool + cap. Its saving
(52.6%) is the tool effect alone.

## Measured results (seed 20261117, 100 tasks)

| Router | $/resolved | Success | Tokens/task |
|---|---|---|---|
| Total-cost (joint) | $0.000122 | 0.98 | 624.5 |
| Model-only baseline | $0.002368 | 1.00 | 2461.0 |
| Tool-only ablation | $0.001122 | 1.00 | 586.6 |
| Optimal-cap (retention-safe) | $0.000133 | 0.96 | 669.3 |

Head-to-head saving: **94.8%**. Tool effect alone: **52.6%**.
Success-rate delta: −0.02 (98 vs 100 resolved).
Optimal-cap saving vs model-only: **94.4%**; cost delta vs the
unconstrained router: **+9.0%**; success delta vs the unconstrained
router: **−0.02** (96 vs 98 resolved).

## The optimal-cap advisor

For each tool, the advisor takes the cheapest measured cap whose mean
retained-fact fraction is at least 0.95 (`ToolProfile.optimal_cap`,
default threshold 0.95). The retention curve is measured on a fine
grid (16-token steps, 64–256, then 320/384/512/1024/2048) because
that is where the curve moves: cap 64 → 0.38, 96 → 0.76,
128 → 0.94, 144 → 1.00. On this dataset every tool's optimal cap is
144: all six mocked tools return the same fact sentences (2–4 per
task, ~35 tokens each), so every curve crosses 0.95 at the same
point. The advisor is per-tool by construction and differentiates
when tools differ in fact density; on these traces the honest
answer is that they coincide. A tool whose curve never reaches the
floor is used uncapped.

The optimal-cap router (`rank_plans_optimal_cap`) uses each tool
only at its advised cap and still chooses model and tool freely by
$/resolved. Its guarantee is a floor, not a mean: no plan it can
pick loses facts to its cap, while the unconstrained router's
web_search/code_executor plans run at cap-128 with 0.94 retention.

## Seed sensitivity of the optimal-cap delta

The optimal-cap vs total-cost delta is **not stable across seeds**
— it is noise, and is reported as such:

| Seed | Total-cost $/resolved | Optimal-cap $/resolved | Cost delta | Success delta |
|---|---|---|---|---|
| 20261117 (canonical) | $0.000122 (98/100) | $0.000133 (96/100) | +9.0% | −0.02 |
| 20261118 | $0.000134 (98/100) | $0.000145 (93/100) | +8.2% | −0.05 |
| 20261119 | $0.000142 (97/100) | $0.000132 (97/100) | −7.0% | +0.00 |
| 20261120 | $0.000116 (99/100) | $0.000155 (90/100) | +33.6% | −0.09 |

Each router's simulation draws from its own seeded stream (the seed
includes the router name), so success draws are unpaired: the
optimal-cap router wins 2 tasks the unconstrained router loses on
the canonical seed (T009, T037) and loses 4 the other way (T011,
T035, T058, T078), all on model_error/coverage draws — none on
cap-caused fact loss. The optimal-cap saving vs model-only is
stable (92.0–94.4% across the four seeds); the delta vs the
unconstrained router is not an effect and is not claimed as one.
