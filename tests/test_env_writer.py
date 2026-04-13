"""
TDD tests for the .env upsert utility (tests written BEFORE implementation).

Covers:
  1. upsert replaces an active key's value in-place
  2. upsert uncomments a commented-out key and sets the value
  3. upsert appends a key that doesn't exist
  4. upsert preserves all other lines exactly (GEMINI_API_KEY unchanged)
  5. upsert handles multiple keys in a single call
  6. read_env_var returns the value of an existing key
  7. read_env_var returns the default when the key is absent
"""
import os
import tempfile
import unittest

from src.core.env_writer import upsert_env_vars, read_env_var


def _write_env(content: str) -> str:
    """Write content to a temp .env file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".env", delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return tmp.name


class TestUpsertEnvVars(unittest.TestCase):

    def tearDown(self):
        # Each test cleans up its own temp file via os.unlink inside the test.
        pass

    def test_replaces_active_key(self):
        """An existing active key must have its value replaced in-place."""
        path = _write_env(
            "# TitanSwarm .env\n"
            "GEMINI_API_KEY=abc123\n"
            "SCRAPER_ROLES=Software Engineer Intern\n"
            "SCRAPER_LOCATIONS=Vancouver, BC\n"
        )
        try:
            upsert_env_vars(path, {"SCRAPER_ROLES": "Backend Developer Intern|Frontend Developer Intern"})
            lines = open(path).readlines()
            # Updated line must contain the new value
            roles_lines = [l for l in lines if l.startswith("SCRAPER_ROLES=")]
            self.assertEqual(len(roles_lines), 1)
            self.assertIn("Backend Developer Intern|Frontend Developer Intern", roles_lines[0])
            # Total line count must not change (replaced in-place, not appended)
            self.assertEqual(len(lines), 4)
        finally:
            os.unlink(path)

    def test_uncomments_commented_key(self):
        """A commented-out key (# KEY=...) must be uncommented and its value set."""
        path = _write_env(
            "GEMINI_API_KEY=abc123\n"
            "# SCRAPER_ROLES=Software Engineer\n"
            "SCRAPER_LOCATIONS=Vancouver, BC\n"
        )
        try:
            upsert_env_vars(path, {"SCRAPER_ROLES": "ML Engineer|Data Engineer"})
            content = open(path).read()
            self.assertIn("SCRAPER_ROLES=ML Engineer|Data Engineer", content)
            # Must not still be commented out
            self.assertNotIn("# SCRAPER_ROLES=", content)
        finally:
            os.unlink(path)

    def test_appends_missing_key(self):
        """A key that doesn't exist anywhere must be appended at the end of the file."""
        path = _write_env(
            "GEMINI_API_KEY=abc123\n"
        )
        try:
            upsert_env_vars(path, {"SCRAPER_ROLES": "Software Engineer Intern"})
            lines = open(path).readlines()
            last_line = lines[-1].strip()
            self.assertEqual(last_line, "SCRAPER_ROLES=Software Engineer Intern")
            # Original line still intact
            self.assertTrue(any("GEMINI_API_KEY=abc123" in l for l in lines))
        finally:
            os.unlink(path)

    def test_preserves_unrelated_keys_exactly(self):
        """Keys NOT in the update dict must be byte-for-byte identical after the call."""
        original = (
            "# TitanSwarm environment variables\n"
            "AI_PROVIDER=gemini\n"
            "GEMINI_API_KEY=super_secret_key_xyz\n"
            "# OPENAI_API_KEY=sk-...\n"
            "SCRAPER_INTERVAL_HOURS=12\n"
        )
        path = _write_env(original)
        try:
            upsert_env_vars(path, {"SCRAPER_INTERVAL_HOURS": "6"})
            content = open(path).read()
            # The API key line must be unchanged
            self.assertIn("GEMINI_API_KEY=super_secret_key_xyz", content)
            self.assertIn("AI_PROVIDER=gemini", content)
            self.assertIn("# OPENAI_API_KEY=sk-...", content)
            self.assertIn("# TitanSwarm environment variables", content)
        finally:
            os.unlink(path)

    def test_multiple_keys_in_one_call(self):
        """All keys in the updates dict must be written correctly in one call."""
        path = _write_env(
            "GEMINI_API_KEY=abc\n"
            "SCRAPER_ROLES=Old Role\n"
            "SCRAPER_LOCATIONS=Old City\n"
            "SCRAPER_INTERVAL_HOURS=12\n"
        )
        try:
            upsert_env_vars(path, {
                "SCRAPER_ROLES":          "Software Engineer Intern|Backend Developer",
                "SCRAPER_LOCATIONS":      "Vancouver, BC|Remote Canada",
                "SCRAPER_INTERVAL_HOURS": "8",
                "SCRAPER_RESULTS_WANTED": "30",  # new key — will be appended
            })
            content = open(path).read()
            self.assertIn("SCRAPER_ROLES=Software Engineer Intern|Backend Developer", content)
            self.assertIn("SCRAPER_LOCATIONS=Vancouver, BC|Remote Canada", content)
            self.assertIn("SCRAPER_INTERVAL_HOURS=8", content)
            self.assertIn("SCRAPER_RESULTS_WANTED=30", content)
            self.assertIn("GEMINI_API_KEY=abc", content)
        finally:
            os.unlink(path)


class TestReadEnvVar(unittest.TestCase):

    def test_reads_existing_key(self):
        """Should return the value of a key that exists in the file."""
        path = _write_env("GEMINI_API_KEY=abc123\nSCRAPER_ROLES=My Role\n")
        try:
            result = read_env_var(path, "SCRAPER_ROLES")
            self.assertEqual(result, "My Role")
        finally:
            os.unlink(path)

    def test_returns_default_for_missing_key(self):
        """Should return the default string when the key is not in the file."""
        path = _write_env("GEMINI_API_KEY=abc123\n")
        try:
            result = read_env_var(path, "SCRAPER_ROLES", default="Software Engineer Intern")
            self.assertEqual(result, "Software Engineer Intern")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
