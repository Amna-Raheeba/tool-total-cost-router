"""Per-tool output-cost profiles, learned offline from mocked traces.

A profile is measured, not asserted: the learner runs each mocked tool
over the task set, records the real output text, and computes

- ``median_tokens`` / ``p90_tokens`` — output size,
- ``compressibility`` — the fraction of output tokens sitting in
  sentences that contain none of the task keywords (droppable by an
  extractive summariser),
- ``re_reads`` — how many times the output re-entered the context,
- ``retry_rate`` — the fraction of calls that errored and were retried.

The same extractive summariser is used at routing time to apply an
output cap: it keeps the highest keyword-overlap sentences first, so the
retained-fact fraction after a cap is a measured quantity too.
"""
from __future__ import annotations

import json
import random
import re
import statistics
from dataclasses import asdict, dataclass

from .tools import BY_NAME, ToolOutput, call_tool, count_tokens

_WORD = re.compile(r"[a-z0-9]+")


def keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2}


def sentence_score(sentence: str, keys: set[str]) -> int:
    """Relevance of a sentence to the task.

    Keyword overlap with the prompt, plus a fixed bonus for FACT
    sentences: by construction they carry the answer-bearing content,
    the analogue of a real retriever ranking answer passages highly.
    Without the bonus, fact sentences score like filler and the
    summariser would drop the answer first.
    """
    return len(keywords(sentence) & keys) + (10 if sentence.startswith("FACT:") else 0)


def extractive_keep(sentences: list[str], keys: set[str], cap_tokens: int | None) -> list[str]:
    """Keep sentences by keyword overlap until the token cap is reached.

    Fact sentences carry the task's keywords, so they score highest and
    survive first. ``cap_tokens=None`` keeps everything. The kept list is
    returned in original order.
    """
    if cap_tokens is None:
        return list(sentences)
    scored = sorted(
        enumerate(sentences),
        key=lambda pair: (-sentence_score(pair[1], keys), pair[0]),
    )
    kept_idx: set[int] = set()
    used = 0
    for idx, sentence in scored:
        cost = count_tokens(sentence)
        if used + cost > cap_tokens and kept_idx:
            continue
        kept_idx.add(idx)
        used += cost
        if used >= cap_tokens:
            break
    return [s for i, s in enumerate(sentences) if i in kept_idx]


def retained_facts(output: ToolOutput, keys: set[str], cap_tokens: int | None) -> float:
    """Fraction of the task's facts still present after applying a cap."""
    if output.facts_total == 0:
        return 1.0
    kept = extractive_keep(output.sentences, keys, cap_tokens)
    kept_facts = sum(1 for s in kept if s.startswith("FACT:"))
    return kept_facts / output.facts_total


def compressibility(output: ToolOutput, keys: set[str]) -> float:
    """Fraction of output tokens in sentences with zero keyword overlap.

    Computed from character lengths, not per-sentence token counts:
    each per-sentence count adds a +1 rounding term, so summing them can
    exceed the whole output's token count and push the ratio above 1.
    """
    total = sum(len(s) for s in output.sentences)
    if total == 0:
        return 0.0
    droppable = sum(
        len(s) for s in output.sentences if sentence_score(s, keys) == 0
    )
    return droppable / total


# Caps at which retention is measured. The grid is fine (16-token steps)
# between 64 and 256 — that is where the retention curve actually moves:
# fact sentences are ~35 tokens each, so a task's facts need 68-144
# tokens in total. A coarse grid (64/128/256) would jump from 0.94
# straight to 1.00 and hide the true threshold.
CAPS = (64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 320, 384, 512, 1024, 2048)


