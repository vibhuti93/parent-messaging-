#!/usr/bin/env python3
"""
Integrity check: Enforce synchronization of Global Invariants 1–17
between root AGENTS.md and docs/prompt_pack/00_global_invariants.md.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENTS_PATH = REPO_ROOT / "AGENTS.md"
PROMPT_INVARIANTS_PATH = REPO_ROOT / "docs" / "prompt_pack" / "00_global_invariants.md"


def extract_invariants(path: Path) -> dict[int, str]:
    if not path.exists():
        print(f"[INVARIANTS SYNC ERROR] File missing: {path}")
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    invariants = {}
    pattern = re.compile(r"^(\d+)\.\s+(.*)$", re.MULTILINE)
    for match in pattern.finditer(text):
        num = int(match.group(1))
        content = match.group(2).strip()
        invariants[num] = content
    return invariants


def main() -> int:
    agents_inv = extract_invariants(AGENTS_PATH)
    prompt_inv = extract_invariants(PROMPT_INVARIANTS_PATH)

    all_keys = sorted(set(agents_inv.keys()) | set(prompt_inv.keys()))
    if not all_keys:
        print("[INVARIANTS SYNC ERROR] No invariants found in files!")
        return 1

    mismatches = []
    for k in all_keys:
        val_agent = agents_inv.get(k)
        val_prompt = prompt_inv.get(k)
        if val_agent != val_prompt:
            mismatches.append(f"Invariant {k} mismatch:\n  AGENTS.md:       {val_agent}\n  00_global_inv:   {val_prompt}")

    if mismatches:
        print(f"[INVARIANTS SYNC FAIL] Found {len(mismatches)} mismatch(es):")
        for m in mismatches:
            print(f"  - {m}")
        return 1

    print(f"[INVARIANTS SYNC PASS] All {len(all_keys)} global invariants synchronized between AGENTS.md and 00_global_invariants.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
