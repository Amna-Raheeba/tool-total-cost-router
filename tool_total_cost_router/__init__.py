"""Tool Total-Cost Router — pick the cheapest *completed task*, not the cheapest model.

Model-only routers price the model call. This router prices the whole
agent loop: model tokens + tool-output tokens re-injected into context
(possibly several times) + expected retry cost. A cheap model paired with
a verbose tool can cost more than a premium model paired with a terse one.

No LLM is used at routing time: the router is a deterministic ledger over
per-tool output-cost profiles learned offline from mocked traces.
"""

__version__ = "0.2.0"
