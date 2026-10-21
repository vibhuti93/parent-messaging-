#!/usr/bin/env python3
"""
W3 Guardrail Checker for omr_dispatch_engine.

Enforces:
  1. Forbidden pattern scan (banned flags, hardcoded versions, .ogg renames, unmasked numbers, localhost)
  2. Banned Hindi vocabulary lint over templates and golden outputs (W3 & D-06)
  3. Secrets scanner (API keys, private keys, access tokens)
  4. Hindi integrity checker (scripts/check_hindi_integrity.py)
  5. State hash and tag checker (scripts/check_state_hashes.py)
  6. Invariants synchronization checker (scripts/check_invariants_sync.py)
  7. Git diff whitespace / EOF checker (git diff --check)
  8. Staged fixture-hash validation (manifest.json check once S1 completes)
  9. Test-count integrity check (monotonically non-decreasing test count)
 10. Foundation lint rules (ADR-0002, ADR-0005, ADR-0008, ADR-0009):
     - No datetime.now/utcnow or naive datetime in src/ (ADR-0005)
     - No float in core package once it exists (ADR-0002)
     - No os.environ outside settings module once it exists (ADR-0009)
     - No print( in src/ (ADR-0008)

Stage-aware skip policy (F7):
A check may SKIP only when its required stage is strictly later than docs/CURRENT_STAGE.
If the stage has been reached and its required artefact is missing, the check FAILS.
Summary line format: PASSED n / SKIPPED n / FAILED n
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Reconfigure stdout for utf-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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

# 2. Banned Hindi vocabulary per D-06 (scanned strictly in templates and golden outputs per W3)
BANNED_HINDI_TERMS = [
    "\u090b\u0923\u093e\u0924\u094d\u092e\u0915 \u0905\u0902\u0915\u0928",
    "\u092a\u094d\u0930\u0924\u093f\u0936\u0924\u0924\u093e",
    "\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915",
    "\u092a\u0942\u0930\u094d\u0923\u093e\u0902\u0915",
    "\u0914\u0938\u0924 \u092e\u093e\u0928",
]

# 3. Secrets scanner (scanned across all text files)
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"), "Private key detected"),
    (re.compile(r"EAAB[0-9A-Za-z]{20,}"), "Meta/WhatsApp Access Token detected"),
    (re.compile(r"(?:api[_-]?key|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]", re.IGNORECASE), "Potential API token assignment detected"),
]

TEXT_EXTENSIONS = {".py", ".html", ".j2", ".json", ".yaml", ".yml", ".md", ".sh", ".txt"}


def get_current_stage() -> int:
    stage_file = REPO_ROOT / "docs" / "CURRENT_STAGE"
    if not stage_file.exists():
        raise RuntimeError("docs/CURRENT_STAGE file is missing!")
    stage_text = stage_file.read_text(encoding="utf-8").strip()
    match = re.search(r"(\d+)", stage_text)
    if not match:
        raise RuntimeError(f"Cannot parse stage number from docs/CURRENT_STAGE: '{stage_text}'")
    return int(match.group(1))


# ==============================================================================
# S0 Check Implementations
# ==============================================================================

def check_forbidden_patterns_and_secrets() -> tuple[str, list[str]]:
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
                    violations.append(f"[{rel_path}] Banned user-facing Hindi term detected (D-06 rule)")

    if violations:
        return "FAILED", violations
    return "PASSED", []


def check_hindi_integrity_tool() -> tuple[str, list[str]]:
    script_path = REPO_ROOT / "scripts" / "check_hindi_integrity.py"
    if not script_path.exists():
        return "FAILED", ["scripts/check_hindi_integrity.py not found"]

    proc = subprocess.run([sys.executable, str(script_path)], cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        output_lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        err_lines = [l.strip() for l in proc.stderr.splitlines() if l.strip()]
        return "FAILED", output_lines + err_lines
    return "PASSED", []


def check_state_hashes_tool() -> tuple[str, list[str]]:
    script_path = REPO_ROOT / "scripts" / "check_state_hashes.py"
    if not script_path.exists():
        return "FAILED", ["scripts/check_state_hashes.py not found"]

    proc = subprocess.run([sys.executable, str(script_path)], cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        output_lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        err_lines = [l.strip() for l in proc.stderr.splitlines() if l.strip()]
        return "FAILED", output_lines + err_lines
    return "PASSED", []


def check_invariants_sync_tool() -> tuple[str, list[str]]:
    script_path = REPO_ROOT / "scripts" / "check_invariants_sync.py"
    if not script_path.exists():
        return "FAILED", ["scripts/check_invariants_sync.py not found"]

    proc = subprocess.run([sys.executable, str(script_path)], cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        output_lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        err_lines = [l.strip() for l in proc.stderr.splitlines() if l.strip()]
        return "FAILED", output_lines + err_lines
    return "PASSED", []


def check_git_diff_whitespace() -> tuple[str, list[str]]:
    # Run git diff --check on HEAD (or cached staged diffs), excluding frozen historical reviews
    # per hard boundary ("Do not edit the old review").
    cmd = [
        "git", "diff", "--check", "HEAD", "--", ".",
        ":(exclude)docs/reviews/stage-0-r4.md",
        ":(exclude)docs/reviews/stage-0-r5-r6.md",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        violations = [
            l.strip() for l in proc.stdout.splitlines()
            if "trailing whitespace" in l or "new blank line at EOF" in l
        ]
        if not violations:
            violations = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        return "FAILED", violations
    return "PASSED", []


# ==============================================================================
# S1+ Stage-Aware Check Implementations
# ==============================================================================

def check_fixture_hashes(current_stage: int) -> tuple[str, list[str]]:
    manifest_path = REPO_ROOT / "fixtures" / "golden" / "manifest.json"
    if current_stage < 1:
        return "SKIPPED", ["fixtures/golden/manifest.json staged for S1"]

    if not manifest_path.exists():
        return "FAILED", ["[FIXTURE GUARD] fixtures/golden/manifest.json missing in Stage S1+!"]

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

    if violations:
        return "FAILED", violations
    return "PASSED", []


def check_test_count_integrity(current_stage: int) -> tuple[str, list[str]]:
    baseline_file = REPO_ROOT / "docs" / ".test_count_baseline"
    if current_stage < 1:
        return "SKIPPED", ["docs/.test_count_baseline staged for S1"]

    if not baseline_file.exists():
        return "FAILED", ["docs/.test_count_baseline missing in Stage S1+!"]

    try:
        prev_count = int(baseline_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return "FAILED", ["docs/.test_count_baseline contains an invalid integer"]

    cmd = ["pytest", "--collect-only", "-q"]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    match = re.search(r"(\d+)\s+tests? collected", proc.stdout)
    current_count = int(match.group(1)) if match else 0

    if current_count < prev_count:
        return "FAILED", [
            f"[TEST COUNT DROP] Current test count ({current_count}) is less than baseline ({prev_count})! "
            "Tests may never be weakened, skipped, or deleted (Part C rule 6, W3 rule)."
        ]

    if current_count > prev_count:
        baseline_file.write_text(str(current_count), encoding="utf-8")
        print(f"[TEST INTEGRITY] Updated baseline test count: {prev_count} -> {current_count}")

    return "PASSED", []


def check_time_hygiene(current_stage: int) -> tuple[str, list[str]]:
    src_dir = REPO_ROOT / "src"
    if current_stage < 2:
        return "SKIPPED", ["src/ application code staged for S2"]

    if not src_dir.exists():
        return "FAILED", ["src/ directory missing in Stage S2+!"]

    py_files = [p for p in src_dir.rglob("*.py") if p.is_file() and p.name != "__init__.py"]
    if not py_files:
        return "FAILED", ["No application source files in src/ for Stage S2+!"]

    violations = []
    banned_time_patterns = [
        (re.compile(r"datetime\.(?:utcnow|today)\s*\("), "datetime.utcnow() or datetime.today() is forbidden; use injected Clock or datetime.now(timezone.utc) per ADR-0005"),
        (re.compile(r"datetime\.now\s*\(\s*\)"), "datetime.now() without explicit timezone is forbidden; use injected Clock or datetime.now(timezone.utc) per ADR-0005"),
    ]

    for p in py_files:
        rel = p.relative_to(REPO_ROOT).as_posix()
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"Could not read {rel}: {e}")
            continue

        for regex, msg in banned_time_patterns:
            if regex.search(content):
                violations.append(f"[{rel}] [TIME HYGIENE] {msg}")

    if violations:
        return "FAILED", violations
    return "PASSED", []


def check_no_float_in_core(current_stage: int) -> tuple[str, list[str]]:
    if current_stage < 2:
        return "SKIPPED", ["Core package staged for S2"]

    core_candidates = [
        REPO_ROOT / "src" / "omr_dispatch" / "core",
        REPO_ROOT / "src" / "omr_dispatch" / "diagnostics.py",
        REPO_ROOT / "src" / "omr_dispatch" / "models.py",
    ]

    core_files = []
    for cand in core_candidates:
        if cand.is_file() and cand.name != "__init__.py":
            core_files.append(cand)
        elif cand.is_dir():
            core_files.extend([p for p in cand.rglob("*.py") if p.is_file() and p.name != "__init__.py"])

    if not core_files:
        return "FAILED", ["Core package missing in Stage S2+!"]

    violations = []
    banned_float_patterns = [
        (re.compile(r":\s*float\b"), "Type annotation 'float' is forbidden in core package; use int, Fraction, or Decimal per ADR-0002"),
        (re.compile(r"->\s*float\b"), "Return type 'float' is forbidden in core package; use int, Fraction, or Decimal per ADR-0002"),
        (re.compile(r"\bfloat\s*\("), "Function call 'float()' is forbidden in core package; use int, Fraction, or Decimal per ADR-0002"),
    ]

    for p in core_files:
        rel = p.relative_to(REPO_ROOT).as_posix()
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"Could not read {rel}: {e}")
            continue

        for regex, msg in banned_float_patterns:
            if regex.search(content):
                violations.append(f"[{rel}] [CORE NUMERICS] {msg}")

    if violations:
        return "FAILED", violations
    return "PASSED", []


def check_os_environ_hygiene(current_stage: int) -> tuple[str, list[str]]:
    src_dir = REPO_ROOT / "src"
    if current_stage < 2:
        return "SKIPPED", ["src/ application code staged for S2"]

    if not src_dir.exists():
        return "FAILED", ["src/ directory missing in Stage S2+!"]

    py_files = [
        p for p in src_dir.rglob("*.py")
        if p.is_file() and p.name != "__init__.py" and p.name not in ("config.py", "settings.py")
    ]
    if not py_files:
        return "FAILED", ["No application source files in src/ for Stage S2+!"]

    violations = []
    banned_env_patterns = [
        (re.compile(r"\bos\.environ\b"), "Direct read of 'os.environ' is forbidden outside settings module; use Settings object per ADR-0009"),
        (re.compile(r"\bos\.getenv\s*\("), "Direct read of 'os.getenv()' is forbidden outside settings module; use Settings object per ADR-0009"),
    ]

    for p in py_files:
        rel = p.relative_to(REPO_ROOT).as_posix()
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"Could not read {rel}: {e}")
            continue

        for regex, msg in banned_env_patterns:
            if regex.search(content):
                violations.append(f"[{rel}] [ENV HYGIENE] {msg}")

    if violations:
        return "FAILED", violations
    return "PASSED", []


def check_no_print_in_src(current_stage: int) -> tuple[str, list[str]]:
    src_dir = REPO_ROOT / "src"
    if current_stage < 2:
        return "SKIPPED", ["src/ application code staged for S2"]

    if not src_dir.exists():
        return "FAILED", ["src/ directory missing in Stage S2+!"]

    py_files = [p for p in src_dir.rglob("*.py") if p.is_file() and p.name != "__init__.py"]
    if not py_files:
        return "FAILED", ["No application source files in src/ for Stage S2+!"]

    violations = []
    banned_print = re.compile(r"\bprint\s*\(")

    for p in py_files:
        rel = p.relative_to(REPO_ROOT).as_posix()
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"Could not read {rel}: {e}")
            continue

        if banned_print.search(content):
            violations.append(
                f"[{rel}] [LOGGING HYGIENE] Raw 'print(' statement found. "
                "Use structured logger with automatic redaction per ADR-0008."
            )

    if violations:
        return "FAILED", violations
    return "PASSED", []


def main() -> int:
    current_stage = get_current_stage()
    print(f"=== Running Guardrails (Current Stage: S{current_stage}) ===")

    checks: list[tuple[str, tuple[str, list[str]]]] = [
        ("Forbidden Patterns & Secrets", check_forbidden_patterns_and_secrets()),
        ("Hindi Integrity Check", check_hindi_integrity_tool()),
        ("State Hashes & Tags Check", check_state_hashes_tool()),
        ("Invariants Synchronization Check", check_invariants_sync_tool()),
        ("Git Diff & Whitespace Check", check_git_diff_whitespace()),
        ("Fixture Hash Validation", check_fixture_hashes(current_stage)),
        ("Test Count Integrity Check", check_test_count_integrity(current_stage)),
        ("Time Hygiene Check", check_time_hygiene(current_stage)),
        ("Core Numerics Check", check_no_float_in_core(current_stage)),
        ("Environment Hygiene Check", check_os_environ_hygiene(current_stage)),
        ("Logging Hygiene Check", check_no_print_in_src(current_stage)),
    ]

    passed_count = 0
    skipped_count = 0
    failed_count = 0
    all_failures: list[str] = []

    for name, (status, msgs) in checks:
        if status == "PASSED":
            passed_count += 1
            print(f"  [PASS] {name}")
        elif status == "SKIPPED":
            skipped_count += 1
            skip_msg = f" ({msgs[0]})" if msgs else ""
            print(f"  [SKIP] {name}{skip_msg}")
        elif status == "FAILED":
            failed_count += 1
            print(f"  [FAIL] {name}")
            for m in msgs:
                all_failures.append(f"[{name}] {m}")

    print("\n------------------------------------------------------------")
    print(f"PASSED {passed_count} / SKIPPED {skipped_count} / FAILED {failed_count}")
    print("------------------------------------------------------------")

    if failed_count > 0:
        print("\nFailures:")
        for f in all_failures:
            print(f"  - {f}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())