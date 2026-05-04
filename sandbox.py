"""
sandbox.py — Runs generated tool code in an isolated subprocess before loading it.
The generated code NEVER executes inside the main agent process until it passes.
"""

import os
import subprocess
import tempfile
import textwrap
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TOOLS_DIR = Path("dynamic_tools")


def _build_test_script(tool_code: str, tool_name: str, test_input: str) -> str:
    """
    Wraps the tool code with a small test harness that calls it and prints output.
    We detect tool functions by looking for @tool decorated callables.
    """
    harness = textwrap.dedent(f"""
import sys
import json

# ── Generated tool code ──────────────────────────────────────────────────────
{tool_code}

# ── Auto test harness ────────────────────────────────────────────────────────
import inspect, types

def find_tools(module_globals):
    found = []
    for name, obj in module_globals.items():
        if name.startswith('_'):
            continue
        if callable(obj) and hasattr(obj, 'name') and hasattr(obj, 'invoke'):
            found.append(obj)
    return found

tools = find_tools(dict(list(globals().items())))
if not tools:
    print("ERROR: No @tool functions found", file=sys.stderr)
    sys.exit(1)

target = next((t for t in tools if t.name == '{tool_name}'), tools[0])
print(f"Testing tool: {{target.name}}")

try:
    result = target.invoke('{test_input}')
    if not result or result.strip() == "":
        print("ERROR: Tool returned empty output", file=sys.stderr)
        sys.exit(1)
    print("OUTPUT:", result[:500])
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
""")
    return harness


def run_in_sandbox(
    tool_code: str,
    tool_name: str,
    test_input: str = "python",
    timeout: int = 15,
) -> tuple[bool, str]:
    """
    Execute generated tool code in an isolated subprocess.

    Returns:
        (passed: bool, message: str)
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix=f"_test_{tool_name}_",
        dir=str(TOOLS_DIR),
        delete=False,
    ) as f:
        script = _build_test_script(tool_code, tool_name, test_input)
        f.write(script)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONPATH": os.getcwd()},
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0 and "OUTPUT:" in stdout:
            output_line = stdout.split("OUTPUT:", 1)[-1].strip()
            logger.info(f"[sandbox] {tool_name} passed: {output_line[:100]}")
            return True, output_line
        else:
            error_msg = stderr or stdout or "Unknown error"
            logger.warning(f"[sandbox] {tool_name} failed: {error_msg}")
            return False, error_msg

    except subprocess.TimeoutExpired:
        msg = f"Tool '{tool_name}' timed out after {timeout}s"
        logger.error(f"[sandbox] {msg}")
        return False, msg
    except Exception as e:
        return False, str(e)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def persist_tool(tool_name: str, tool_code: str) -> Path:
    """Save a passing tool to the dynamic_tools directory."""
    path = TOOLS_DIR / f"{tool_name}.py"
    with open(path, "w") as f:
        f.write(f"# Auto-generated tool: {tool_name}\n")
        f.write("# This file was written and tested by the agent at runtime.\n\n")
        f.write(tool_code)
    logger.info(f"[sandbox] Persisted tool to {path}")
    return path
