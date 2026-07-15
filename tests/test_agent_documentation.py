from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def catalog_entries() -> list[dict[str, object]]:
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    return [entry for entry in index["agents"] if isinstance(entry, dict)]


def test_every_catalog_agent_has_complete_readme_and_spec() -> None:
    entries = catalog_entries()
    assert entries

    for entry in entries:
        package = ROOT / str(entry["path"])
        readme = package / "README.md"
        spec = package / "SPEC.md"
        agent_id = str(entry["agent_id"])

        assert readme.is_file(), f"{package.name} is missing README.md"
        assert spec.is_file(), f"{package.name} is missing SPEC.md"

        readme_text = readme.read_text(encoding="utf-8")
        spec_text = spec.read_text(encoding="utf-8")

        assert readme_text.startswith("# "), f"{readme} needs one H1 title"
        assert agent_id in readme_text, f"{readme} must name {agent_id}"
        assert "[SPEC.md](SPEC.md)" in readme_text, f"{readme} must link SPEC.md"
        assert len(readme_text) >= 1_000, f"{readme} is too thin to guide reuse"

        assert spec_text.startswith("# "), f"{spec} needs one H1 title"
        assert agent_id in spec_text, f"{spec} must name {agent_id}"
        assert "## Identity" in spec_text, f"{spec} needs identity"
        assert "## Compatibility" in spec_text, f"{spec} needs compatibility rules"
        assert "required tests" in spec_text.lower(), f"{spec} needs test obligations"
        assert len(spec_text) >= 2_000, f"{spec} is too thin to define a contract"


def test_documented_identity_matches_packaged_definition() -> None:
    for entry in catalog_entries():
        resource = ROOT / str(entry["resource_path"])
        definition = json.loads(resource.read_text(encoding="utf-8"))
        package = ROOT / str(entry["path"])
        spec_text = (package / "SPEC.md").read_text(encoding="utf-8")

        assert definition["agent_id"] == entry["agent_id"]
        assert definition["version"] == entry["version"]
        assert str(definition["agent_id"]) in spec_text
        if definition["package_kind"] == "runtime_node":
            assert f"{definition['agent_id']}@{definition['version']}" in spec_text
        else:
            assert f"`{definition['version']}`" in spec_text
