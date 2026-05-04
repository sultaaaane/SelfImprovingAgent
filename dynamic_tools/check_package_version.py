# Auto-generated tool: check_package_version
# Written and sandbox-tested by the agent at runtime.

from langchain_core.tools import tool
import requests

@tool
def check_package_version(package_name: str) -> str:
    """Check the latest version of a Python package on PyPI."""
    try:
        res = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=8)
        if res.status_code != 200:
            return f"Package '{package_name}' not found on PyPI"
        d = res.json()["info"]
        latest_version = d["version"]
        return f"The latest version of {package_name} is {latest_version}"
    except Exception as e:
        return f"Error checking package version: {e}"