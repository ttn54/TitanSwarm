"""
GitHub Repo Enricher — fetches public repo metadata + README excerpts
from the GitHub REST API and formats them as a ledger-compatible text block.

No API key required. Uses only Python stdlib urllib (zero new dependencies).
Rate limit: 60 unauthenticated requests/hour — more than enough for a single
profile save.
"""
import base64
import json
import urllib.error
import urllib.request


_GITHUB_API = "https://api.github.com"
_MAX_REPOS = 6
_README_CHARS = 2000  # enough to capture Tech Stack sections in most READMEs


def fetch_github_context(username: str) -> str:
    """
    Fetch the top _MAX_REPOS public, non-fork repos for *username* (sorted by
    stars descending) and return a formatted text block ready to be written into
    the ledger.

    Returns "" on any HTTP error (e.g. 404 unknown user, rate-limit).
    """
    import re as _re
    username = _re.sub(r'^(?:https?://)?github\.com/', '', username.strip()).strip('/')
    if not username:
        return ""

    # ── 1. Fetch repo list ──────────────────────────────────────────────────
    repos_url = f"{_GITHUB_API}/users/{username}/repos?per_page=100&sort=pushed&type=owner"
    req = urllib.request.Request(
        repos_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "TitanSwarm/2.0"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            repos: list[dict] = json.loads(resp.read())
    except urllib.error.HTTPError:
        return ""
    except Exception:
        return ""

    # ── 2. Filter forks + junk repos, sort by stars, take top N ────────────
    _junk_langs = {None, "config"}
    owned = [
        r for r in repos
        if not r.get("fork", False)
        and r.get("language") not in _junk_langs
        and r.get("name", "").lower() != username.lower()  # skip profile README repos
    ]
    owned.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
    top = owned[:_MAX_REPOS]

    if not top:
        return ""

    # ── 3. Fetch README for each repo ───────────────────────────────────────
    lines: list[str] = []
    for repo in top:
        name        = repo.get("name", "")
        stars       = repo.get("stargazers_count", 0)
        language    = repo.get("language") or "Unknown"
        description = repo.get("description") or ""
        topics      = ", ".join(repo.get("topics") or [])

        readme_text = _fetch_readme(username, name)

        header = f"### {name}  ★{stars}  |  {language}"
        if topics:
            header += f"  |  topics: {topics}"
        lines.append(header)
        if description:
            lines.append(f"Description: {description}")
        if readme_text:
            lines.append(f"README: {readme_text[:_README_CHARS]}")
        else:
            # No README — synthesise a tech line from API metadata so the AI
            # still knows the stack (language + topics are reliable signals).
            tech_line = language
            if topics:
                tech_line += ", " + topics
            lines.append(f"Tech: {tech_line}")
        lines.append("")  # blank line between repos

    return "\n".join(lines).strip()


def _fetch_readme(username: str, repo_name: str) -> str:
    """Return the decoded README text for a repo, or "" if unavailable."""
    url = f"{_GITHUB_API}/repos/{username}/{repo_name}/readme"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "TitanSwarm/2.0"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"].replace("\n", "")).decode("utf-8", errors="replace")
        return data.get("content", "")
    except Exception:
        return ""
