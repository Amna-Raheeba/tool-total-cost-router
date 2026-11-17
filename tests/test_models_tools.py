"""Tests for model pricing and mocked tools."""
import random

from tool_total_cost_router.models import BY_NAME, MODELS, base_success
from tool_total_cost_router.tools import BY_NAME as TOOLS, call_tool, count_tokens


def test_token_counting():
    assert count_tokens("") == 1
    assert count_tokens("abcd") == 2  # 4 chars -> 1 + 1
    assert count_tokens("a" * 40) == 11


def test_model_prices():
    cheap = BY_NAME["flash-lite"]
    assert cheap.input_cost(1_000_000) == 0.10
    assert cheap.output_cost(1_000_000) == 0.40
    premium = BY_NAME["pro"]
    assert premium.input_cost(1_000_000) == 2.50
    assert premium.output_cost(1_000_000) == 10.00
    assert len(MODELS) == 3


def test_base_success_ordering():
    # Harder tasks are harder for every model; better models do better.
    assert base_success(BY_NAME["flash-lite"], 1) > base_success(BY_NAME["flash-lite"], 3)
    assert base_success(BY_NAME["pro"], 3) > base_success(BY_NAME["flash-lite"], 3)


def test_tool_specs_cover_six_tools():
    assert set(TOOLS) == {
        "calculator", "api_lookup", "database_lookup",
        "code_executor", "web_search", "document_reader",
    }
    # Verbose tools re-read more often: the cost the model-only router ignores.
    assert TOOLS["document_reader"].re_reads == 3
    assert TOOLS["calculator"].re_reads == 1
    assert TOOLS["document_reader"].min_tokens > TOOLS["web_search"].min_tokens
    assert TOOLS["web_search"].min_tokens > TOOLS["api_lookup"].min_tokens


def test_call_tool_returns_all_facts():
    rng = random.Random(1)
    facts = ["fact one", "fact two", "fact three"]
    out = call_tool("web_search", facts, rng)
    assert not out.error
    assert out.facts_present == 3
    assert out.tokens > 1000  # verbose tool really is verbose
    assert all(f in out.text for f in facts)


def test_call_tool_deterministic_given_rng():
    facts = ["fact one", "fact two"]
    a = call_tool("document_reader", facts, random.Random(7))
    b = call_tool("document_reader", facts, random.Random(7))
    assert a.sentences == b.sentences
    assert a.tokens == b.tokens


def test_terse_tool_is_terse():
    rng = random.Random(2)
    out = call_tool("calculator", ["x is 42"], rng)
    assert out.tokens < 200


def test_tool_error_rate_is_small():
    rng = random.Random(3)
    errors = sum(1 for _ in range(200) if call_tool("api_lookup", ["f"], rng).error)
    assert errors < 20  # 3% nominal; allow generous slack
