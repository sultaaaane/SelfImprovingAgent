# Auto-generated tool: fetch_pypi_info
# Written and sandbox-tested by the agent at runtime.

from langchain_core.tools import tool
import requests

@tool
def fetch_pypi_info(package_name: str) -> str:
    """Fetch PyPI metadata for a Python package: latest version, summary, homepage, license."""
    try:
        res = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=8)
        if res.status_code != 200:
            return f"Package '{package_name}' not found on PyPI"
        d = res.json()["info"]
        return (
            f"Package: {d['name']}\n"
            f"Version: {d['version']}\n"
            f"Summary: {d['summary']}\n"
            f"License: {d.get('license', 'N/A')}\n"
            f"Homepage: {d.get('home_page', 'N/A')}"
        )
    except Exception as e:
        return f"Error fetching PyPI info: {e}"