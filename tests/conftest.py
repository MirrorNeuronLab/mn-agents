from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent

for path in [
    WORKSPACE / "mn-python-sdk",
    *sorted(ROOT.glob("prototype_*_agent/src")),
]:
    sys.path.insert(0, str(path))
