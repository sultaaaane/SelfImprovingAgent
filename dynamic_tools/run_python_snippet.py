# Auto-generated tool: run_python_snippet
# Written and sandbox-tested by the agent at runtime.

from langchain_core.tools import tool
import requests

@tool
def run_python_snippet(snippet: str) -> str:
    """Run a Python code snippet and return the output."""
    try:
        # Create a temporary file to store the snippet
        with open("temp_script.py", "w") as f:
            f.write(snippet)
        
        # Run the script using exec
        local_vars = {}
        global_vars = {}
        exec(compile(open("temp_script.py").read(), "temp_script.py", 'exec'), global_vars, local_vars)
        
        # Return the output of the snippet
        return str(local_vars.get("__result__", "No output"))
    except Exception as e:
        return f"Error running Python snippet: {e}"