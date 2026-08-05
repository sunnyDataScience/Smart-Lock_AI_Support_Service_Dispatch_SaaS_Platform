#!/usr/bin/env python3
"""Render each SC into a Gherkin BDD view — three surfaces, one source (CR-0185).

BDD here is a **generated view of the scenario spine**, never a fifth hand-kept
numbering system (that is exactly the failure 28_Scenarios §0 was built to end).
Everything is derived from the SC card fields already parsed by _canon.Scenario:

    As a  <primary persona>          <- sc_embodies_persona.yaml + 06_UX §3
    I want <SC 名稱>                  <- 28_Scenarios §1
    So that <persona 成功定義>        <- 06_UX §3
    Given <觸發>  When <主要步驟>  Then <完成判定>          -> the happy path
    each 失敗與例外 clause (cond → result)                  -> one @failure scenario

Keywords stay English (Feature/Scenario/Given/When/Then) so standard Gherkin tools
read the files; the step text stays 繁體中文. Change the SC card upstream and rerun
`_build_workbooks.py` — the .feature files, the 28_Scenarios inline blocks, and the
workbook sheet all regenerate together. Do not hand-edit any of the three.

Outputs:
    bdd/SC-*.feature                     one Gherkin feature per scenario
    28_Scenarios.md                      per-card <!-- BEGIN/END GENERATED BDD --> block
    (xlsx sheet is emitted by _build_workbooks.py via bdd_rows())
"""

from __future__ import annotations

import re
from pathlib import Path

import _canon as C

HERE = Path(__file__).resolve().parent
CANON = HERE.parent
BDD_DIR = CANON / "bdd"
SCENARIO_MD = CANON / "28_Scenarios.md"


def _clean(text: str) -> str:
    return C.plain(text).strip()


def _arrow_steps(text: str, first_kw: str) -> list[str]:
    """`a → b → c` becomes `<first_kw> a / And b / And c`. Empty text -> []."""
    parts = [p.strip() for p in re.split(r"\s*→\s*", _clean(text)) if p.strip()]
    if not parts:
        return []
    return [f"    {first_kw} {parts[0]}", *(f"    And {p}" for p in parts[1:])]


