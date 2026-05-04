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


def _build_test_script(tool_filepath: str, tool_name: str, test_input: str) -> str:
    """
    Builds a test harness that imports the tool file via importlib (same as
    registry.py does), then invokes the tool.

    The old approach embedded raw tool code and scanned globals() — this failed
    because LangChain's @tool decorator produces a StructuredTool object that
    isn't visible in globals() at scan time.
    """
    safe_path = tool_filepath.replace("\\", "\\\\")
    harness = f"""
import sys
import importlib.util

TOOL_FILE  = r"{safe_path}"
TOOL_NAME  = "{tool_name}"
TEST_INPUT = "{test_input}"

try:
    spec = importlib.util.spec_from_file_location("_tool_under_test", TOOL_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except Exception as e:
    print(f"ERROR: Could not import tool file: {{e}}", file=sys.stderr)
    sys.exit(1)

tools = []
for attr_name in dir(module):
    if attr_name.startswith("_"):
        continue
    obj = getattr(module, attr_name)
    if hasattr(obj, "name") and hasattr(obj, "invoke") and callable(obj.invoke):
        tools.append(obj)

if not tools:
    print("ERROR: No @tool functions found in module", file=sys.stderr)
    sys.exit(1)

target = next((t for t in tools if getattr(t, "name", "") == TOOL_NAME), tools[0])
print(f"Testing tool: {{target.name}}")

try:
    result = target.invoke(TEST_INPUT)
    result_str = str(result).strip()
    if not result_str:
        print("ERROR: Tool returned empty output", file=sys.stderr)
        sys.exit(1)
    print("OUTPUT:", result_str[:500])
    sys.exit(0)
except Exception as e:
    print(f"ERROR: Tool invocation failed: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    return harness


def run_in_sandbox(
    tool_code: str,
    tool_name: str,
    test_input: str = "python",
    timeout: int = 15,
) -> tuple[bool, str]:
    """
    Write the tool code to a temp file, run the harness against it in a
    subprocess, return (passed, output_or_error).
    """
    TOOLS_DIR.mkdir(exist_ok=True)

    # 1. Write tool code to temp file so harness can importlib-load it
    tool_fd, tool_path = tempfile.mkstemp(
        suffix=".py", prefix=f"_tool_{tool_name}_", dir=str(TOOLS_DIR)
    )
    try:
        with os.fdopen(tool_fd, "w") as f:
            f.write(tool_code)

        # 2. Write harness script
        harness_fd, harness_path = tempfile.mkstemp(
            suffix=".py", prefix=f"_harness_{tool_name}_", dir=str(TOOLS_DIR)
        )
        try:
            with os.fdopen(harness_fd, "w") as f:
                f.write(_build_test_script(tool_path, tool_name, test_input))

            result = subprocess.run(
                ["python3", harness_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONPATH": os.getcwd()},
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0 and "OUTPUT:" in stdout:
                output_line = stdout.split("OUTPUT:", 1)[-1].strip()
                logger.info(f"[sandbox] {tool_name} PASSED: {output_line[:100]}")
                return True, output_line
            else:
                error_msg = stderr or stdout or "Unknown error"
                logger.warning(f"[sandbox] {tool_name} FAILED: {error_msg}")
                return False, error_msg

        except subprocess.TimeoutExpired:
            msg = f"Tool '{tool_name}' timed out after {timeout}s"
            logger.error(f"[sandbox] {msg}")
            return False, msg
        except Exception as e:
            return False, str(e)
        finally:
            try:
                os.unlink(harness_path)
            except Exception:
                pass

    finally:
        try:
            os.unlink(tool_path)
        except Exception:
            pass


def persist_tool(tool_name: str, tool_code: str) -> Path:
    """Save a passing tool permanently to dynamic_tools/."""
    TOOLS_DIR.mkdir(exist_ok=True)
    path = TOOLS_DIR / f"{tool_name}.py"
    with open(path, "w") as f:
        f.write(f"# Auto-generated tool: {tool_name}\n")
        f.write("# Written and sandbox-tested by the agent at runtime.\n\n")
        f.write(tool_code)
    logger.info(f"[sandbox] Persisted {tool_name} → {path}")
    return path
