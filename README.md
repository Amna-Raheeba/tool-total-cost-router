# Tool Total-Cost Router

**Routers pick the cheapest model. This one picks the cheapest
completed task.**

Model-only routers (RouteLLM, xRouter, and my own
[llm-cost-optimized-router](https://github.com/Amna-Raheeba/llm-cost-optimized-router))
price the model call. In a tool-using agent, the model call is not the
whole bill: a tool's output re-enters the context on every following
turn — the return journey. A verbose tool can emit ~100× the user
message's tokens, and the agent pays input price for those tokens again
on every re-read, plus retry cost when a cheap plan fails. Nobody
routes on that total. This router does.

**Measured result (100 scripted tasks, seed 20261117): 94.8% cheaper
per resolved task than model-only routing — $0.000122 vs $0.002368 —
and 52.6% cheaper from tool-output routing alone, with the model tier
held fixed.** Success rate 0.98 vs 1.00 (see §6 for the honest caveats).

**New in v0.2.0 — the per-tool optimal-cap advisor.** No router
ships this: from each tool's measured retention-vs-cap curve, the
advisor computes the cheapest output cap that preserves at least 95%
of the facts, and the optimal-cap router uses each tool only at its
advised cap — so it never trades facts for dollars. On this dataset
every tool's optimal cap is 144 tokens (see §4 for why, honestly
stated). The retention-safe router costs $0.000133/resolved — 94.4%
cheaper than model-only — with success 0.96 vs 0.98 for the
unconstrained router, a difference within RNG noise (see §6).

## 1. The idea in 30 seconds

```text
model-only router:  cheapest model that can do the job  →  ignores the tool bill
total-cost router:  cheapest (model, tool, output-cap) jointly
                    by expected $/resolved-task
```

Total cost of one attempt:

```text
attempt_cost = input_price  × (prompt_tokens + tool_tokens_after_cap × re_reads)
             + output_price × answer_tokens
$/resolved   = attempt_cost / p_attempt
```

A cheap model + verbose tool can cost **more** than a premium model +
terse tool. Example from the demo (`python -m tool_total_cost_router demo`):

| Router | Plan | Cost | Tokens |
|---|---|---|---|
| Model-only | flash-lite + web_search, uncapped | $0.000501 | 6,747 |
| Total-cost | flash-lite + web_search, cap-128 | $0.000086 | 537 |

Same model, same tool — the cap alone makes it 5.8× cheaper, because
the facts survive (retention 0.94) while the re-read bill collapses.

## 2. How it works

1. **Profiles, learned offline.** Each mocked tool is run over the
   task set (600 traces) and measured: median/p90 output tokens,
   compressibility, re-reads, retry rate — and a **retention-vs-cap
   curve**: for each cap, what fraction of the facts survives
   extractive summarisation. The router reads this curve; it never
   guesses what a cap costs.
2. **Joint routing.** Every (model, tool, cap) plan the task allows is
   priced from the ledger and ranked by expected $/resolved-task. No
   LLM at routing time — the router is a deterministic ledger.
3. **Deterministic simulation.** Plans are executed against mocked
   tools that generate real text, with seeded success draws and
   retries (up to 3 attempts; a retry tries the next-ranked plan).

## 3. Quick start

```bash
pip install -e .            # core is stdlib-only; no dependencies
python -m tool_total_cost_router learn       # learn tool profiles
python -m tool_total_cost_router caps        # per-tool optimal caps
python -m tool_total_cost_router demo        # one task, all routers
python -m tool_total_cost_router evaluate    # 100-task head-to-head
python -m tool_total_cost_router route --task T051
streamlit run dashboard/app.py               # pip install streamlit first
```

## 4. Measured results

100 scripted tasks (4 types × 25; difficulty 40/35/25), seed 20261117.
Full rows in `results/evaluation.csv`.

| Router | $/resolved | Success | Tokens/task |
|---|---|---|---|
| **Total-cost (joint)** | **$0.000122** | 0.98 | 624.5 |
| Model-only baseline | $0.002368 | 1.00 | 2461.0 |
| Tool-only ablation | $0.001122 | 1.00 | 586.6 |
| Optimal-cap (retention-safe) | $0.000133 | 0.96 | 669.3 |

- **Head-to-head saving: 94.8%.**
- **Tool effect alone: 52.6%** — same model tier as the baseline,
  optimising only tool + cap. This is the novel contribution,
  isolated from model-tier arbitrage.
- **Optimal-cap saving: 94.4% vs model-only.** The retention
  guarantee costs +9.0% per resolved task vs the unconstrained
  router on the canonical seed — but the delta is not stable across
  seeds (−7.0% to +33.6% over four seeds), so the two routers are
  within noise of each other on cost and success; what the
  optimal-cap router guarantees is the floor (no cap-caused fact
  loss), not a mean improvement. See §6.
- Largest effect on research tasks: $0.000142 vs $0.005683 per
  resolved task, where the baseline's default tool (web search,
  ~1,700 tokens, re-read twice) dominates the bill.

