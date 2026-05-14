#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _add_support_path() -> None:
    root = Path(__file__).resolve().parents[2]
    support = root / "mn-skills" / "blueprint_support_skill" / "src"
    if support.exists() and str(support) not in sys.path:
        sys.path.insert(0, str(support))


def main(argv: list[str] | None = None) -> int:
    _add_support_path()
    from mn_blueprint_support.agent_templates import validate_agent_library

    parser = argparse.ArgumentParser(description="Validate the mn-agents shared template library.")
    parser.add_argument("--agents-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="Print JSON issues instead of plain text.")
    args = parser.parse_args(argv)

    issues = validate_agent_library(args.agents_root)
    if args.json:
        print(json.dumps({"issues": issues}, indent=2, sort_keys=True))
    elif issues:
        for issue in issues:
            print(f"{issue['severity']}: {issue['field']}: {issue['message']}")
    else:
        print("mn-agents validation passed")
    return 1 if any(issue["severity"] == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
