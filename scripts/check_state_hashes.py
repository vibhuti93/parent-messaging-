#!/usr/bin/env python3
"""
Integrity check: Validate all git commit hashes and associated tags in docs/STATE.md.
Every full 40-char hexadecimal commit hash in STATE.md must resolve in git,
and every tag named adjacent to a hash must resolve to that exact commit.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / "docs" / "STATE.md"


def git_commit_exists(commit_hash: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "cat-file", "-e", f"{commit_hash}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0
    except Exception:
        return False


def git_resolve_tag(tag_name: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", f"refs/tags/{tag_name}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
        # Fallback to direct rev-parse
        proc2 = subprocess.run(
            ["git", "rev-parse", f"{tag_name}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if proc2.returncode == 0:
            return proc2.stdout.strip()
        return None
    except Exception:
        return None


def main() -> int:
    if not STATE_FILE.exists():
        print(f"[STATE HASH ERROR] {STATE_FILE} does not exist.")
        return 1

    content = STATE_FILE.read_text(encoding="utf-8")
    violations = []

    # 1. Verify every 40-char hexadecimal hash in STATE.md resolves in git
    hashes_found = set(re.findall(r"\b[0-9a-f]{40}\b", content))
    if not hashes_found:
        print("[STATE HASH WARN] No 40-character commit hashes found in docs/STATE.md.")
    else:
        for commit_hash in sorted(hashes_found):
            if not git_commit_exists(commit_hash):
                violations.append(f"Commit hash {commit_hash} found in docs/STATE.md does not resolve in git repository.")

    # 2. Verify every tag named adjacent to a hash points to that exact commit
    # Patterns like: `stage-0-r6` (commit: `8f59ebd...`) or `stage-0-r6` (Commit hash `8f59ebd...`)
    tag_hash_pattern = re.compile(
        r"`([a-zA-Z0-9_\-]+)`\s*\([^`\n]*?(?:commit|Commit hash)[:\s]+`?([0-9a-f]{40})`?",
        re.IGNORECASE,
    )
    for match in tag_hash_pattern.finditer(content):
        tag_name = match.group(1)
        expected_hash = match.group(2)

        resolved_commit = git_resolve_tag(tag_name)
        if not resolved_commit:
            violations.append(f"Tag '{tag_name}' named next to hash {expected_hash} could not be resolved in git.")
        elif resolved_commit != expected_hash:
            violations.append(
                f"Tag '{tag_name}' mismatch: points to {resolved_commit}, but docs/STATE.md specifies {expected_hash}."
            )

    if violations:
        print(f"[STATE HASH FAIL] Found {len(violations)} hash/tag hygiene violation(s):")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        f"[STATE HASH PASS] All {len(hashes_found)} commit hash(es) and tagged references in docs/STATE.md verified successfully."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
