"""
Utility for safely updating individual keys in a .env file.

Uses a targeted line-by-line upsert strategy:
  - Active key  (KEY=value)      → replaced in-place
  - Commented key (# KEY=value)  → uncommented and updated in-place
  - Missing key                  → appended at end of file

All other content (comments, blank lines, unrelated keys) is preserved exactly.
"""
import os
import re


def upsert_env_vars(env_path: str, updates: dict) -> None:
    """
    Update specific keys in a .env file without touching any other content.

    For each key in `updates`:
      - If the key exists (active): replace the value on that line.
      - If the key is commented out (# KEY=...): uncomment and set the value.
      - If the key doesn't exist anywhere: append KEY=value at the end of the file.

    Preserves all comments, blank lines, and unrelated keys exactly.
    """
    if not updates:
        return

    # Read existing lines (or start empty if the file doesn't exist yet)
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = []

    remaining = dict(updates)  # keys not yet written

    new_lines = []
    for line in lines:
        matched_key = None
        for key in list(remaining):
            # Match an active line: KEY= or KEY =
            active_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
            # Match a commented line: # KEY= or #KEY= or # KEY =
            commented_re = re.compile(rf"^\s*#\s*{re.escape(key)}\s*=")
            if active_re.match(line) or commented_re.match(line):
                matched_key = key
                break
        if matched_key is not None:
            new_lines.append(f"{matched_key}={remaining.pop(matched_key)}\n")
        else:
            new_lines.append(line)

    # Append any keys that were never found in the file
    for key, value in remaining.items():
        # Ensure there's a trailing newline before appending
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def read_env_var(env_path: str, key: str, default: str = "") -> str:
    """Return the value of `key` from the .env file, or `default` if not found."""
    if not os.path.exists(env_path):
        return default
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            k, _, v = stripped.partition("=")
            if k.strip() == key:
                return v.strip()
    return default
