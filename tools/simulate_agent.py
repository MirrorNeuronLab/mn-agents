#!/usr/bin/env python3.11
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _add_support_path() -> None:
    workspace = Path(__file__).resolve().parents[2]
    support = workspace / "mn-skills" / "blueprint_support_skill" / "src"
    if support.exists() and str(support) not in sys.path:
        sys.path.insert(0, str(support))
    agents_root = Path(__file__).resolve().parents[1]
    if str(agents_root) not in sys.path:
        sys.path.insert(0, str(agents_root))


def _load_node(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "uses" in data:
        return data
    if isinstance(data, dict) and isinstance(data.get("nodes"), list) and len(data["nodes"]) == 1:
        return data["nodes"][0]
    raise SystemExit("input JSON must be a single agent fixture/node, or a manifest with exactly one node")


def main(argv: list[str] | None = None) -> int:
    _add_support_path()
    from tools.agent_behavior import find_agents_root, simulate_agent_instance

    parser = argparse.ArgumentParser(description="Simulate a single mn-agents fixture or manifest node.")
    parser.add_argument("node", type=Path, help="Path to a fixture JSON file, node JSON file, or one-node manifest.")
    parser.add_argument("--agents-root", type=Path, help="Path to mn-agents root. Defaults to auto-detection.")
    args = parser.parse_args(argv)

    node = _load_node(args.node)
    agents_root = args.agents_root or find_agents_root(args.node)
    result = simulate_agent_instance(node, agents_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
