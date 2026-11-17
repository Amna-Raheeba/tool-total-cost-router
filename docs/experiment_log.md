# Experiment Log

## 2026-11-17 — Audit + v0.2.0: per-tool optimal-cap advisor (seed 20261117)

### Audit findings (completeness check)

The v0.1.0 repo was complete and honest: 40 tests green, dashboard
AppTest 0 exceptions, hierarchical README, CHANGELOG/LICENSE/
.gitignore/CI workflow all present, no TODOs or placeholders, no
`.env`, privacy scan clean. Four gaps were found and fixed:

1. **No AppTest in the test suite.** `dashboard/README.md` claimed
   the app "is verified with AppTest — see docs/experiment_log.md",
   but the log never mentioned AppTest and no test file ran it.
   Fixed: `tests/test_dashboard.py` (AppTest, skipped in CI where
   Streamlit is absent) — 4 tabs, headline metrics, optimal-cap
   table, route button all covered, 0 exceptions.
2. **Deprecated `use_container_width`.** Streamlit warns it will be
   removed after 2025-12-31. Fixed: `width="stretch"` in
   `dashboard/app.py`; Streamlit requirement raised to >= 1.44.
3. **Hand-written `results/evaluation_summary.md`.** `evaluate`
   regenerated the CSV and JSON but not the .md, so it could drift.
   Fixed: `evaluate.write_summary_md` generates it from the same
   summary dict; `cmd_evaluate` writes all three files.
4. **Coarse retention grid.** The curve was measured at 64/128/256…
   and jumped from 0.94 straight to 1.00, hiding the true
   threshold. Fixed: 16-token steps, 64–256 (see below).

### What was added

Per-tool optimal-cap advisor — the feature no other router ships:
each tool's cheapest measured cap preserving ≥ 95% of facts, and a
retention-safe router that uses each tool only at its advised cap.
Fine grid resolves the threshold at 144 tokens for every tool.

### Measured results (canonical seed 20261117)

| Router | $/resolved | Success | Tokens/task | Attempts |
|---|---|---|---|---|
| Total-cost (joint) | $0.000122 | 0.98 (98/100) | 624.5 | 1.22 |
| Model-only baseline | $0.002368 | 1.00 (100/100) | 2461.0 | 1.17 |
| Tool-only ablation | $0.001122 | 1.00 (100/100) | 586.6 | 1.18 |
| Optimal-cap (retention-safe) | $0.000133 | 0.96 (96/100) | 669.3 | 1.28 |

Optimal-cap saving vs model-only **94.4%**; cost delta vs the
unconstrained router **+9.0%**; success delta **−0.02**.

### Seed sensitivity — the delta is noise, not an effect

| Seed | Total-cost | Optimal-cap | Cost delta | Success delta |
|---|---|---|---|---|
| 20261117 | $0.000122, 98/100 | $0.000133, 96/100 | +9.0% | −0.02 |
| 20261118 | $0.000134, 98/100 | $0.000145, 93/100 | +8.2% | −0.05 |
| 20261119 | $0.000142, 97/100 | $0.000132, 97/100 | −7.0% | +0.00 |
| 20261120 | $0.000116, 99/100 | $0.000155, 90/100 | +33.6% | −0.09 |

Each router draws from its own seeded stream, so the draws are
unpaired: on the canonical seed the optimal-cap router wins 2 tasks
the unconstrained router loses (T009, T037) and loses 4 the other
way (T011, T035, T058, T078) — all on model_error/coverage draws,
none on cap-caused fact loss. The optimal-cap saving vs model-only
is stable (92.0–94.4%); the delta vs the unconstrained router is
reported as noise. The guarantee is the floor: every plan the
retention-safe router can pick retains ≥ 95% of the facts by
construction, while the unconstrained router's web_search and
code_executor plans run at cap-128 with 0.94 retention.

### Honest limits (carried into README §6)

- Caps are tuned on mocked traces; retention is measured on fact
  sentences, not real tool outputs.
- All six tools share the optimal cap 144 because they share the
  same fact sentences — the advisor differentiates only when tools
  differ in fact density.
- Success draws are unpaired across routers; a 96-vs-98 difference
  on 100 tasks is within draw noise.

## 2026-11-17 — Build v0.1.0 (seed 20261117)

### What was built

Joint (model, tool, output-cap) router over per-tool profiles learned
offline from 600 mocked traces; 100 scripted tasks; deterministic
simulator; head-to-head evaluation against the predecessor's
model-only router, plus a tool-only ablation arm.

### Measured results

| Router | $/resolved | Success | Tokens/task | Attempts |
|---|---|---|---|---|
| Total-cost (joint) | $0.000122 | 0.98 (98/100) | 624.5 | 1.22 |
| Model-only baseline | $0.002368 | 1.00 (100/100) | 2461.0 | 1.17 |
| Tool-only ablation | $0.001122 | 1.00 (100/100) | 586.6 | 1.18 |

Head-to-head saving **94.8%**; tool effect alone **52.6%**.
Evaluation is byte-identical on re-run (verified: two consecutive
`evaluate` runs diff clean).

### Learned profiles (600 traces)

| Tool | Median tok | p90 tok | Compressibility | Re-reads | Retry |
|---|---|---|---|---|---|
| calculator | 104 | 140 | 0.00 | 1 | 0.00 |
| api_lookup | 152 | 212 | 0.00 | 1 | 0.01 |
| code_executor | 310 | 455 | 0.00 | 1 | 0.02 |
| database_lookup | 462 | 572 | 0.01 | 2 | 0.03 |
| web_search | 1736 | 2394 | 0.22 | 2 | 0.03 |
| document_reader | 5568 | 7396 | 0.24 | 3 | 0.00 |

Retention curve (all tools): cap 64 → 0.38, cap 128 → 0.94,
cap 256+ → 1.00.

### Three bugs found and fixed (each with a regression test)

1. **Extractive summariser dropped the answer first.** Fact sentences
   contain no prompt keywords, so they scored like filler. Fixed with
   a relevance bonus for FACT sentences (the analogue of a retriever
   ranking answer passages highly); `test_extractive_keep_respects_cap`
   covers it.
2. **Compressibility could exceed 1.0.** Per-sentence token counts
   each add a +1 rounding term, so their sum exceeds the whole
   output's count. Fixed by computing the ratio from character
   lengths; `test_compressibility_between_zero_and_one` covers it.
3. **Retention curve was flat at 1.0.** Facts were ~13 tokens each,
   so any cap ≥ 64 held them all and the cap was a free win. Fixed by
   making fact sentences realistic (~35 tokens) and adding a 64-token
   cap; the curve now shows a real trade-off (0.38 at cap 64).

### Honest limitations

- The 94.8% headline mixes model-tier arbitrage with tool routing;
  the 52.6% tool-only ablation is the novel contribution, reported
  alongside it — not hidden.
- Success rate is 0.98 vs the baseline's 1.00 (task T065 failed all
  three attempts). The saving is reported with that delta, not
  without it.
- Mocked tools are free; their cost is context tokens only. Model
  prices are labelled estimates, not live vendor prices.
- The simulator is a model of an agent loop, not a live agent: the
  numbers prove the routing idea on scripted tasks, not on
  production traffic.
