#!/usr/bin/env python3
"""
W3 Guardrail Checker for omr_dispatch_engine
Enforces:
  1. Forbidden pattern scan (banned flags, hardcoded versions, .ogg renames, unmasked numbers, localhost)
  2. Banned Hindi vocabulary lint over templates and golden outputs (W3 & D-06)
  3. Secrets scanner (API keys, private keys, access tokens)
  4. Staged fixture-hash validation (manifest.json check once S1 completes)
  5. Test-count integrity check (monotonically non-decreasing test count)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files and directories to ignore entirely
EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "venv", ".venv", "node_modules"}

# 1. Forbidden code patterns (scanned in src/ and templates/)
FORBIDDEN_CODE_PATTERNS = [
    (re.compile(r"voice\s*:\s*true", re.IGNORECASE), "Banned property 'voice: true' found (W3 rule)"),
    (re.compile(r"['\"]v\d+\.\d+['\"]"), "Hardcoded Graph API version string found; must be resolved from verified config (W3 rule)"),
    (re.compile(r"\.rename\(.*\.ogg['\"]\)", re.IGNORECASE), "Direct file rename to .ogg detected; audio must be transcoded via FFmpeg (W3 rule)"),
    (re.compile(r"shutil\.move\(.*\.ogg['\"]\)", re.IGNORECASE), "Direct file move to .ogg detected; audio must be transcoded via FFmpeg (W3 rule)"),
    (re.compile(r"(?:print|logger\.\w+)\(.*[6-9]\d{9}.*\)"), "Potential unmasked 10-digit Indian mobile number in logging/print statement (Part C rule 10)"),
]

# Production files where localhost is strictly forbidden
FORBIDDEN_LOCALHOST_FILES = [
    re.compile(r"^src/.*\.py$"),
    re.compile(r"^\.env\.production$"),
]

# 2. Banned Hindi vocabulary per D-06 (scanned ONLY in templates and golden outputs per W3)
BANNED_HINDI_TERMS = [
    "ऋणात्मक अंकन",
    "प्रतिशतता",
    "प्राप्तांक",
    "पूर्णांक",
    "औसत मान",
]

# 3. Secrets scanner (scanned across all text files)
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"), "Private key detected"),
    (re.compile(r"EAAB[0-9A-Za-z]{20,}"), "Meta/WhatsApp Access Token detected"),
    (re.compile(r"(?:api[_-]?key|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]", re.IGNORECASE), "Potential API token assignment detected"),
]

TEXT_EXTENSIONS = {".py", ".html", ".j2", ".json", ".yaml", ".yml", ".md", ".sh", ".txt"}


def check_forbidden_patterns_and_secrets() -> list[str]:
    violations = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue

        rel_path = path.relative_to(REPO_ROOT).as_posix()
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            violations.append(f"Could not read {rel_path}: {e}")
            continue

        # A. Secrets scan (all text files)
        for regex, desc in SECRET_PATTERNS:
            if regex.search(content):
                violations.append(f"[{rel_path}] SECRET DETECTED: {desc}")

        # B. Localhost scan (production source files only)
        for rule in FORBIDDEN_LOCALHOST_FILES:
            if rule.match(rel_path) and "localhost" in content.lower():
                violations.append(f"[{rel_path}] 'localhost' is forbidden in production source files (W3 rule)")

        # C. Forbidden code patterns (only in src/ and templates/, excluding specs and scripts)
        if rel_path.startswith(("src/", "templates/")):
            for regex, desc in FORBIDDEN_CODE_PATTERNS:
                if regex.search(content):
                    violations.append(f"[{rel_path}] {desc}")

        # D. Banned Hindi vocabulary (W3: strictly over templates and golden outputs, not specs or scripts)
        is_hindi_target = (
            rel_path.startswith("templates/")
            or rel_path.startswith("src/omr_dispatch/hindi_templates")
            or (rel_path.startswith("fixtures/golden/") and rel_path.endswith((".json", ".txt", ".html")))
        )
        if is_hindi_target:
            for term in BANNED_HINDI_TERMS:
                if term in content:
                    violations.append(f"[{rel_path}] Banned user-facing Hindi term '{term}' detected (D-06 rule)")

    return violations


def check_fixture_hashes() -> list[str]:
    """W3 Fixture hash check: Staged for activation once S1 creates manifest.json."""
    manifest_path = REPO_ROOT / "fixtures" / "golden" / "manifest.json"
    if not manifest_path.exists():
        print("[FIXTURE GUARD] fixtures/golden/manifest.json not present yet (S1 pending) -> SKIPPED")
        return []

    violations = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files_map = manifest.get("files", {})
        for rel_file, expected_hash in files_map.items():
            target = REPO_ROOT / rel_file
            if not target.exists():
                violations.append(f"[FIXTURE TAMPERING] Frozen fixture missing: {rel_file}")
                continue
            actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                violations.append(
                    f"[FIXTURE TAMPERING] Hash mismatch on {rel_file}: expected {expected_hash}, got {actual_hash}"
                )
    except Exception as e:
        violations.append(f"Failed to validate manifest.json: {e}")

    return violations


def check_test_count_integrity() -> list[str]:
    """Ensure test counts never decrease (W3 rule)."""
    baseline_file = REPO_ROOT / "docs" / ".test_count_baseline"
    if not baseline_file.exists():
        print("[TEST INTEGRITY] docs/.test_count_baseline not found -> SKIPPED (staged for S1)")
        return []

    try:
        prev_count = int(baseline_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return ["docs/.test_count_baseline contains an invalid integer"]

    cmd = ["pytest", "--collect-only", "-q"]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    match = re.search(r"(\d+)\s+tests? collected", proc.stdout)
    current_count = int(match.group(1)) if match else 0

    if current_count < prev_count:
        return [
            f"[TEST COUNT DROP] Current test count ({current_count}) is less than baseline ({prev_count})! "
            "Tests may never be weakened, skipped, or deleted (Part C rule 6, W3 rule)."
        ]

    if current_count > prev_count:
        baseline_file.write_text(str(current_count), encoding="utf-8")
        print(f"[TEST INTEGRITY] Updated baseline test count: {prev_count} -> {current_count}")

    return []


def main():
    all_violations = []

    print("=== Running W3 Guardrails ===")
    violations = check_forbidden_patterns_and_secrets()
    if violations:
        all_violations.extend(violations)

    hash_violations = check_fixture_hashes()
    if hash_violations:
        all_violations.extend(hash_violations)

    test_violations = check_test_count_integrity()
    if test_violations:
        all_violations.extend(test_violations)

    if all_violations:
        print("\n[GUARDRAIL FAILURE] Found violations:")
        for v in all_violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[GUARDRAIL PASS] All pre-commit guardrails satisfied.")
    sys.exit(0)


if __name__ == "__main__":
    main()