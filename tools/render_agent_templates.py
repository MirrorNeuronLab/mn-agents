#!/usr/bin/env python3.11
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
    from mn_blueprint_support.agent_templates import render_manifest_agent_templates

    parser = argparse.ArgumentParser(description="Render mn-agents template references in a blueprint manifest.")
    parser.add_argument("manifest", type=Path, help="Manifest containing optional nodes[].uses references.")
    parser.add_argument("--agents-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Output path. Defaults to stdout.")
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rendered = render_manifest_agent_templates(manifest, args.agents_root)
    text = json.dumps(rendered, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
