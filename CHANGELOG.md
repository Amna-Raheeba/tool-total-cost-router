# Changelog

## 0.2.0 — 2026-11-17

- **New: per-tool optimal-cap advisor.** Each tool's cheapest
  measured cap preserving ≥ 95% of facts (`ToolProfile.optimal_cap`,
  `optimal_caps`); a retention-safe router (`route_optimal_cap`) that
  uses each tool only at its advised cap. Measured on 100 scripted
  tasks: $0.000133/resolved, 94.4% cheaper than model-only, success
  0.96 — the delta vs the unconstrained router (+9.0% cost, −0.02
  success on the canonical seed) is within RNG noise across seeds
  and is reported as such; the guarantee is the retention floor.
- Retention curve now measured on a fine grid (16-token steps,
  64–256): the threshold is 144 tokens for every tool, because all
  six mocked tools share the same fact sentences.
- New CLI: `caps` (advisor table, `--threshold`); `demo` now shows
  all three routers; `evaluate` also writes
  `results/evaluation_summary.md` (generated, no longer hand-written).
- Dashboard: new "Optimal caps" tab; Overview and Route-a-task tabs
  show the optimal-cap router; AppTest coverage in
  `tests/test_dashboard.py` (the v0.1.0 README claimed AppTest
  verification that did not exist in the suite).
- Fixed the deprecated `use_container_width` (Streamlit requirement
  raised to >= 1.44).
- 57 tests (was 40), all passing; CI unchanged (plain pytest).

## 0.1.0 — 2026-11-17

- Joint (model, tool, output-cap) router by expected $/resolved-task.
- Per-tool output-cost profiles learned offline from 600 mocked traces
  (median/p90 tokens, compressibility, re-reads, retry rate,
  retention-vs-cap curve).
- 100 scripted tasks (4 types × 25); deterministic simulator with
  retries; head-to-head evaluation vs the model-only baseline plus a
  tool-only ablation arm.
- Measured: 94.8% cheaper per resolved task head-to-head; 52.6% from
  tool-output routing alone; success 0.98 vs 1.00.
- Streamlit dashboard over the real pipeline; 40 tests, all passing;
  CI on Python 3.10/3.11/3.12.
