# Auto-generated tool: fetch_github_readme
# Written and sandbox-tested by the agent at runtime.

from langchain_core.tools import tool
import requests

@tool
def fetch_github_readme(repo_url: str) -> str:
    """Fetch the README content from a GitHub repository URL."""
    try:
        # Extract the username and repo name from the URL
        parts = repo_url.split('/')
        if len(parts) < 5 or parts[3] != 'repos':
            return "Invalid GitHub repository URL"
        
        username = parts[4]
        repo_name = parts[5]
        
        # Construct the API URL to fetch the README
        api_url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
        
        # Make the request to the GitHub API
        res = requests.get(api_url, timeout=8)
        if res.status_code != 200:
            return "README not found or repository does not exist"
        
        # Decode and return the README content
        readme_content = res.json()['content']
        return base64.b64decode(readme_content).decode('utf-8')
    except Exception as e:
        return f"Error fetching GitHub README: {e}"