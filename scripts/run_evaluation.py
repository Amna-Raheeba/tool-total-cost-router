#!/usr/bin/env python3
"""Learn profiles (if missing) and run the 100-task evaluation.

Used by CI (see .github/workflows/ci.yml) and locally:
    python scripts/run_evaluation.py
Writes results/evaluation.csv and results/evaluation_summary.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool_total_cost_router.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["evaluate"]))
