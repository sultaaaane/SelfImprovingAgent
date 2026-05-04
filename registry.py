"""
registry.py — Live tool registry that loads tools dynamically at runtime.
The agent uses this instead of a static TOOLS list.
"""

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TOOLS_DIR = Path("dynamic_tools")
TOOLS_DIR.mkdir(exist_ok=True)

MANIFEST_PATH = Path("tool_manifest.json")

# Packages the tool writer is allowed to import
ALLOWED_IMPORTS = {
    "requests", "bs4", "beautifulsoup4", "json", "re", "os",
    "subprocess", "urllib", "http", "collections", "itertools",
    "datetime", "pathlib", "typing", "ddgs", "duckduckgo_search",
    "langchain_core",
}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Any] = {}
        self._load_base_tools()
        self._load_persisted_tools()

    # ── Base tools ────────────────────────────────────────────────────────────

    def _load_base_tools(self):
        try:
            from tools import search_web, read_page
            self.register(search_web)
            self.register(read_page)
            logger.info("Base tools loaded: search_web, read_page")
        except ImportError as e:
            logger.error(f"Failed to load base tools: {e}")

    # ── Persisted dynamic tools ───────────────────────────────────────────────

    def _load_persisted_tools(self):
        """On startup, reload any tools from previous sessions."""
        for path in TOOLS_DIR.glob("*.py"):
            ok, msg = self.load_from_file(str(path))
            if ok:
                logger.info(f"Restored tool from {path.name}: {msg}")
            else:
                logger.warning(f"Could not restore {path.name}: {msg}")

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, tool_fn: Any):
        name = getattr(tool_fn, "name", None) or tool_fn.__name__
        self._tools[name] = tool_fn
        self._save_manifest()

    def load_from_file(self, filepath: str) -> tuple[bool, str]:
        """Dynamically import a generated tool file and register all tools in it."""
        try:
            spec = importlib.util.spec_from_file_location("_dynamic", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            loaded = []
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(module, attr_name)
                # LangChain tools expose .name and .invoke
                if callable(attr) and hasattr(attr, "name") and hasattr(attr, "invoke"):
                    self.register(attr)
                    loaded.append(attr.name)

            if not loaded:
                return False, "No @tool functions found in file"

            self._save_manifest()
            return True, f"Loaded: {loaded}"
        except Exception as e:
            return False, f"Import error: {e}"

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_all(self) -> list:
        return list(self._tools.values())

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def describe(self) -> str:
        """Return a human-readable summary for the planner prompt."""
        lines = []
        for name, fn in self._tools.items():
            desc = getattr(fn, "description", "no description")
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)

    # ── Manifest ──────────────────────────────────────────────────────────────

    def _save_manifest(self):
        manifest = {}
        for name, fn in self._tools.items():
            manifest[name] = getattr(fn, "description", "")
        with open(MANIFEST_PATH, "w") as f:
            json.dump(manifest, f, indent=2)

    @staticmethod
    def validate_imports(code: str) -> tuple[bool, str]:
        """Reject code that imports disallowed packages."""
        import ast
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    root = name.split(".")[0]
                    if root not in ALLOWED_IMPORTS:
                        return False, f"Disallowed import: '{root}'"
        return True, "ok"


# ── Singleton ─────────────────────────────────────────────────────────────────
registry = ToolRegistry()
