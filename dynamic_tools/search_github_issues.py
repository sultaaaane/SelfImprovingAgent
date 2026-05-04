# Auto-generated tool: search_github_issues
# Written and sandbox-tested by the agent at runtime.

from langchain_core.tools import tool
import requests

@tool
def search_github_issues(query: str) -> str:
    """Search GitHub issues for a specific query. Returns titles, URLs, and brief descriptions of the issues."""
    try:
        url = f"https://api.github.com/search/issues?q={query}"
        res = requests.get(url, timeout=8)
        if res.status_code != 200:
            return f"Error searching GitHub issues: {res.status_code} - {res.text}"
        data = res.json()
        issues = []
        for item in data["items"]:
            title = item["title"]
            url = item["html_url"]
            description = item["body"][:150] + "..." if len(item["body"]) > 150 else item["body"]
            issues.append(f"Title: {title}\nURL: {url}\nDescription: {description}\n")
        return "\n".join(issues)
    except Exception as e:
        return f"Error searching GitHub issues: {e}"