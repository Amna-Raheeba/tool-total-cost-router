# Evaluation Summary — 100 scripted tasks (seed 20261117)

| Router | $/resolved-task | Success rate | Mean tokens/task | Mean attempts |
|---|---|---|---|---|
| **Total-cost (joint)** | **$0.000122** | 0.98 (98/100) | 624.5 | 1.22 |
| Model-only baseline | $0.002368 | 1.00 (100/100) | 2461.0 | 1.17 |
| Tool-only ablation | $0.001122 | 1.00 (100/100) | 586.6 | 1.18 |
| Optimal-cap (retention-safe) | $0.000133 | 0.96 (96/100) | 669.3 | 1.28 |

- **Head-to-head saving: 94.8%** ($0.002246 per resolved task).
- **Tool effect alone (model tier held fixed): 52.6%.**
- **Optimal-cap routing: 94.4% cheaper than model-only**, success-rate delta vs the unconstrained router: -0.02, cost delta vs the unconstrained router: +9.0%.
- Success-rate delta: -0.02.

Per-type $/resolved (total-cost vs model-only):

| Type | Total-cost | Model-only |
|---|---|---|
| code | $0.000095 | $0.000689 |
| compute | $0.000124 | $0.000912 |
| lookup | $0.000127 | $0.002188 |
| research | $0.000142 | $0.005683 |

The effect is largest on research tasks, where the baseline's default
tool (web search, ~1,700 tokens, re-read twice) dominates the bill.
Full per-task rows: `results/evaluation.csv`.
Reproduce: `python -m tool_total_cost_router evaluate`.