Learned tool profiles (600 traces):

| Tool | Median tok | p90 tok | Re-reads | Retry |
|---|---|---|---|---|
| calculator | 104 | 140 | 1 | 0.00 |
| api_lookup | 152 | 212 | 1 | 0.01 |
| code_executor | 310 | 455 | 1 | 0.02 |
| database_lookup | 462 | 572 | 2 | 0.03 |
| web_search | 1,736 | 2,394 | 2 | 0.03 |
| document_reader | 5,568 | 7,396 | 3 | 0.00 |

Retention curve (all tools, fine grid): cap 64 → 0.38, cap 96 →
0.76, cap 128 → 0.94, cap 144 → 1.00 — the cap is a real decision,
not a free win. The curve is measured on a fine grid (16-token
steps, 64–256) because that is where it moves: fact sentences are
~35 tokens each, so a task's facts need 68–144 tokens in total.

### The optimal-cap advisor

For each tool, the advisor reads its own measured retention curve
and takes the cheapest cap clearing a 95% retention floor
(`ToolProfile.optimal_cap`, default threshold 0.95). A tool whose
curve never reaches the floor is used uncapped — the advisor never
recommends a cap it has not measured as safe.

| Tool | Optimal cap | Retention at cap | Retention one cap down |
|---|---|---|---|
| calculator | 144 | 1.000 | 0.938 |
| api_lookup | 144 | 1.000 | 0.937 |
| code_executor | 144 | 1.000 | 0.939 |
| database_lookup | 144 | 1.000 | 0.938 |
| web_search | 144 | 1.000 | 0.936 |
| document_reader | 144 | 1.000 | 0.938 |

Honest note: all six tools land on the same cap, 144. That is not a
bug in the advisor — it is a property of these mocked traces: every
tool returns the same fact sentences (2–4 per task, ~35 tokens
each), so every tool's curve crosses 0.95 at the same point (the
four-fact tasks need 144 tokens). The advisor is per-tool by
construction — each cap is computed from that tool's own curve —
and it will differentiate on real tools whose fact density differs.
The fine grid is what makes 144 visible at all: on the old coarse
grid (64/128/256) the answer would have been 256, wasting 112
tokens of headroom on every re-read.

## 5. Project layout

```text
tool_total_cost_router/   core package (models, tools, profiles, pricing,
                          router, tasks, simulator, evaluate, cli)
data/                     tasks.jsonl (100 tasks), tool_profiles.json
notebooks/                01_cost_model_demo.py, 02_evaluation.py
dashboard/                Streamlit app over the real pipeline
results/                  evaluation.csv, evaluation_summary.json/.md
docs/                     architecture.md, api.md, metrics.md, experiment_log.md
tests/                    57 tests, plain pytest (incl. AppTest for the dashboard)
```

## 6. Honest limitations

- The 94.8% headline mixes model-tier arbitrage with tool routing;
  the 52.6% tool-only ablation is the novel contribution and is
  reported alongside it, not hidden.
- Success rate is 0.98 vs the baseline's 1.00 (one task failed all
  three attempts). The saving is reported with that delta.
- Mocked tools are free; their cost is context tokens only. Model
  prices are labelled estimates, not live vendor prices.
- This is a model of an agent loop on scripted tasks, not a live
  agent: the numbers prove the routing idea, not production traffic.
- **Optimal-cap limits.** Caps are tuned on mocked traces, and
  retention is measured on fact sentences, not real tool outputs.
  All six tools share the same optimal cap (144) because they share
  the same fact sentences — the advisor differentiates only when
  tools differ in fact density. The optimal-cap vs total-cost delta
  (+9.0% cost, −0.02 success on the canonical seed) is not stable
  across seeds, so it is reported as noise, not as an effect: the
  guarantee is the retention floor, not a mean saving.
- **Unpaired RNG streams.** Each router's simulation draws from its
  own seeded stream, so a 96-vs-98 success difference on 100 tasks
  is within draw noise; the evaluation does not claim a paired
  comparison.

## 7. Relation to llm-cost-optimized-router

That project routes **models** (complexity → cheapest adequate tier,
with a budget gate, retries, and a semantic cache). This is its
sequel: it keeps the same cost-ledger idea and extends routing to the
**tool and its output**, which the first router never priced. The
model-only baseline in the evaluation is the first router's logic,
reimplemented so the comparison is apples-to-apples.

## 8. Tests

```bash
pytest -q        # 57 tests, stdlib-only, no network
```

CI runs plain `pytest` on Python 3.10/3.11/3.12 plus the demo and the
full evaluation (see `.github/workflows/ci.yml`). The dashboard
AppTest (`tests/test_dashboard.py`) is skipped in CI, where Streamlit
is not installed; it runs locally where Streamlit is present.

## 9. License

MIT — see `LICENSE`.
