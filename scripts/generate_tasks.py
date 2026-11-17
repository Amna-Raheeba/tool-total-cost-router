#!/usr/bin/env python3
"""Generate the 100 scripted tasks into data/tasks.jsonl (deterministic)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool_total_cost_router.tasks import generate_tasks, save_tasks

if __name__ == "__main__":
    tasks = generate_tasks()
    out = Path(__file__).resolve().parent.parent / "data" / "tasks.jsonl"
    save_tasks(tasks, str(out))
    print(f"wrote {len(tasks)} tasks to {out}")