@dataclass
class ToolProfile:
    tool: str
    median_tokens: float
    p90_tokens: float
    compressibility: float
    re_reads: int
    retry_rate: float
    n_traces: int
    # Measured mean retained-fact fraction at each output cap, from real
    # traces (extractive summarisation). The router reads this curve
    # instead of guessing how much a cap costs in information.
    retention: dict[int, float]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["retention"] = {str(k): v for k, v in self.retention.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ToolProfile":
        data = dict(data)
        data["retention"] = {int(k): v for k, v in data.get("retention", {}).items()}
        return cls(**data)

    def retained_at(self, cap_tokens: int | None) -> float:
        if cap_tokens is None:
            return 1.0
        return self.retention.get(cap_tokens, 1.0)

    def optimal_cap(self, threshold: float = 0.95) -> int | None:
        """Cheapest measured cap preserving at least ``threshold`` of facts.

        This is the per-tool optimal-cap advisor: read the tool's own
        measured retention curve and take the smallest cap that clears
        the retention floor. Returns ``None`` (uncapped) when no
        measured cap reaches the threshold — the advisor never
        recommends a cap it has not measured as safe.
        """
        for cap in sorted(self.retention):
            if self.retention[cap] >= threshold:
                return cap
        return None


def optimal_caps(
    profiles: dict[str, ToolProfile], threshold: float = 0.95
) -> dict[str, int | None]:
    """One optimal cap per tool, from each tool's own retention curve."""
    return {tool: p.optimal_cap(threshold) for tool, p in profiles.items()}


@dataclass
class Trace:
    tool: str
    tokens: int
    compressibility: float
    re_reads: int
    error: bool
    sentences: list[str]
    keys: set[str]
    facts_total: int


def run_traces(tasks: list[dict], tools: list[str], seed: int = 20261117) -> list[Trace]:
    """Run every tool over every task's facts and record a trace per call."""
    rng = random.Random(seed)
    traces: list[Trace] = []
    for task in tasks:
        keys = keywords(task["prompt"])
        for tool in tools:
            out = call_tool(tool, task["facts"], rng)
            traces.append(
                Trace(
                    tool=tool,
                    tokens=out.tokens,
                    compressibility=compressibility(out, keys) if not out.error else 0.0,
                    re_reads=BY_NAME[tool].re_reads,
                    error=out.error,
                    sentences=out.sentences,
                    keys=keys,
                    facts_total=out.facts_total,
                )
            )
    return traces


def learn_profiles(traces: list[Trace]) -> dict[str, ToolProfile]:
    """Aggregate traces into one profile per tool."""
    by_tool: dict[str, list[Trace]] = {}
    for trace in traces:
        by_tool.setdefault(trace.tool, []).append(trace)
    profiles: dict[str, ToolProfile] = {}
    for tool, rows in by_tool.items():
        ok = [r for r in rows if not r.error]
        token_list = sorted(r.tokens for r in ok)
        p90 = token_list[min(len(token_list) - 1, int(0.9 * len(token_list)))] if token_list else 0
        retention: dict[int, float] = {}
        for cap in CAPS:
            vals = []
            for r in ok:
                out = ToolOutput(tool=tool, sentences=r.sentences, facts_total=r.facts_total)
                vals.append(retained_facts(out, r.keys, cap))
            retention[cap] = float(statistics.mean(vals)) if vals else 1.0
        profiles[tool] = ToolProfile(
            tool=tool,
            median_tokens=float(statistics.median(token_list)) if token_list else 0.0,
            p90_tokens=float(p90),
            compressibility=float(statistics.mean([r.compressibility for r in ok])) if ok else 0.0,
            re_reads=int(statistics.median([r.re_reads for r in rows])) if rows else 0,
            retry_rate=len(rows) and sum(1 for r in rows if r.error) / len(rows),
            n_traces=len(rows),
            retention=retention,
        )
    return profiles


def profiles_to_json(profiles: dict[str, ToolProfile]) -> str:
    return json.dumps({k: v.to_dict() for k, v in profiles.items()}, indent=2)


def profiles_from_json(text: str) -> dict[str, ToolProfile]:
    return {k: ToolProfile.from_dict(v) for k, v in json.loads(text).items()}
