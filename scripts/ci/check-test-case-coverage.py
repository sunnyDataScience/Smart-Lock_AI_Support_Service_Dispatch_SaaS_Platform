#!/usr/bin/env python3
"""
scripts/ci/check-test-case-coverage.py
--------------------------------------
Validate test case registry against coverage rules. Exit 1 on errors (in strict mode).

Rules (see docs/2-contracts/test-cases/CONVENTION.md §8):
  R1: Every FR-NNNN has ≥ 1 TC trace                       (warn → error 1 week later)
  R2: Every active module has ≥ 5 TC                       (warn → error)
  R3: Every BDD scenario has <!-- TC-ID: BDD-NNNN -->      (error)
  R4: No orphan TC (empty trace)                           (warn)
  R5: No duplicate source line range                       (error)
  R6: Tags only from controlled vocabulary                 (warn)
  R7: Required fields present                              (error)

Usage:
  python scripts/ci/check-test-case-coverage.py             # default: warn-only
  python scripts/ci/check-test-case-coverage.py --strict    # warn → error (CI blocking)
  python scripts/ci/check-test-case-coverage.py --report    # write coverage report to stdout
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install via: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs/2-contracts/test-cases/registry.yaml"
FR_DIR = REPO_ROOT / "docs/2-contracts/functional-requirements"
MODULES_DIR = REPO_ROOT / "docs/2-contracts/modules"
BDD_FILE = REPO_ROOT / "docs/3-process/bdd/all-features.md"

VALID_TAGS = {
    "happy-path",
    "boundary",
    "error-handling",
    "business-rule",
    "idempotency",
    "smoke-test",
    "security",
}
REQUIRED_FIELDS = {"id", "title", "type", "source", "trace", "tags", "status"}
MODULE_MIN_TC = 5
SCENARIO_PATTERN = re.compile(r"^\s*Scenario(?:\s+Outline)?:")
TC_ID_PATTERN = re.compile(r"<!--\s*TC-ID:\s*([A-Z]+-\d{4})")


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print(f"ERROR: registry not found at {REGISTRY_PATH}", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}


def list_active_frs() -> set[str]:
    """Return set of FR-NNNN IDs from FR-*.md filenames."""
    return {
        m.group(1)
        for path in FR_DIR.glob("FR-*.md")
        if (m := re.match(r"(FR-\d{4})", path.name))
    }


def list_active_modules() -> set[str]:
    """Return set of module names (filename stem) excluding INDEX."""
    return {
        path.stem
        for path in MODULES_DIR.glob("*.md")
        if path.stem != "INDEX"
    }


def check_r1_fr_coverage(cases: list[dict], strict: bool) -> tuple[int, int]:
    """R1: Every FR has ≥ 1 TC trace."""
    active = list_active_frs()
    covered = set()
    for c in cases:
        for fr in c.get("trace", {}).get("fr", []) or []:
            covered.add(fr)
    uncovered = sorted(active - covered)

    if uncovered:
        severity = "ERROR" if strict else "WARN"
        print(f"[{severity}] R1 — {len(uncovered)} FR(s) uncovered (no TC trace):")
        for fr in uncovered:
            print(f"        {fr}")
        return (len(uncovered) if strict else 0), len(uncovered)
    print(f"[OK]   R1 — All {len(active)} FRs have ≥ 1 TC trace")
    return 0, 0


def check_r2_module_coverage(cases: list[dict], strict: bool) -> tuple[int, int]:
    """R2: Every module has ≥ MODULE_MIN_TC."""
    active = list_active_modules()
    counts: dict[str, int] = defaultdict(int)
    for c in cases:
        for m in c.get("trace", {}).get("module", []) or []:
            counts[m] += 1

    under = sorted([(m, counts.get(m, 0)) for m in active if counts.get(m, 0) < MODULE_MIN_TC])
    if under:
        severity = "ERROR" if strict else "WARN"
        print(f"[{severity}] R2 — {len(under)} module(s) under {MODULE_MIN_TC} TC threshold:")
        for m, n in under:
            print(f"        {m}: {n}/{MODULE_MIN_TC}")
        return (len(under) if strict else 0), len(under)
    print(f"[OK]   R2 — All {len(active)} modules have ≥ {MODULE_MIN_TC} TC")
    return 0, 0


def check_r3_bdd_scenarios_tagged() -> tuple[int, int]:
    """R3: Every BDD scenario has <!-- TC-ID: BDD-NNNN --> (always error)."""
    if not BDD_FILE.exists():
        return 0, 0
    lines = BDD_FILE.read_text(encoding="utf-8").splitlines()
    scenarios = []
    for i, line in enumerate(lines):
        if SCENARIO_PATTERN.match(line):
            # Look backwards up to 5 lines for a TC-ID marker (allowing tags between marker and Scenario)
            tagged = any(TC_ID_PATTERN.search(lines[j]) for j in range(max(0, i - 5), i))
            if not tagged:
                scenarios.append((i + 1, line.strip()))

    if scenarios:
        print(f"[ERROR] R3 — {len(scenarios)} BDD scenario(s) missing TC-ID marker:")
        for line_no, line in scenarios[:10]:
            print(f"        L{line_no}: {line[:80]}")
        if len(scenarios) > 10:
            print(f"        ... and {len(scenarios) - 10} more")
        return len(scenarios), len(scenarios)
    print("[OK]   R3 — All BDD scenarios tagged")
    return 0, 0


def check_r4_orphan_tcs(cases: list[dict], strict: bool) -> tuple[int, int]:
    """R4: Orphan TC (empty trace) — always warn-only (some cross-cutting cases
    legitimately lack FR/flow trace, e.g. V1↔V2 sync, internal infra)."""
    orphans = []
    for c in cases:
        trace = c.get("trace") or {}
        if not any(trace.get(k) for k in ("flow", "fr", "module")):
            orphans.append(c["id"])
    if orphans:
        print(f"[WARN] R4 — {len(orphans)} orphan TC(s) (empty trace, allowed for cross-cutting):")
        for tid in orphans[:10]:
            print(f"        {tid}")
        if len(orphans) > 10:
            print(f"        ... and {len(orphans) - 10} more")
        return 0, len(orphans)
    print("[OK]   R4 — No orphan TCs")
    return 0, 0


def check_r5_duplicate_source(cases: list[dict]) -> tuple[int, int]:
    """R5: No two TCs share the same source line range (always error)."""
    seen: dict[str, list[str]] = defaultdict(list)
    for c in cases:
        seen[c.get("source", "")].append(c["id"])
    dups = {s: ids for s, ids in seen.items() if len(ids) > 1}
    if dups:
        print(f"[ERROR] R5 — {len(dups)} duplicate source range(s):")
        for src, ids in list(dups.items())[:10]:
            print(f"        {src}  →  {', '.join(ids)}")
        return len(dups), len(dups)
    print("[OK]   R5 — No duplicate source ranges")
    return 0, 0


def check_r6_tag_vocabulary(cases: list[dict], strict: bool) -> tuple[int, int]:
    """R6: Tags from controlled vocabulary only."""
    bad: list[tuple[str, list[str]]] = []
    for c in cases:
        invalid = [t for t in (c.get("tags") or []) if t not in VALID_TAGS]
        if invalid:
            bad.append((c["id"], invalid))
    if bad:
        severity = "ERROR" if strict else "WARN"
        print(f"[{severity}] R6 — {len(bad)} TC(s) with non-vocabulary tags:")
        for tid, tags in bad[:10]:
            print(f"        {tid}: {tags}")
        return (len(bad) if strict else 0), len(bad)
    print(f"[OK]   R6 — All tags from controlled vocabulary ({len(VALID_TAGS)} terms)")
    return 0, 0


def check_r7_required_fields(cases: list[dict]) -> tuple[int, int]:
    """R7: Required fields present (always error)."""
    bad = []
    for c in cases:
        missing = REQUIRED_FIELDS - set(c.keys())
        if missing:
            bad.append((c.get("id", "<no-id>"), sorted(missing)))
    if bad:
        print(f"[ERROR] R7 — {len(bad)} TC(s) with missing required fields:")
        for tid, missing in bad[:10]:
            print(f"        {tid}: missing {missing}")
        return len(bad), len(bad)
    print(f"[OK]   R7 — All {len(cases)} TCs have required fields")
    return 0, 0


def print_summary(cases: list[dict]) -> None:
    by_type: dict[str, int] = defaultdict(int)
    for c in cases:
        by_type[c.get("type", "unknown")] += 1
    print("\n" + "=" * 60)
    print("Registry summary:")
    print(f"  Total TCs: {len(cases)}")
    for t in ("bdd", "integration", "unit", "eval", "e2e"):
        print(f"    {t:>12}: {by_type.get(t, 0)}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Treat warns as errors (CI blocking)")
    parser.add_argument("--report", action="store_true", help="Also print coverage report")
    args = parser.parse_args()

    registry = load_registry()
    cases = registry.get("test_cases") or []

    print(f"Checking {len(cases)} test cases against coverage rules...\n")

    total_errors = 0
    total_warnings = 0

    for fn, name in [
        (lambda: check_r1_fr_coverage(cases, args.strict), "R1"),
        (lambda: check_r2_module_coverage(cases, args.strict), "R2"),
        (check_r3_bdd_scenarios_tagged, "R3"),
        (lambda: check_r4_orphan_tcs(cases, args.strict), "R4"),
        (lambda: check_r5_duplicate_source(cases), "R5"),
        (lambda: check_r6_tag_vocabulary(cases, args.strict), "R6"),
        (lambda: check_r7_required_fields(cases), "R7"),
    ]:
        errs, warns = fn()
        total_errors += errs
        total_warnings += warns

    if args.report:
        print_summary(cases)

    print(f"\nResult: {total_errors} error(s), {total_warnings} warning(s)")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
