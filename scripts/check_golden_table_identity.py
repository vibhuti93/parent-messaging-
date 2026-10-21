#!/usr/bin/env python3
"""
Verify that the 20-student OMR golden table rows in docs/prompt_pack/S1.md
(all STU_* lines, batch summary, and subject labels) are byte-identical
to the stage-0-r4 release, excluding the line-9 roster description edit.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
S1_PATH = os.path.join(ROOT_DIR, "docs", "prompt_pack", "S1.md")


def main() -> int:
    try:
        r4_bytes = subprocess.check_output(
            ["git", "show", "stage-0-r4:docs/prompt_pack/S1.md"],
            cwd=ROOT_DIR,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[FAIL] Could not read docs/prompt_pack/S1.md at tag stage-0-r4: {exc}")
        return 1

    r4_lines = r4_bytes.decode("utf-8").splitlines()

    if not os.path.exists(S1_PATH):
        print(f"[FAIL] Current file not found: {S1_PATH}")
        return 1

    with open(S1_PATH, "r", encoding="utf-8") as fp:
        current_lines = fp.read().splitlines()

    # Lines 10 to 40 inclusive (0-indexed 9 to 40) comprise the 20-student OMR golden table rows
    r4_golden_rows = r4_lines[9:40]
    current_golden_rows = current_lines[9:40]

    if len(r4_golden_rows) != len(current_golden_rows):
        print(
            f"[FAIL] Line count mismatch: stage-0-r4 has {len(r4_golden_rows)} lines, current has {len(current_golden_rows)} lines."
        )
        return 1

    mismatches = []
    for line_idx, (r4_l, cur_l) in enumerate(zip(r4_golden_rows, current_golden_rows), start=10):
        if r4_l != cur_l:
            mismatches.append((line_idx, r4_l, cur_l))

    if mismatches:
        print(f"[FAIL] Golden table row mismatch against stage-0-r4 ({len(mismatches)} difference(s)):")
        for line_idx, r4_l, cur_l in mismatches:
            print(f"  Line {line_idx}:")
            print(f"    stage-0-r4: {r4_l}")
            print(f"    current:    {cur_l}")
        return 1

    print(
        f"[GOLDEN TABLE PASS] All {len(current_golden_rows)} OMR golden table rows (lines 10-40) in S1.md are byte-identical to stage-0-r4."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
