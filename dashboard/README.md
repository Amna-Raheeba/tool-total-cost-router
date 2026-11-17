# Dashboard

A Streamlit front end over the real total-cost routing pipeline — not a mock.
Every tab calls the same router, profiles and simulator the library, CLI
and evaluation use.

## Run

```bash
pip install streamlit
streamlit run dashboard/app.py
```

## Tabs

1. **Overview** — the head-to-head numbers from
   `results/evaluation_summary.json`: $/resolved-task for every
   router, the saving, the tool-effect ablation, success rates,
   tokens/task, the per-type breakdown, and the optimal-cap
   router's numbers.
2. **Route a task** — pick any of the 100 scripted tasks and run all
   three routers on it live, with the top 5 ranked plans.
3. **Tool profiles** — the learned per-tool profiles (median/p90 output
   tokens, compressibility, re-reads, retry rate, retention at caps).
4. **Optimal caps** — the per-tool optimal-cap advisor table: each
   tool's cheapest cap preserving ≥ 95% of the facts, its retention
   at that cap, and its retention one cap down (the cliff the
   advisor is standing on).

## Tests

`tests/test_dashboard_helpers.py` covers the helper functions.
The Streamlit app itself is covered by AppTest in
`tests/test_dashboard.py` (skipped in CI, where Streamlit is not
installed; run locally with `pytest tests/test_dashboard.py`).
