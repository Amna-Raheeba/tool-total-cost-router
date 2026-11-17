"""The 100 scripted tasks.

Four task types, 25 each, difficulty split 40 / 35 / 25 across levels
1 / 2 / 3. Each task names the tools that can solve it and each tool's
coverage — the probability the tool returns the needed facts. Coverage
is a property of the task/tool pair, measured by the simulator, and is
the same for both routers.

The generator is deterministic (fixed seed), so ``data/tasks.jsonl`` is
reproducible from ``scripts/generate_tasks.py``.
"""
from __future__ import annotations

import json
import random

TASK_TYPES = ("lookup", "compute", "research", "code")

# Coverage: P(tool returns the needed facts) per task type.
COVERAGE: dict[str, dict[str, float]] = {
    "lookup": {"database_lookup": 0.97, "api_lookup": 0.95, "web_search": 0.60},
    "compute": {"calculator": 0.98, "code_executor": 0.90, "api_lookup": 0.50},
    "research": {"web_search": 0.95, "document_reader": 0.95, "api_lookup": 0.70, "database_lookup": 0.60},
    "code": {"code_executor": 0.96, "document_reader": 0.55, "web_search": 0.50},
}

# Prompt templates per type. {n} is the task number, {a}/{b} are numbers.
PROMPTS = {
    "lookup": "Find the current {field} for record {n} and report it with its source.",
    "compute": "Compute the result of {a} * {b} + {a} and show the working.",
    "research": "Summarise what is known about {topic} and list the key findings.",
    "code": "Write a short program that {goal} and report its output.",
}

FIELDS = ["price", "status", "owner", "expiry date", "location"]
TOPICS = [
    "renewable energy storage",
    "urban water management",
    "smallholder crop insurance",
    "low-cost prosthetics",
    "rural broadband access",
]
GOALS = [
    "counts the vowels in a given sentence",
    "sorts a list of numbers and prints the median",
    "checks whether a year is a leap year",
    "reverses each word in a sentence",
    "finds the largest prime below 100",
]


def generate_tasks(seed: int = 20261117) -> list[dict]:
    """Generate the 100 scripted tasks deterministically."""
    rng = random.Random(seed)
    tasks: list[dict] = []
    difficulties = [1] * 40 + [2] * 35 + [3] * 25
    rng.shuffle(difficulties)
    tid = 0
    for task_type in TASK_TYPES:
        for i in range(25):
            tid += 1
            difficulty = difficulties[tid - 1]
            n_facts = 2 + (difficulty - 1)  # harder tasks need more facts
            if task_type == "lookup":
                prompt = PROMPTS[task_type].format(field=rng.choice(FIELDS), n=1000 + tid)
            elif task_type == "compute":
                prompt = PROMPTS[task_type].format(a=rng.randint(11, 97), b=rng.randint(3, 19))
            elif task_type == "research":
                prompt = PROMPTS[task_type].format(topic=rng.choice(TOPICS))
            else:
                prompt = PROMPTS[task_type].format(goal=rng.choice(GOALS))
            facts = [
                f"{task_type} fact {j + 1} for task {tid}: the recorded value is "
                f"{rng.randint(100, 999)} units, reference code R-{rng.randint(10000, 99999)}, "
                f"verified against the source ledger entry on file"
                for j in range(n_facts)
            ]
            tasks.append(
                {
                    "id": f"T{tid:03d}",
                    "type": task_type,
                    "difficulty": difficulty,
                    "prompt": prompt,
                    "facts": facts,
                    "tools": dict(COVERAGE[task_type]),
                }
            )
    return tasks


def answer_tokens_for(difficulty: int) -> int:
    """Model output budget for the final answer (tokens)."""
    return 100 + 50 * difficulty


def load_tasks(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def save_tasks(tasks: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for task in tasks:
            fh.write(json.dumps(task) + "\n")
