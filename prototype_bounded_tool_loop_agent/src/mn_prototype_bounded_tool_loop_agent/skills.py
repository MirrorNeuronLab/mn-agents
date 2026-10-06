"""Discover installed, explicitly declared skills and invoke their public APIs."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from importlib import metadata, resources

from jsonschema import Draft202012Validator


class SkillRuntime:
    """Trusted bindings carry resources; the model supplies only schema-checked arguments."""

    def __init__(
        self,
        descriptors,
        bindings: Mapping[tuple[str, str], Callable],
        *,
        max_output_bytes=65536,
    ):
        self.descriptors = {}
        self.bindings = dict(bindings)
        self.read_hashes = {}
        self.max_output_bytes = max_output_bytes
        for descriptor in descriptors:
            identifier = descriptor["id"]
            if identifier in self.descriptors:
                raise ValueError(f"duplicate skill: {identifier}")
            for operation in descriptor["operations"].values():
                Draft202012Validator.check_schema(operation["arguments"])
            self.descriptors[identifier] = descriptor
        for identifier, operation in self.bindings:
            if (
                identifier not in self.descriptors
                or operation not in self.descriptors[identifier]["operations"]
            ):
                raise ValueError("binding has no declared skill operation")

    @classmethod
    def discover(cls, distributions, bindings, *, install_dependencies=True, **options):
        """Register admitted packages after their optional local dependency setup.

        Python distributions must already be installed. Setup runs once per
        explicitly supplied distribution; imports and invocation never install.
        """
        if not isinstance(install_dependencies, bool):
            raise ValueError("install_dependencies must be a boolean")
        descriptors = []
        setups = []
        for name in sorted(set(distributions)):
            distribution = metadata.distribution(name)
            entries = [e for e in distribution.entry_points if e.group == "mn.skills"]
            if not entries:
                raise ValueError(f"declared skill has no mn.skills descriptor: {name}")
            for entry in entries:
                descriptor = entry.load()()
                descriptor["distribution"] = distribution.metadata["Name"]
                descriptor["version"] = distribution.version
                descriptors.append(descriptor)
            hooks = [e for e in distribution.entry_points if e.group == "mn.skills.setup"]
            if len(hooks) > 1:
                raise ValueError(f"declared skill has multiple mn.skills.setup hooks: {name}")
            if hooks:
                setups.append((name, hooks[0]))
        # Validate every descriptor and binding before any dependency side effect.
        runtime = cls(descriptors, bindings, **options)
        runtime.preparation = {}
        for name, entry in setups:
            result = entry.load()({"version": 1, "allow_install": install_dependencies})
            if not isinstance(result, dict) or result.get("version") != 1 or result.get("status") not in {"ready", "installed"}:
                raise ValueError(f"skill dependency setup did not complete: {name}")
            runtime.preparation[name] = result
        return runtime

    def list_skills(self):
        return [
            {
                "id": key,
                "description": value["description"],
                "operations": sorted(op for skill, op in self.bindings if skill == key),
            }
            for key, value in sorted(self.descriptors.items())
        ]

    def read_skill(self, skill):
        descriptor = self.descriptors[skill]
        manual = (
            resources.files(descriptor["module"])
            .joinpath("resources/SKILL.md")
            .read_text(encoding="utf-8")
        )
        digest = hashlib.sha256(manual.encode()).hexdigest()
        self.read_hashes[skill] = digest
        return {
            "skill": skill,
            "sha256": digest,
            "manual": manual,
            "operations": {
                name: spec["arguments"]
                for name, spec in descriptor["operations"].items()
                if (skill, name) in self.bindings
            },
        }

    def invoke_skill(self, skill, operation, arguments):
        import json

        if skill not in self.read_hashes:
            raise ValueError("read_skill must precede invocation")
        if (skill, operation) not in self.bindings:
            raise ValueError("skill operation is not registered")
        schema = self.descriptors[skill]["operations"][operation]["arguments"]
        Draft202012Validator(schema).validate(arguments)
        result = self.bindings[skill, operation](**arguments)
        if (
            len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode())
            > self.max_output_bytes
        ):
            raise ValueError("skill output exceeded byte limit; narrow the enquiry")
        return result
