#!/usr/bin/env python3
"""
Hindi integrity, encoding, and template consistency checker.
Part of Stage S0 guardrails for omr_dispatch_engine.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import unicodedata

# Reconfigure stdout for utf-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
CATALOG_PATH = os.path.join(DOCS_DIR, "message_catalog.md")
TEMPLATES_DIR = os.path.join(DOCS_DIR, "templates")
FIXTURES_GOLDEN_DIR = os.path.join(ROOT_DIR, "fixtures", "golden")

# D-06 Banned terms written strictly as \u escapes, never literal Hindi
BANNED_TERMS = [
    "\u090b\u0923\u093e\u0924\u094d\u092e\u0915 \u0905\u0902\u0915\u0928",  # rinatmak ankan
    "\u092a\u094d\u0930\u0924\u093f\u0936\u0924\u0924\u093e",              # pratishatta
    "\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915",          # praptank
    "\u092a\u0942\u0930\u094d\u0923\u093e\u0902\u0915",                      # purnank
    "\u0914\u0938\u0924 \u092e\u093e\u0928",                                  # ausat maan
]

# Devanagari digits U+0966 to U+096F
DEVANAGARI_DIGITS = [chr(cp) for cp in range(0x0966, 0x0970)]

# Files exempt from Devanagari digit and orphan mark check because they explicitly
# document Unicode / font rendering rules or review findings.
EXEMPT_TECHNICAL_FILES = {
    os.path.normpath(os.path.join(DOCS_DIR, "adr", "ADR-0010-text-and-unicode.md")),
    os.path.normpath(os.path.join(DOCS_DIR, "prompt_pack", "S6.md")),
    os.path.normpath(os.path.join(DOCS_DIR, "DECISIONS_OPEN.md")),
}


def get_devanagari_combining_marks() -> set[str]:
    combining = set()
    for cp in range(0x0900, 0x0980):
        ch = chr(cp)
        cat = unicodedata.category(ch)
        if cat in ("Mn", "Mc"):
            combining.add(ch)
    return combining


def check_encoding_and_structure(errors: list[str]) -> None:
    combining_marks = get_devanagari_combining_marks()
    md_files = glob.glob(os.path.join(DOCS_DIR, "**", "*.md"), recursive=True)

    for fpath in md_files:
        norm_path = os.path.normpath(fpath)
        rel_path = os.path.relpath(fpath, ROOT_DIR)

        # 1. Strict UTF-8 validation
        try:
            with open(fpath, "rb") as fp:
                raw_bytes = fp.read()
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"[UTF-8 DECODE ERROR] {rel_path}: {exc}")
            continue

        # 2. Check for U+FFFD (Replacement character)
        if "\ufffd" in text:
            errors.append(f"[U+FFFD REPLACEMENT CHAR] {rel_path} contains U+FFFD")

        # 3. Check NFC normalization
        if not unicodedata.is_normalized("NFC", text):
            errors.append(f"[NON-NFC NORMALIZATION] {rel_path} is not in Unicode NFC form")

        # Determine if file is exempt from Devanagari digits and orphan mark policy discussion
        is_exempt = norm_path in EXEMPT_TECHNICAL_FILES or os.path.normpath(
            os.path.join(DOCS_DIR, "reviews")
        ) in norm_path

        if is_exempt:
            continue

        # 4. Check orphan Devanagari combining marks and Devanagari digits
        lines = text.splitlines()
        for line_no, line in enumerate(lines, 1):
            # Check digits
            for d in DEVANAGARI_DIGITS:
                if d in line:
                    errors.append(
                        f"[DEVANAGARI DIGIT] {rel_path}:{line_no} contains Devanagari numeral '{d}'"
                    )

            # Check orphan combining marks
            for i, ch in enumerate(line):
                if ch in combining_marks:
                    if i == 0:
                        errors.append(
                            f"[ORPHAN COMBINING MARK] {rel_path}:{line_no} mark at line start"
                        )
                    elif line[i - 1].isspace():
                        errors.append(
                            f"[ORPHAN COMBINING MARK] {rel_path}:{line_no} mark follows whitespace"
                        )
                    elif ord(line[i - 1]) < 128:
                        errors.append(
                            f"[ORPHAN COMBINING MARK] {rel_path}:{line_no} mark follows ASCII char '{line[i - 1]}'"
                        )


def check_banned_terms(errors: list[str]) -> None:
    # 1. In docs/message_catalog.md, banned terms may only appear on the single normative rule line
    if not os.path.exists(CATALOG_PATH):
        errors.append(f"[FILE NOT FOUND] {CATALOG_PATH}")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as fp:
        catalog_lines = fp.readlines()

    normative_rule_line = None
    for idx, line in enumerate(catalog_lines, 1):
        if "Vocabulary Compliance (D-06):" in line:
            normative_rule_line = idx
            break

    if normative_rule_line is None:
        errors.append("[CATALOG RULE MISSING] Could not find 'Vocabulary Compliance (D-06):' line in message_catalog.md")

    for idx, line in enumerate(catalog_lines, 1):
        if idx == normative_rule_line:
            continue
        for term in BANNED_TERMS:
            if term in line:
                term_escaped = term.encode("unicode_escape").decode("ascii")
                errors.append(
                    f"[BANNED TERM] docs/message_catalog.md:{idx} contains banned term ({term_escaped}) outside normative rule line"
                )

    # 2. In docs/templates/*.md, banned terms must never appear
    template_files = glob.glob(os.path.join(TEMPLATES_DIR, "*.md"))
    for tpath in template_files:
        rel_path = os.path.relpath(tpath, ROOT_DIR)
        with open(tpath, "r", encoding="utf-8") as fp:
            t_lines = fp.readlines()
        for idx, line in enumerate(t_lines, 1):
            for term in BANNED_TERMS:
                if term in line:
                    term_escaped = term.encode("unicode_escape").decode("ascii")
                    errors.append(
                        f"[BANNED TERM] {rel_path}:{idx} contains banned term ({term_escaped})"
                    )


def check_greeting_consistency(errors: list[str]) -> None:
    if not os.path.exists(CATALOG_PATH):
        errors.append(f"[FILE NOT FOUND] {CATALOG_PATH}")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as fp:
        catalog_content = fp.read()

    # Extract normative greeting from catalog rules section
    # Rule 1: Every message begins with a fixed leading greeting: `"प्रिय अभिभावक, "`
    m = re.search(
        r"Fixed Leading Greeting:\*\*\s*Every message begins with a fixed leading greeting:\s*`?\"([^\"]+)\"`?",
        catalog_content,
    )
    if not m:
        errors.append("[GREETING EXTRACTION] Could not extract fixed leading greeting from message_catalog.md rules")
        return

    normative_greeting = m.group(1)
    normative_greeting_bytes = normative_greeting.encode("utf-8")

    # Check templates in docs/templates/*.md
    # guardian_otp_challenge.md is exempt per Rule 8 (Authentication category)
    template_files = glob.glob(os.path.join(TEMPLATES_DIR, "*.md"))
    for tpath in template_files:
        filename = os.path.basename(tpath)
        if filename == "guardian_otp_challenge.md":
            continue

        rel_path = os.path.relpath(tpath, ROOT_DIR)
        with open(tpath, "r", encoding="utf-8") as fp:
            content = fp.read()

        # Find raw template bodies inside ```text ... ``` blocks
        text_blocks = re.findall(r"```text\s*\n(.*?)\n```", content, re.DOTALL)
        if not text_blocks:
            errors.append(f"[TEMPLATE FORMAT] {rel_path} has no ```text``` template code block")
            continue

        for block_idx, block in enumerate(text_blocks, 1):
            block_lines = [b.strip() for b in block.strip().splitlines() if b.strip()]
            if not block_lines:
                continue
            first_line = block_lines[0]
            first_line_bytes = first_line.encode("utf-8")
            if not first_line_bytes.startswith(normative_greeting_bytes):
                errors.append(
                    f"[GREETING MISMATCH] {rel_path} block {block_idx} does not start with normative greeting byte-for-byte"
                )

    # Check templates defined in docs/message_catalog.md
    # Sections 1 to 5 are academic/attendance templates; section 6 is GUARDIAN_OTP_CHALLENGE
    sections = re.split(r"\n(?=##\s+\d+\.\s+)", catalog_content)
    for section in sections:
        # Check if this is an academic/attendance section
        header_match = re.match(r"##\s+(\d+)\.\s+`?([A-Z_]+)`?", section.strip())
        if not header_match:
            continue
        sec_num, sec_name = header_match.groups()
        if sec_name == "GUARDIAN_OTP_CHALLENGE":
            continue

        # Extract code blocks
        text_blocks = re.findall(r"```text\s*\n(.*?)\n```", section, re.DOTALL)
        for block_idx, block in enumerate(text_blocks, 1):
            block_lines = [b.strip() for b in block.strip().splitlines() if b.strip()]
            if not block_lines:
                continue
            first_line = block_lines[0]
            first_line_bytes = first_line.encode("utf-8")
            if not first_line_bytes.startswith(normative_greeting_bytes):
                errors.append(
                    f"[GREETING MISMATCH] docs/message_catalog.md ({sec_name}) block {block_idx} does not start with normative greeting byte-for-byte"
                )


def scan_decoded_json_string(
    val: str,
    path_str: str,
    rel_path: str,
    errors: list[str],
    combining_marks: set[str],
) -> None:
    # 1. NFC normalization check on decoded string
    if not unicodedata.is_normalized("NFC", val):
        errors.append(f"[NON-NFC NORMALIZATION] {rel_path} at {path_str} is not in Unicode NFC form")

    # 2. Banned terms check on decoded string
    for term in BANNED_TERMS:
        if term in val:
            term_escaped = term.encode("unicode_escape").decode("ascii")
            errors.append(
                f"[BANNED TERM] {rel_path} at {path_str} contains banned Hindi term ({term_escaped})"
            )

    # 3. Devanagari digits check on decoded string
    for d in DEVANAGARI_DIGITS:
        if d in val:
            errors.append(
                f"[DEVANAGARI DIGIT] {rel_path} at {path_str} contains Devanagari numeral '{d}'"
            )

    # 4. Orphan combining marks on decoded string
    for i, ch in enumerate(val):
        if ch in combining_marks:
            if i == 0:
                errors.append(
                    f"[ORPHAN COMBINING MARK] {rel_path} at {path_str} mark at string start"
                )
            elif val[i - 1].isspace():
                errors.append(
                    f"[ORPHAN COMBINING MARK] {rel_path} at {path_str} mark follows whitespace"
                )
            elif ord(val[i - 1]) < 128:
                errors.append(
                    f"[ORPHAN COMBINING MARK] {rel_path} at {path_str} mark follows ASCII char '{val[i - 1]}'"
                )


def traverse_json_data(
    data: object,
    path: str,
    rel_path: str,
    errors: list[str],
    combining_marks: set[str],
) -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            scan_decoded_json_string(k, f"{path}.key('{k}')", rel_path, errors, combining_marks)
            traverse_json_data(v, f"{path}.{k}", rel_path, errors, combining_marks)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            traverse_json_data(item, f"{path}[{i}]", rel_path, errors, combining_marks)
    elif isinstance(data, str):
        scan_decoded_json_string(data, path, rel_path, errors, combining_marks)


def check_golden_fixtures_hindi_integrity(errors: list[str]) -> None:
    combining_marks = get_devanagari_combining_marks()
    json_files = glob.glob(os.path.join(FIXTURES_GOLDEN_DIR, "*.json"))

    for fpath in sorted(json_files):
        rel_path = os.path.relpath(fpath, ROOT_DIR)

        # 1. Strict UTF-8 validation
        try:
            with open(fpath, "rb") as fp:
                raw_bytes = fp.read()
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"[UTF-8 DECODE ERROR] {rel_path}: {exc}")
            continue

        # 2. Check for U+FFFD (Replacement character)
        if "\ufffd" in text:
            errors.append(f"[U+FFFD REPLACEMENT CHAR] {rel_path} contains U+FFFD")

        # 3. Check NFC normalization on raw file text
        if not unicodedata.is_normalized("NFC", text):
            errors.append(f"[NON-NFC NORMALIZATION] {rel_path} is not in Unicode NFC form")

        # 4. Check for banned terms (D-06) on raw text
        for term in BANNED_TERMS:
            if term in text:
                term_escaped = term.encode("unicode_escape").decode("ascii")
                errors.append(
                    f"[BANNED TERM] {rel_path} contains banned Hindi term ({term_escaped})"
                )

        # 5. Check orphan Devanagari combining marks and Devanagari digits on raw text
        lines = text.splitlines()
        for line_no, line in enumerate(lines, 1):
            for d in DEVANAGARI_DIGITS:
                if d in line:
                    errors.append(
                        f"[DEVANAGARI DIGIT] {rel_path}:{line_no} contains Devanagari numeral '{d}'"
                    )

            for i, ch in enumerate(line):
                if ch in combining_marks:
                    if i == 0:
                        errors.append(
                            f"[ORPHAN COMBINING MARK] {rel_path}:{line_no} mark at line start"
                        )
                    elif line[i - 1].isspace():
                        errors.append(
                            f"[ORPHAN COMBINING MARK] {rel_path}:{line_no} mark follows whitespace"
                        )
                    elif ord(line[i - 1]) < 128:
                        errors.append(
                            f"[ORPHAN COMBINING MARK] {rel_path}:{line_no} mark follows ASCII char '{line[i - 1]}'"
                        )

        # 6. Parse JSON and scan decoded keys and string values
        try:
            parsed = json.loads(text)
        except Exception as exc:
            errors.append(f"[JSON PARSE ERROR] {rel_path}: {exc}")
            continue

        traverse_json_data(parsed, "$", rel_path, errors, combining_marks)


def main() -> int:
    errors: list[str] = []

    check_encoding_and_structure(errors)
    check_banned_terms(errors)
    check_greeting_consistency(errors)
    check_golden_fixtures_hindi_integrity(errors)

    if errors:
        print(f"[FAIL] Hindi integrity check failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[HINDI INTEGRITY PASS] All docs and golden fixtures UTF-8/NFC clean, zero orphan marks, zero unapproved banned terms, greetings consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
