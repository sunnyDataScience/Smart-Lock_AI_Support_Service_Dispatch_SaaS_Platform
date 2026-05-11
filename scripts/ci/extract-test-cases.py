#!/usr/bin/env python3
"""
scripts/ci/extract-test-cases.py
--------------------------------
Scan all test source files for <!-- TC-ID: XXX --> markers and (re)generate
docs/2-contracts/test-cases/registry.yaml.

Sources scanned:
  - docs/3-process/bdd/all-features.md      → BDD-NNNN
  - docs/2-contracts/modules/*.md           → IT-NNNN / UT-NNNN
  - docs/2-contracts/state-machines/*.md    → IT-NNNN (transitions as integration cases)

Usage:
  python scripts/ci/extract-test-cases.py             # rebuild registry from sources
  python scripts/ci/extract-test-cases.py --dry-run   # show what would change, no write
  python scripts/ci/extract-test-cases.py --assign-ids  # replace PLACEHOLDER markers with next available IDs
  python scripts/ci/extract-test-cases.py --check     # exit 1 if registry would change (CI consistency check)

Schema: see docs/2-contracts/test-cases/CONVENTION.md §5
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install via: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs/2-contracts/test-cases/registry.yaml"

SOURCES = {
    "bdd": [REPO_ROOT / "docs/3-process/bdd/all-features.md"],
    "modules": sorted((REPO_ROOT / "docs/2-contracts/modules").glob("*.md")),
    "state_machines": sorted((REPO_ROOT / "docs/2-contracts/state-machines").glob("*.md")),
}

TC_ID_PATTERN = re.compile(
    r"<!--\s*TC-ID:\s*([A-Z]+-\d{4})(?:\s*\|\s*legacy:\s*([A-Za-z0-9_-]+))?\s*-->"
)
PLACEHOLDER_PATTERN = re.compile(r"<!--\s*TC-ID:\s*PLACEHOLDER(?:\s*\|\s*([^>]+))?\s*-->")

TYPE_PREFIX = {
    "BDD": "bdd",
    "IT": "integration",
    "UT": "unit",
    "EVAL": "eval",
    "E2E": "e2e",
}

VALID_TAGS = {
    "happy-path",
    "boundary",
    "error-handling",
    "business-rule",
    "idempotency",
    "smoke-test",
    "security",
}


@dataclass
class TestCase:
    id: str
    title: str
    type: str
    source: str  # file#Lstart-Lend
    trace: dict = field(default_factory=lambda: {"flow": [], "fr": [], "module": []})
    tags: list[str] = field(default_factory=list)
    status: str = "implemented"
    legacy_id: str | None = None
    test_impl: str | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "source": self.source,
            "trace": {k: v for k, v in self.trace.items() if v},
            "tags": self.tags,
            "status": self.status,
        }
        if self.legacy_id:
            d["legacy_id"] = self.legacy_id
        if self.test_impl:
            d["test_impl"] = self.test_impl
        return d


def parse_id_prefix(tc_id: str) -> tuple[str, int]:
    prefix, num = tc_id.split("-")
    return prefix, int(num)


def infer_title_from_context(lines: list[str], marker_line_idx: int) -> str:
    """Pick the first non-empty, non-tag line after the marker as the case title."""
    for j in range(marker_line_idx + 1, min(marker_line_idx + 10, len(lines))):
        line = lines[j].strip()
        if not line:
            continue
        if line.startswith("@") and "Scenario" not in line:
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        if line.startswith("Scenario:"):
            line = line[len("Scenario:"):].strip()
        if line.startswith("情境") or line.startswith("規格"):
            parts = line.split(":", 1) + line.split("—", 1)
            line = parts[1].strip() if len(parts) > 1 else line
        return line[:80]
    return "(title not inferred)"


def infer_source_range(file_rel: str, start_line: int, lines: list[str]) -> str:
    """Find next TC-ID marker or EOF; use as upper bound of this case's source range."""
    for j in range(start_line, len(lines)):
        if TC_ID_PATTERN.search(lines[j]) and j > start_line - 1:
            return f"{file_rel}#L{start_line}-L{j}"
    return f"{file_rel}#L{start_line}-L{len(lines)}"


def scan_file(path: Path, default_type: str) -> list[TestCase]:
    """Extract all TC-ID markers from a single file."""
    cases: list[TestCase] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    file_rel = str(path.relative_to(REPO_ROOT))

    markers: list[tuple[int, str, str | None]] = []
    for i, line in enumerate(lines):
        m = TC_ID_PATTERN.search(line)
        if m:
            markers.append((i, m.group(1), m.group(2)))

    for idx, (line_idx, tc_id, legacy) in enumerate(markers):
        prefix, _ = parse_id_prefix(tc_id)
        case_type = TYPE_PREFIX.get(prefix, default_type)
        title = infer_title_from_context(lines, line_idx)

        # Source range: from marker line to next marker (or EOF)
        next_line = markers[idx + 1][0] if idx + 1 < len(markers) else len(lines)
        source = f"{file_rel}#L{line_idx + 1}-L{next_line}"

        cases.append(
            TestCase(
                id=tc_id,
                title=title,
                type=case_type,
                source=source,
                legacy_id=legacy,
            )
        )

    return cases


def scan_all() -> list[TestCase]:
    all_cases: list[TestCase] = []
    for path in SOURCES["bdd"]:
        if path.exists():
            all_cases.extend(scan_file(path, "bdd"))
    for path in SOURCES["modules"]:
        all_cases.extend(scan_file(path, "integration"))
    for path in SOURCES["state_machines"]:
        all_cases.extend(scan_file(path, "integration"))
    return all_cases


