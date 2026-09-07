from __future__ import annotations
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ToolHandler = Callable[[dict[str, Any]], Any]

def _clean(value: Any, *, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class GeneratedCodePolicy:
    timeout_seconds: int = 15
    max_output_chars: int = 20_000
    max_code_chars: int = 40_000
    max_memory_mb: int = 256
    allowed_imports: tuple[str, ...] = (
        "collections",
        "csv",
        "datetime",
        "decimal",
        "functools",
        "hashlib",
        "itertools",
        "json",
        "math",
        "operator",
        "random",
        "re",
        "statistics",
    )


    def __post_init__(self):
        limits = {"timeout_seconds": 600, "max_output_chars": 1_000_000,
                  "max_code_chars": 1_000_000, "max_memory_mb": 4096}
        for name, maximum in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= maximum:
                raise ValueError(f"{name} must be an integer between 1 and {maximum}")


def _validate_generated_python(code: str, policy: GeneratedCodePolicy) -> ast.AST:
    if not code.strip():
        raise ValueError("generated code is empty")
    if len(code) > policy.max_code_chars:
        raise ValueError("generated code exceeds max_code_chars")
    tree = ast.parse(code, mode="exec")
    blocked_calls = {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "memoryview",
        "open",
        "setattr",
        "vars",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [item.name.split(".", 1)[0] for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".", 1)[0]]
        else:
            names = []
        blocked_import = next((name for name in names if name not in policy.allowed_imports), "")
        if blocked_import:
            raise ValueError(f"generated code import is not allowed: {blocked_import}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
            raise ValueError(f"generated code call is not allowed: {node.func.id}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("generated code dunder names are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("generated code dunder attribute access is not allowed")
    return tree


def _resource_limiter(policy: GeneratedCodePolicy) -> Callable[[], None] | None:
    if os.name != "posix" or not sys.platform.startswith("linux"):
        return None

    def apply_limits() -> None:
        import resource

        memory = max(64, policy.max_memory_mb) * 1024 * 1024
        cpu = max(1, policy.timeout_seconds)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    return apply_limits


def execute_generated_python(
    code: str,
    *,
    workspace: str | Path,
    input_payload: dict[str, Any] | None = None,
    policy: GeneratedCodePolicy | None = None,
    execution_id: str = "",
) -> dict[str, Any]:
    """Validate and execute generated Python in the caller's outer sandbox."""

    resolved_policy = policy or GeneratedCodePolicy()
    _validate_generated_python(code, resolved_policy)
    input_bytes = json.dumps(input_payload or {}, sort_keys=True).encode("utf-8")
    if len(input_bytes) > 1_048_576:
        raise ValueError("generated-code input exceeds the one MiB limit")
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    identifier = _clean(execution_id, limit=120) or _digest(code)[:12]
    safe_identifier = re.sub(r"[^A-Za-z0-9_.-]+", "-", identifier).strip(".-") or "generated"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                     prefix=f"{safe_identifier}-", suffix=".py", delete=False) as script:
        script.write(code)
        script_path = Path(script.name)
    started = time.monotonic()
    stdout, stderr, returncode, timed_out = _run_bounded_process(
        script_path, root, input_bytes, resolved_policy,
    )
    return {
        "execution_id": safe_identifier,
        "status": "timed_out" if timed_out else "completed" if returncode == 0 else "failed",
        "returncode": None if timed_out else returncode,
        "stdout": stdout[0], "stderr": stderr[0],
        "stdout_truncated": stdout[1], "stderr_truncated": stderr[1],
        "code_sha256": _digest(code), "script_path": str(script_path),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
    }


def _run_bounded_process(script, root, input_bytes, policy):
    import signal
    import tempfile
    import threading

    buffers = [bytearray(), bytearray()]
    truncated = [False, False]
    limit = policy.max_output_chars * 4

    def drain(stream, index):
        with stream:
            while chunk := stream.read(4096):
                remaining = max(0, limit - len(buffers[index]))
                buffers[index].extend(chunk[:remaining])
                truncated[index] |= len(chunk) > remaining

    with tempfile.TemporaryFile() as input_file:
        input_file.write(input_bytes)
        input_file.seek(0)
        with subprocess.Popen(
            [sys.executable, "-I", str(script)], stdin=input_file,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=root,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "LANG": "C.UTF-8"},
            start_new_session=True, preexec_fn=_resource_limiter(policy),
        ) as process:
            readers = [threading.Thread(target=drain, args=(stream, index), daemon=True)
                       for index, stream in enumerate((process.stdout, process.stderr))]
            for reader in readers:
                reader.start()
            timed_out = False
            try:
                process.wait(timeout=policy.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                # Reap the whole execution group, including descendants that
                # could otherwise keep the output pipes open after parent exit.
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                elif process.poll() is None:
                    process.kill()
                process.wait()
                for reader in readers:
                    reader.join(timeout=2)
            result = []
            for index, buffer in enumerate(buffers):
                output = bytes(buffer).decode("utf-8", errors="replace")
                result.append((output[:policy.max_output_chars], truncated[index] or len(output) > policy.max_output_chars))
            return result[0], result[1], process.returncode, timed_out
