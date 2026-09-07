from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .execution import GeneratedCodePolicy, execute_generated_python, _clean, _digest

ToolHandler = Callable[[dict[str, Any]], Any]

@dataclass
class ToolRegistry:
    allowed_tools: set[str]
    handlers: dict[str, ToolHandler] = field(default_factory=dict)

    def register(self, name: str, handler: ToolHandler) -> None:
        normalized = _clean(name, limit=120)
        if normalized not in self.allowed_tools:
            raise ValueError(f"tool is not allowlisted: {normalized}")
        self.handlers[normalized] = handler

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        normalized = _clean(name, limit=120)
        if normalized not in self.allowed_tools:
            raise ValueError(f"tool is not allowlisted: {normalized}")
        if normalized not in self.handlers:
            raise ValueError(f"tool is not registered: {normalized}")
        return self.handlers[normalized](arguments or {})


@dataclass
class ToolSession:
    goal: dict[str, Any]
    registry: ToolRegistry
    workspace: Path
    prompt_factory: Callable[..., dict[str, Any]]
    max_tool_calls: int = 12
    code_policy: GeneratedCodePolicy = field(default_factory=GeneratedCodePolicy)
    prompts: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)

    def run(self, propose_action, *, max_iterations=8):
        """Compose session tools with the package's shared bounded loop."""
        from . import ToolLoopSpec, create_agent

        remaining = max(0, self.max_tool_calls - sum(item.get("kind") == "tool_call" for item in self.trace))
        agent = create_agent(ToolLoopSpec(
            propose_action=propose_action,
            execute_action=lambda context, action, **options: self.use_tool(action.name, dict(action.arguments)),
            validate_action=lambda context, action, **options: action.name in self.registry.allowed_tools,
            max_iterations=max_iterations, max_tool_calls=remaining,
        ))
        return agent(self.goal)

    def create_prompt(
        self,
        *,
        phase: str,
        instructions: list[str],
        context_refs: list[str] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        requested = sorted(self.registry.allowed_tools) if allowed_tools is None else allowed_tools
        unknown = sorted(set(requested) - self.registry.allowed_tools)
        if unknown:
            raise ValueError(f"prompt requested non-allowlisted tools: {', '.join(unknown)}")
        prompt = self.prompt_factory(
            self.goal,
            phase=phase,
            instructions=instructions,
            context_refs=context_refs,
            allowed_tools=requested,
        )
        self.prompts.append(prompt)
        self.trace.append({"kind": "prompt_created", "phase": phase, "prompt_id": prompt["prompt_id"]})
        return prompt

    def use_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        tool_calls = sum(1 for item in self.trace if item.get("kind") == "tool_call")
        if tool_calls >= self.max_tool_calls:
            raise RuntimeError("autonomous tool-call budget exhausted")
        call_id = f"tool_{tool_calls + 1:03d}"
        started = time.monotonic()
        try:
            result = self.registry.execute(name, arguments)
            self.trace.append(
                {
                    "kind": "tool_call",
                    "call_id": call_id,
                    "tool": name,
                    "status": "completed",
                    "arguments_sha256": _digest(arguments or {}),
                    "result_sha256": _digest(result),
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
                }
            )
            return result
        except Exception as exc:
            self.trace.append(
                {
                    "kind": "tool_call",
                    "call_id": call_id,
                    "tool": name,
                    "status": "failed",
                    "arguments_sha256": _digest(arguments or {}),
                    "error": str(exc)[:1000],
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
                }
            )
            raise

    def execute_python(self, code: str, *, input_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        execution_id = f"generated_{sum(1 for item in self.trace if item.get('kind') == 'generated_code') + 1:03d}"
        result = execute_generated_python(
            code,
            workspace=self.workspace,
            input_payload=input_payload,
            policy=self.code_policy,
            execution_id=execution_id,
        )
        self.trace.append(
            {
                "kind": "generated_code",
                "execution_id": result["execution_id"],
                "status": result["status"],
                "returncode": result["returncode"],
                "code_sha256": result["code_sha256"],
                "elapsed_ms": result["elapsed_ms"],
            }
        )
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "mn.autonomous_research.session.v1",
            "goal": self.goal,
            "prompts": self.prompts,
            "trace": self.trace,
            "workspace": str(self.workspace),
            "tool_budget": self.max_tool_calls,
            "tool_calls_used": sum(1 for item in self.trace if item.get("kind") == "tool_call"),
            "generated_code_runs": sum(1 for item in self.trace if item.get("kind") == "generated_code"),
        }