def _then_steps(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[；;。]\s*", _clean(text)) if p.strip()]
    if not parts:
        return ["    Then （完成判定未填，補 28_Scenarios 卡）"]
    return [f"    Then {parts[0]}", *(f"    And {p}" for p in parts[1:])]


def _failure_clauses(text: str) -> list[tuple[str, str]]:
    """Split 失敗與例外 into (condition, result). `cond → result`; ；separates clauses."""
    out: list[tuple[str, str]] = []
    for clause in re.split(r"[；;]\s*", _clean(text)):
        clause = clause.strip()
        if not clause:
            continue
        if "→" in clause:
            cond, _, result = clause.partition("→")
            out.append((cond.strip(), result.strip()))
        else:
            out.append(("觸發此例外情況", clause))
    return out


def _feature_text(sc: C.Scenario, per_by_id: dict, rel: C.Relations) -> str:
    prims = rel.personas_of(sc.sc_id, "primary")
    secs = rel.personas_of(sc.sc_id, "secondary")
    prim = per_by_id.get(prims[0]) if prims else None

    lines = [f"@{sc.sc_id} @{sc.priority} @{sc.line}", f"Feature: {sc.sc_id} {sc.name}", ""]
    if prim:
        lines += [
            f"  As a {prim.name}（{prim.per_id}）",
            f"  I want {sc.name}",
            f"  So that {prim.success}",
            "",
        ]

    def label(pids: list[str], role: str) -> str:
        return "；".join(f"{p} {per_by_id[p].name}（{role}）" for p in pids if p in per_by_id)

    who = "；".join(filter(None, [label(prims, "primary"), label(secs, "secondary")]))
    if who:
        lines.append(f"  # 體現 Persona: {who}")
    script = sorted(rel.script_cases(sc.sc_id))
    if script:
        lines.append(f"  # 驗收腳本案例（sc_verified_by_tc）: {', '.join(script)}")
    lines.append("")

    lines.append("  @happy")
    lines.append(f"  Scenario: 正常路徑 — {sc.name}")
    lines += _arrow_steps(sc.trigger, "Given") or ["    Given （觸發未填，補 28_Scenarios 卡）"]
    lines += _arrow_steps(sc.steps, "When") or ["    When 執行旅程主要步驟"]
    lines += _then_steps(sc.done)
    lines.append("")

    for cond, result in _failure_clauses(sc.fail):
        lines.append("  @failure")
        lines.append(f"  Scenario: 例外 — {cond}")
        lines += _arrow_steps(sc.trigger, "Given") or ["    Given （觸發未填）"]
        lines.append(f"    When {cond}")
        lines.append(f"    Then {result}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_features() -> dict[str, str]:
    """{sc_id: gherkin text} for every SC that has a primary persona edge."""
    per_by_id = {p.per_id: p for p in C.load_personas()}
    rel = C.load_relations()
    return {
        sc.sc_id: _feature_text(sc, per_by_id, rel)
        for sc in C.load_scenarios()
    }


def bdd_rows() -> list[dict]:
    """Flat rows (one per Gherkin scenario) for the workbook sheet."""
    per_by_id = {p.per_id: p for p in C.load_personas()}
    rel = C.load_relations()
    rows: list[dict] = []
    for sc in C.load_scenarios():
        prims = rel.personas_of(sc.sc_id, "primary")
        persona = f"{prims[0]} {per_by_id[prims[0]].name}" if prims and prims[0] in per_by_id else "⚠ 無"
        when = "\n".join(p.strip() for p in re.split(r"\s*→\s*", _clean(sc.steps)) if p.strip())
        rows.append({
            "sc": sc.sc_id, "name": sc.name, "line": sc.line, "persona": persona,
            "type": "happy 正常路徑", "given": _clean(sc.trigger), "when": when,
            "then": _clean(sc.done),
        })
        for cond, result in _failure_clauses(sc.fail):
            rows.append({
                "sc": sc.sc_id, "name": sc.name, "line": sc.line, "persona": persona,
                "type": "failure 例外", "given": _clean(sc.trigger), "when": cond, "then": result,
            })
    return rows


def write_feature_files(features: dict[str, str]) -> int:
    BDD_DIR.mkdir(exist_ok=True)
    keep = {f"{sc}.feature" for sc in features}
    for stale in BDD_DIR.glob("SC-*.feature"):
        if stale.name not in keep:
            stale.unlink()
    for sc, text in features.items():
        # newline="\n"：生成物一律 LF，否則同一份 feature 在 Windows 與 Linux 上跑
        # 會差出「每行一個位元組」，diff 全紅而內容其實沒動。
        (BDD_DIR / f"{sc}.feature").write_text(text, encoding="utf-8", newline="\n")
    return len(features)


def inject_scenarios_md(features: dict[str, str]) -> None:
    """Insert one BEGIN/END GENERATED BDD block at the end of each SC card. Idempotent."""
    text = SCENARIO_MD.read_text(encoding="utf-8")
    text = re.sub(
        r"\n*<!-- BEGIN GENERATED BDD .*?<!-- END GENERATED BDD[^>]*-->",
        "", text, flags=re.S,
    )

    def repl(m: re.Match) -> str:
        body, sc = m.group(1), m.group(2)
        if sc not in features:
            return body
        block = (
            f"\n\n<!-- BEGIN GENERATED BDD {sc} · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->\n"
            f"```gherkin\n{features[sc].rstrip()}\n```\n"
            f"<!-- END GENERATED BDD {sc} -->"
        )
        return body.rstrip() + block

    text = re.sub(r"(#### (SC-\d\d).*?)(?=\n#### |\n### |\n## |\Z)", repl, text, flags=re.S)
    SCENARIO_MD.write_text(text, encoding="utf-8", newline="\n")


def generate() -> dict[str, str]:
    features = build_features()
    write_feature_files(features)
    inject_scenarios_md(features)
    return features


if __name__ == "__main__":
    n = len(generate())
    print(f"  ✓ bdd/*.feature（{n} 條）+ 28_Scenarios.md 內嵌 BDD 塊")
