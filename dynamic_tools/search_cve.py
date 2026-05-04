# Auto-generated tool: search_cve
# Written and sandbox-tested by the agent at runtime.

from langchain_core.tools import tool
import requests

@tool
def search_cve(cve_id: str) -> str:
    """Search for details about a Common Vulnerabilities and Exposures (CVE) ID."""
    try:
        url = f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}"
        res = requests.get(url, timeout=8)
        if res.status_code != 200:
            return f"CVE '{cve_id}' not found"
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        cve_info = soup.find('div', class_='vuln-description').text.strip()
        return f"Details for CVE {cve_id}:\n{cve_info}"
    except Exception as e:
        return f"Error searching for CVE: {e}"