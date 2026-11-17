# Architecture

## The problem

Model-only routers (RouteLLM, xRouter, and Amna's own
`llm-cost-optimized-router`) price the model call. In a tool-using
agent, the model call is not the whole bill: a tool's output re-enters
the context on every following turn — the return journey. A verbose
tool can emit ~100× the user message's tokens, and the agent pays input
price for those tokens again on every re-read, plus retry cost when a
cheap plan fails. Nobody routes on that total.

## The idea

Route **(model, tool, output-cap) jointly** by expected
$/resolved-task, from a deterministic ledger over per-tool profiles
learned offline from mocked traces. No LLM at routing time.

```
task ──► enumerate plans ──► price each plan from profiles ──► cheapest $/resolved
         (model × tool × cap)   attempt_cost / p_attempt
```

## Components

| Module | Role |
|---|---|
| `models.py` | 3 model tiers, prices, base success by difficulty |
| `tools.py` | 6 mocked tools; deterministic text output with fact sentences spread through filler |
| `profiles.py` | Offline learner: median/p90 output tokens, compressibility, re-reads, retry rate, retention-vs-cap curve (fine grid) + per-tool optimal-cap advisor |
| `pricing.py` | The ledger: attempt cost and $/resolved (one formula for every router) |
| `router.py` | Joint router (enumerates all plans) + model-only baseline (predecessor logic) + retention-safe optimal-cap router |
| `tasks.py` | 100 scripted tasks: 4 types × 25, difficulty 40/35/25 |
| `simulator.py` | Deterministic execution: real tool calls, real caps, seeded success draws, retries |
| `evaluate.py` | Head-to-head + tool-only ablation + optimal-cap arm; CSV + JSON + Markdown outputs |
| `cli.py` | `learn`, `caps`, `route`, `demo`, `evaluate`, `models` |

## The ledger

```
attempt_cost = input_price × (prompt_tokens + tool_tokens_after_cap × re_reads)
             + output_price × answer_tokens
$/resolved   = attempt_cost / p_attempt
```

`$/resolved = attempt_cost / p` is exact for a retry-until-resolved
loop (expected attempts = 1/p). A finite retry budget changes the
numerator and denominator by the same factor, so the ratio is
unchanged — see `docs/metrics.md`.

## The retention curve

The router never guesses what a cap costs in information. The profile
learner measures it: for each cap, run the extractive summariser over
real traces and record the mean retained-fact fraction. The grid is
fine (16-token steps, 64–256) because that is where the curve moves.
Measured on this task set: cap 64 → 0.38 retained, cap 96 → 0.76,
cap 128 → 0.94, cap 144 → 1.00. The cap is therefore a real decision,
not a free win.

## The optimal-cap advisor (v0.2.0)

The advisor turns the measured curve into a policy: for each tool,
the cheapest cap preserving at least 95% of the facts
(`ToolProfile.optimal_cap`). The optimal-cap router uses each tool
only at its advised cap — the cap is a policy, not an optimisation
variable — while still choosing model and tool freely by $/resolved.
On this dataset every tool's optimal cap is 144, because all six
mocked tools return the same fact sentences; the advisor is per-tool
by construction and differentiates when tools differ in fact
density. A tool whose curve never reaches the floor is used
uncapped. The guarantee is a floor (no cap-caused fact loss), not a
mean improvement: on the canonical seed the retention-safe router
costs $0.000133/resolved (94.4% cheaper than model-only) at 0.96
success, and the delta vs the unconstrained router is within RNG
noise — see `docs/metrics.md` for the seed sensitivity.

## Why stdlib-only

The core has no dependencies: the cost model, the simulator and the
router must run identically on any machine, including bare CI. The
only optional dependency is Streamlit, for the dashboard.