def find_placeholders() -> list[tuple[Path, int, str | None]]:
    """Return [(file, line_idx, legacy_hint)] of PLACEHOLDER markers across all sources."""
    out: list[tuple[Path, int, str | None]] = []
    for source_group in SOURCES.values():
        for path in source_group:
            if not path.exists():
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
                m = PLACEHOLDER_PATTERN.search(line)
                if m:
                    hint = m.group(1).strip() if m.group(1) else None
                    out.append((path, i, hint))
    return out


def next_available_id(existing: list[TestCase], prefix: str) -> str:
    nums = [parse_id_prefix(c.id)[1] for c in existing if c.id.startswith(f"{prefix}-")]
    next_num = (max(nums) + 1) if nums else 1
    return f"{prefix}-{next_num:04d}"


def assign_ids(dry_run: bool = False) -> int:
    existing = scan_all()
    placeholders = find_placeholders()
    if not placeholders:
        print("No PLACEHOLDER markers found.")
        return 0

    by_file: dict[Path, list[tuple[int, str | None]]] = {}
    for path, line_idx, hint in placeholders:
        by_file.setdefault(path, []).append((line_idx, hint))

    assigned_count = 0
    for path, items in by_file.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_idx, hint in items:
            # Determine prefix from file location heuristic
            if "bdd/all-features" in str(path):
                prefix = "BDD"
            elif "/modules/" in str(path):
                prefix = "IT"  # default; can be overridden manually to UT
            elif "/state-machines/" in str(path):
                prefix = "IT"
            else:
                print(f"WARN: cannot infer prefix for {path}", file=sys.stderr)
                continue

            new_id = next_available_id(existing, prefix)
            existing.append(TestCase(id=new_id, title="(pending)", type=TYPE_PREFIX[prefix], source=str(path)))

            old_line = lines[line_idx]
            legacy_part = f" | legacy: {hint}" if hint else ""
            new_marker = f"<!-- TC-ID: {new_id}{legacy_part} -->"
            lines[line_idx] = PLACEHOLDER_PATTERN.sub(new_marker, old_line)
            assigned_count += 1
            print(f"  {path.relative_to(REPO_ROOT)}:{line_idx + 1}  PLACEHOLDER → {new_id}")

        if not dry_run:
            path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    print(f"\nAssigned {assigned_count} new TC-IDs{' (dry-run, no files written)' if dry_run else ''}.")
    return assigned_count


def build_registry(cases: list[TestCase]) -> dict:
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generated_by": "scripts/ci/extract-test-cases.py",
            "schema_version": 1,
            "total_count": len(cases),
        },
        "test_cases": [c.to_dict() for c in sorted(cases, key=lambda x: (x.id.split("-")[0], int(x.id.split("-")[1])))],
    }


def write_registry(registry: dict, dry_run: bool) -> None:
    yaml_text = yaml.dump(
        registry,
        sort_keys=False,
        allow_unicode=True,
        width=120,
        default_flow_style=False,
    )
    if dry_run:
        print(yaml_text)
        return
    header = (
        "# Test Case Registry — CI Single Source of Truth\n"
        "#\n"
        "# Auto-generated by scripts/ci/extract-test-cases.py\n"
        "# DO NOT EDIT MANUALLY — edit source files and re-run the script.\n"
        "#\n"
        "# Schema: docs/2-contracts/test-cases/CONVENTION.md §5\n\n"
    )
    REGISTRY_PATH.write_text(header + yaml_text, encoding="utf-8")
    print(f"Wrote {len(registry['test_cases'])} cases to {REGISTRY_PATH.relative_to(REPO_ROOT)}")


def check_registry_consistency() -> int:
    """Exit 1 if registry differs from what extract would produce."""
    cases = scan_all()
    fresh = build_registry(cases)
    if not REGISTRY_PATH.exists():
        print("ERROR: registry.yaml missing.", file=sys.stderr)
        return 1
    current_text = REGISTRY_PATH.read_text(encoding="utf-8")
    try:
        current = yaml.safe_load(current_text)
    except yaml.YAMLError as exc:
        print(f"ERROR: registry.yaml invalid YAML: {exc}", file=sys.stderr)
        return 1
    current_cases = (current or {}).get("test_cases") or []
    fresh_cases = fresh["test_cases"]

    if len(current_cases) != len(fresh_cases):
        print(f"DRIFT: count differs (registry={len(current_cases)}, fresh={len(fresh_cases)})", file=sys.stderr)
        return 1

    diffs = []
    by_id = {c["id"]: c for c in current_cases}
    for fc in fresh_cases:
        cc = by_id.get(fc["id"])
        if not cc:
            diffs.append(f"  MISSING in registry: {fc['id']}")
            continue
        if cc.get("source") != fc["source"]:
            diffs.append(f"  {fc['id']}: source drifted ({cc.get('source')} → {fc['source']})")

    if diffs:
        print("DRIFT detected:", file=sys.stderr)
        for d in diffs:
            print(d, file=sys.stderr)
        return 1

    print("Registry consistent.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--assign-ids", action="store_true", help="Replace PLACEHOLDER markers with next IDs")
    parser.add_argument("--check", action="store_true", help="Exit 1 if registry would change")
    args = parser.parse_args()

    if args.check:
        return check_registry_consistency()

    if args.assign_ids:
        assign_ids(dry_run=args.dry_run)

    cases = scan_all()
    registry = build_registry(cases)
    write_registry(registry, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
