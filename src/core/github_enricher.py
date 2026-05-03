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
_README_INTRO_CHARS = 500   # always include the opening description
_README_TECH_CHARS  = 2000  # chars to capture from the Tech Stack section onwards
_README_FALLBACK_CHARS = 3000  # if no Tech Stack section found, take this many chars


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
        readme_excerpt = _smart_readme_excerpt(readme_text) if readme_text else ""

        header = f"### {name}  ★{stars}  |  {language}"
        if topics:
            header += f"  |  topics: {topics}"
        lines.append(header)
        if description:
            lines.append(f"Description: {description}")
        if readme_excerpt:
            lines.append(f"README: {readme_excerpt}")
        else:
            # No README — synthesise a tech line from API metadata so the AI
            # still knows the stack (language + topics are reliable signals).
            tech_line = language
            if topics:
                tech_line += ", " + topics
            lines.append(f"Tech: {tech_line}")
        lines.append("")  # blank line between repos

    return "\n".join(lines).strip()


def _smart_readme_excerpt(readme: str) -> str:
    """
    Extract the most useful portion of a README for tech-stack detection.

    Strategy:
    1. Always include the first _README_INTRO_CHARS chars (project description).
    2. Find the Tech Stack / Built With / Technologies section and include up to
       _README_TECH_CHARS chars from that section onwards.
    3. If no such section exists, return the first _README_FALLBACK_CHARS chars.

    This ensures the Tech Stack section is never cut off regardless of how long
    the Features / Documentation sections before it are.
    """
    import re as _re
    _TECH_SECTION_RE = _re.compile(
        r"(^#{1,3}\s*(?:tech(?:nolog(?:y|ies)|nical stack)?|built with|stack|dependencies|tools used)[^\n]*)",
        _re.IGNORECASE | _re.MULTILINE,
    )
    intro = readme[:_README_INTRO_CHARS]
    m = _TECH_SECTION_RE.search(readme)
    if m:
        tech_section = readme[m.start(): m.start() + _README_TECH_CHARS]
        # Combine intro + tech section (deduplicate if they overlap)
        if m.start() < _README_INTRO_CHARS:
            excerpt = readme[:_README_INTRO_CHARS + _README_TECH_CHARS]
        else:
            excerpt = intro + "\n...\n" + tech_section
    else:
        # No dedicated tech section — just return the opening chunk
        excerpt = readme[:_README_FALLBACK_CHARS]
    # Replace ### with #### inside README excerpts so they don't get
    # mistaken for repo-block separators (which also use ###) when the
    # ledger is later split by _extract_github_tech_map.
    import re as _re2
    excerpt = _re2.sub(r"(?m)^### ", "#### ", excerpt)
    return excerpt


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
