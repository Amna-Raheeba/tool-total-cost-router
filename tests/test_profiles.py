"""Tests for the profile learner and the extractive summariser."""
import random

from tool_total_cost_router.profiles import (
    compressibility,
    extractive_keep,
    keywords,
    learn_profiles,
    retained_facts,
    run_traces,
)
from tool_total_cost_router.tasks import generate_tasks
from tool_total_cost_router.tools import ToolOutput, call_tool


def _output(tool="web_search", facts=("alpha fact", "beta fact")):
    return call_tool(tool, list(facts), random.Random(11))


def test_keywords_drop_short_words():
    # Words of 2 chars or fewer ("12") are dropped; 3-letter words stay.
    assert keywords("Find the price for record 12") == {
        "find", "the", "price", "for", "record",
    }


def test_extractive_keep_respects_cap():
    out = _output()
    keys = keywords("Find the price for record")
    kept = extractive_keep(out.sentences, keys, 128)
    from tool_total_cost_router.tools import count_tokens

    assert count_tokens(" ".join(kept)) <= 128 + 40  # one sentence may overshoot
    assert any(s.startswith("FACT:") for s in kept)  # facts survive first


def test_extractive_keep_none_keeps_everything():
    out = _output()
    kept = extractive_keep(out.sentences, {"zzz"}, None)
    assert kept == out.sentences


def test_retained_facts_full_without_cap():
    out = _output()
    assert retained_facts(out, keywords("anything"), None) == 1.0


def test_retained_facts_drops_at_tiny_cap():
    # Real task facts are ~35 tokens each; a 64-token cap cannot hold
    # three of them, so some facts must be lost.
    facts = [
        "research fact 1 for task 1: the recorded value is 123 units, reference code R-12345, verified against the source ledger entry on file",
        "research fact 2 for task 1: the recorded value is 456 units, reference code R-67890, verified against the source ledger entry on file",
        "research fact 3 for task 1: the recorded value is 789 units, reference code R-11111, verified against the source ledger entry on file",
    ]
    out = call_tool("web_search", facts, random.Random(11))
    assert retained_facts(out, keywords("anything"), 64) < 1.0


def test_compressibility_between_zero_and_one():
    out = _output()
    c = compressibility(out, keywords("price record"))
    assert 0.0 <= c <= 1.0


def test_learn_profiles_measures_all_tools():
    tasks = generate_tasks()
    traces = run_traces(tasks, ["calculator", "web_search", "document_reader"])
    profiles = learn_profiles(traces)
    assert set(profiles) == {"calculator", "web_search", "document_reader"}
    doc = profiles["document_reader"]
    assert doc.median_tokens > profiles["web_search"].median_tokens
    assert doc.median_tokens > 3000
    assert doc.re_reads == 3
    assert doc.n_traces == 100
    # Retention curve: tight caps lose facts, loose caps keep them.
    assert doc.retention[64] < doc.retention[256] <= 1.0
    assert doc.retained_at(None) == 1.0
    assert doc.retained_at(256) == doc.retention[256]


def test_profiles_json_roundtrip():
    from tool_total_cost_router.profiles import profiles_from_json, profiles_to_json

    tasks = generate_tasks()
    profiles = learn_profiles(run_traces(tasks, ["api_lookup"]))
    restored = profiles_from_json(profiles_to_json(profiles))
    assert restored["api_lookup"].median_tokens == profiles["api_lookup"].median_tokens
    assert restored["api_lookup"].retention == profiles["api_lookup"].retention
