"""Root conftest: makes the package importable under plain `pytest`.

GitHub Actions runs plain `pytest` (see .github/workflows/ci.yml), which
does not put the repo root on sys.path the way `python -m pytest` does.
The `pythonpath = ["."]` setting in pyproject.toml covers it; this file
exists as the belt-and-braces copy used by the other repos in this
portfolio.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
