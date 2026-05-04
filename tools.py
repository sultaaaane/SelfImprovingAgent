"""
tools.py — Base tools available from startup.
Dynamic tools are written at runtime and live in dynamic_tools/
"""

from langchain_core.tools import tool
import requests
from bs4 import BeautifulSoup

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


@tool
def search_web(query: str) -> str:
    """Search the web for a query. Returns titles, URLs, and snippets."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No results found"
        output = ""
        for r in results:
            output += f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n\n"
        return output.strip()
    except Exception as e:
        return f"Search error: {e}"


@tool
def read_page(url: str) -> str:
    """Fetch and extract the main text content from a webpage URL."""
    try:
        res = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:8000]
    except Exception as e:
        return f"Failed to read page: {e}"
