"""Mocked tools with deterministic, measurable output.

Every tool call returns a list of sentences. Some sentences carry the
task's required facts (tagged ``FACT``); the rest are filler that costs
tokens without adding information. Because the output is real generated
text, its token count, its compressibility and how much of it survives a
cap are *measured*, never assumed.

Token counting follows the predecessor project: 1 token ≈ 4 characters.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    """Deterministic token estimate: 1 token per 4 characters."""
    return max(1, int(len(text) / CHARS_PER_TOKEN) + 1)


# Filler sentence templates. Each tool mixes its own filler style so that
# outputs differ in verbosity and in how much of them is droppable.
FILLER = {
    "web_search": [
        "This page also discusses related topics in some detail.",
        "Readers may also be interested in the following background material.",
        "The article continues with a lengthy overview of the subject area.",
        "Several advertisements and navigation links appear between sections.",
        "The site recommends three further articles on similar subjects.",
        "A sidebar lists trending stories from the past week.",
    ],
    "document_reader": [
        "The following section provides additional historical context.",
        "As noted in earlier chapters, the background is extensive.",
        "This paragraph restates the methodology in fuller detail.",
        "The appendix contains tables that are not needed for the answer.",
        "A footnote expands on a minor point raised two pages earlier.",
        "The introduction summarises material covered in other documents.",
    ],
    "database_lookup": [
        "Row metadata includes creation timestamps and internal identifiers.",
        "The record also stores audit fields that are not part of the answer.",
        "Additional columns describe the source system of each record.",
    ],
    "api_lookup": [
        "Response includes pagination metadata and rate-limit headers.",
    ],
    "code_executor": [
        "# standard library imports and environment setup follow",
        "# the runtime prints progress information to standard output",
    ],
    "calculator": [],
}


@dataclass(frozen=True)
class ToolSpec:
    """Static description of a mocked tool."""

    name: str
    description: str
    # How many times the tool's output re-enters the model context in a
    # typical agent loop (final answer turn, verification turn, ...).
    # This is an agent-loop assumption, recorded in traces and learned
    # back by the profile learner — see profiles.py.
    re_reads: int
    # Probability a call fails transiently and must be retried.
    error_rate: float
    # Output size band (tokens) the generator targets.
    min_tokens: int
    max_tokens: int


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("calculator", "Arithmetic on task numbers", re_reads=1, error_rate=0.01, min_tokens=10, max_tokens=40),
    ToolSpec("api_lookup", "Structured field lookup over an API", re_reads=1, error_rate=0.03, min_tokens=60, max_tokens=160),
    ToolSpec("database_lookup", "Row lookup over a table", re_reads=2, error_rate=0.03, min_tokens=250, max_tokens=600),
    ToolSpec("code_executor", "Run a short program and return stdout", re_reads=1, error_rate=0.05, min_tokens=150, max_tokens=500),
    ToolSpec("web_search", "Search results with snippets", re_reads=2, error_rate=0.04, min_tokens=1200, max_tokens=2600),
    ToolSpec("document_reader", "Full document text", re_reads=3, error_rate=0.02, min_tokens=3500, max_tokens=8000),
)

BY_NAME = {t.name: t for t in TOOLS}


@dataclass
class ToolOutput:
    """The result of one mocked tool call."""

    tool: str
    sentences: list[str] = field(default_factory=list)
    facts_present: int = 0
    facts_total: int = 0
    error: bool = False

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    @property
    def tokens(self) -> int:
        return count_tokens(self.text)


def _fact_sentence(tool: str, fact: str) -> str:
    return f"FACT: {fact}"


def call_tool(tool: str, facts: list[str], rng: random.Random) -> ToolOutput:
    """Run a mocked tool. Deterministic given (tool, facts, rng state).

    The output interleaves the task's fact sentences with filler until the
    tool's target token band is reached. Facts are therefore spread through
    the output, which is exactly why truncation and summarisation lose
    information — and why a terse tool can beat a verbose one.
    """
    spec = BY_NAME[tool]
    if rng.random() < spec.error_rate:
        return ToolOutput(tool=tool, sentences=[], facts_present=0, facts_total=len(facts), error=True)

    filler_pool = FILLER[tool]
    sentences: list[str] = []
    fact_sentences = [_fact_sentence(tool, f) for f in facts]
    # Interleave: a fact, then a random run of filler, so facts are spread.
    fact_iter = iter(fact_sentences)
    pending = next(fact_iter, None)
    tokens = 0
    target = rng.randint(spec.min_tokens, spec.max_tokens)
    while tokens < target:
        if pending is not None and rng.random() < 0.35:
            sentences.append(pending)
            tokens += count_tokens(pending)
            pending = next(fact_iter, None)
        elif filler_pool:
            s = rng.choice(filler_pool)
            sentences.append(s)
            tokens += count_tokens(s)
        else:
            break
    # Facts not yet emitted (small outputs) are appended at the end so the
    # tool still returns them — a terse tool returns its facts compactly.
    while pending is not None:
        sentences.append(pending)
        pending = next(fact_iter, None)
    return ToolOutput(
        tool=tool,
        sentences=sentences,
        facts_present=len(facts),
        facts_total=len(facts),
    )
