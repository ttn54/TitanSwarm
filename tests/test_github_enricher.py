"""
TDD tests for GitHub repo enrichment (Step 2 — failing tests written before implementation).

Tests cover:
  1. fetch_github_context parses repos correctly from mocked API response
  2. fetch_github_context skips forked repos
  3. fetch_github_context returns only top 6 by stars
  4. fetch_github_context returns "" on 404 (unknown username)
  5. write_github_section appends block when no section exists yet
  6. write_github_section replaces existing block without duplicating it
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from src.core.github_enricher import fetch_github_context
from src.core.ledger import LedgerManager


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_repo(name, stars, fork=False, description="", language="Python", topics=None, readme=""):
    """Build a dict that mimics a GitHub REST API repo object."""
    return {
        "name": name,
        "stargazers_count": stars,
        "fork": fork,
        "description": description or f"{name} description",
        "language": language,
        "topics": topics or [],
        "_readme": readme,  # synthetic key used by the mock below
    }


def _mock_urlopen(repos: list, readme_map: dict = None):
    """
    Returns a context manager mock for urllib.request.urlopen that:
    - Returns repo list as JSON for the /repos endpoint
    - Returns README text for any /readme endpoint
    - Raises urllib.error.HTTPError(404) for any other endpoint
    """
    import urllib.error

    readme_map = readme_map or {}

    def side_effect(req, *args, **kwargs):
        url = req if isinstance(req, str) else req.full_url
        if "/repos?per_page" in url:
            # Return the repo list (strip synthetic _readme key)
            clean = [{k: v for k, v in r.items() if k != "_readme"} for r in repos]
            data = json.dumps(clean).encode()
        elif "/readme" in url:
            repo_name = url.split("/repos/")[1].split("/")[1]
            content = readme_map.get(repo_name, f"README for {repo_name}")
            import base64
            data = json.dumps({
                "content": base64.b64encode(content.encode()).decode(),
                "encoding": "base64",
            }).encode()
        else:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        mock_resp = MagicMock()
        mock_resp.read.return_value = data
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    return patch("urllib.request.urlopen", side_effect=side_effect)


# ─── tests ───────────────────────────────────────────────────────────────────

class TestFetchGithubContext(unittest.TestCase):

    def test_fetch_parses_repos(self):
        """Output must contain all non-fork repo names."""
        repos = [
            _make_repo("TitanStore", 12, language="Go", readme="A Raft database."),
            _make_repo("TitanSwarm", 5,  language="Python", readme="Job co-pilot."),
            _make_repo("Portfolio",  2,  language="HTML",   readme="My site."),
        ]
        with _mock_urlopen(repos, {"TitanStore": "A Raft database.", "TitanSwarm": "Job co-pilot.", "Portfolio": "My site."}):
            result = fetch_github_context("zenuser")

        self.assertIn("TitanStore", result)
        self.assertIn("TitanSwarm", result)
        self.assertIn("Portfolio",  result)

    def test_fetch_skips_forks(self):
        """Forked repos must NOT appear in the output."""
        repos = [
            _make_repo("MyOriginal", 5),
            _make_repo("SomeoneElsesFork", 100, fork=True),
        ]
        with _mock_urlopen(repos, {"MyOriginal": "Original project."}):
            result = fetch_github_context("zenuser")

        self.assertIn("MyOriginal", result)
        self.assertNotIn("SomeoneElsesFork", result)

    def test_fetch_top_6_only(self):
        """When more than 6 non-fork repos exist, only the top 6 by stars are included."""
        repos = [_make_repo(f"Repo{i}", stars=i) for i in range(10, 0, -1)]  # Repo10…Repo1
        readme_map = {f"Repo{i}": f"readme {i}" for i in range(1, 11)}
        with _mock_urlopen(repos, readme_map):
            result = fetch_github_context("zenuser")

        # Top 6 by stars: Repo10 … Repo5 should appear
        # Use "★N  |" (exact header format) to avoid substring false matches like ★1 in ★10
        for i in range(10, 4, -1):
            self.assertIn(f"★{i}  |", result)
        # Repo4 and below should NOT appear
        for i in range(4, 0, -1):
            self.assertNotIn(f"★{i}  |", result)

    def test_fetch_404_returns_empty(self):
        """A 404 response (unknown username) must return an empty string, not raise."""
        import urllib.error

        def raise_404(req, *args, **kwargs):
            url = req if isinstance(req, str) else req.full_url
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with patch("urllib.request.urlopen", side_effect=raise_404):
            result = fetch_github_context("this_user_does_not_exist_xyz")

        self.assertEqual(result, "")


class TestWriteGithubSection(unittest.TestCase):

    def _make_ledger(self, content: str) -> tuple[str, LedgerManager]:
        """Write content to a temp file and return (path, LedgerManager)."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.flush()
        tmp.close()
        mgr = LedgerManager(ledger_path=tmp.name, db_path=":memory:")
        return tmp.name, mgr

    def tearDown(self):
        # temp files are cleaned up per-test via os.unlink inside tests
        pass

    def test_write_github_section_appends(self):
        """When ledger has no GitHub section, the block should be appended."""
        path, mgr = self._make_ledger("## Imported Resume:\nJohn Doe, SFU\n")
        try:
            mgr.write_github_section("### TitanStore\nA Raft DB.")
            content = open(path, encoding="utf-8").read()
            self.assertIn("## GitHub Projects:", content)
            self.assertIn("TitanStore", content)
            # Original resume section must still be there
            self.assertIn("Imported Resume", content)
        finally:
            os.unlink(path)

    def test_write_github_section_replaces(self):
        """When ledger already has a GitHub section, it must be replaced (no duplicates)."""
        initial = (
            "## Imported Resume:\nJohn Doe\n\n"
            "## GitHub Projects:\n### OldRepo\nOld content.\n"
        )
        path, mgr = self._make_ledger(initial)
        try:
            mgr.write_github_section("### NewRepo\nNew content.")
            content = open(path, encoding="utf-8").read()
            self.assertIn("NewRepo", content)
            self.assertNotIn("OldRepo", content)
            # Section header must appear exactly once
            self.assertEqual(content.count("## GitHub Projects:"), 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
