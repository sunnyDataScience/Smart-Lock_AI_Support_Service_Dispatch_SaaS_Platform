#!/usr/bin/env python3
"""One-shot migration: QTM 「指定 TC」 free-text column -> a real relation table.

The QTM master table in 20_Test_Cases.md §2.1 carries the RQ x TC edge inside a
single string cell: "TC-CS-AI-01/02/11", "TC-COMPLIANCE-01~04",
"TC-CS-AI-04 + TC-COMPLIANCE-07", and sometimes plain prose like
"Flow DSL state/guard/block contract" -- which is a test *design*, not a case.

This script expands that column into one edge per row and derives `kind` from
each case's own 類型 column in the detail tables (§3 onwards).

    類型      -> kind
    happy     -> happy
    權限      -> failure     (a negative authorisation assertion)
    例外      -> failure
    timeout   -> recovery
    非功能    -> boundary

Rows whose designated cell holds no resolvable TC ID are emitted as
`unresolved` so they surface as a gap instead of silently vanishing.

SPENT -- do not re-run. It was executed once on 2026-07-27; since then
20_Test_Cases.md §2.1 has been regenerated *from* the YAML by
`_sync_test_canon.py`, so the 指定 TC column this script reads no longer
exists in its original shape. Kept only as the audit record of how
`_relations/rq_verified_by_tc.yaml` came to be; maintain that YAML by hand.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANON = HERE.parent
OUT = HERE / "_relations" / "rq_verified_by_tc.yaml"

TC_RE = re.compile(r"TC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d+")

# The 類型 column sits at a different index in each detail table, and carries
# composite values ("happy+例外", "權限+冪等"). So: scan every cell, and when a
# cell mixes a negative token with happy, the negative one wins -- V10 asks
# whether the failure path is covered, and that is the informative answer.
KIND_TOKENS = [
    ("例外", "failure"),
    ("權限", "failure"),
    ("timeout", "recovery"),
    ("邊界", "boundary"),
    ("非功能", "boundary"),
    ("happy", "happy"),
]


def load_case_kinds() -> dict[str, str]:
    """TC ID -> kind, scanned out of the detail tables' 類型 cell."""
    text = (CANON / "20_Test_Cases.md").read_text(encoding="utf-8")
    kinds: dict[str, str] = {}
    # The ID cell sometimes has completion markers glued on
    # ("TC-DISPATCH-07✅2026-07-10CR-0144(...)"), so anchor on the ID prefix and
    # discard whatever trails it inside the same cell.
    row_re = rf"^\|\s*({TC_RE.pattern})[^|]*\|(.+)$"
    for tc, rest in re.findall(row_re, text, re.MULTILINE):
        for col in (c.strip() for c in rest.split("|")):
            if not col or len(col) > 24:  # a long cell is prose, not a 類型
                continue
            hit = next((k for token, k in KIND_TOKENS if token in col), None)
            if hit:
                kinds[tc] = hit
                break
        kinds.setdefault(tc, "happy")
    return kinds


def expand(cell: str, known: set[str]) -> tuple[list[str], str]:
    """Expand a designated-TC cell into concrete TC IDs.

    Handles three shorthand forms layered on top of each other:
        TC-CS-AI-01/02/11   suffix list sharing the leading domain
        TC-COMPLIANCE-01~04 inclusive range
        A + B               explicit conjunction
    Returns (ids, leftover_prose).
    """
    ids: list[str] = []
    text = cell

    # ranges first -- they would otherwise be eaten by the bare-ID pass
    for m in re.finditer(rf"({TC_RE.pattern})\s*[~～]\s*(\d+)", text):
        head, last = m.group(1), int(m.group(2))
        stem, first = head.rsplit("-", 1)
        ids.extend(f"{stem}-{n:02d}" for n in range(int(first), last + 1))
        text = text.replace(m.group(0), " ")

    # slash lists: TC-CS-AI-01/02/11
    for m in re.finditer(rf"({TC_RE.pattern})((?:\s*/\s*\d+)+)", text):
        head, tail = m.group(1), m.group(2)
        stem = head.rsplit("-", 1)[0]
        ids.append(head)
        ids.extend(f"{stem}-{n.strip()}" for n in tail.split("/") if n.strip())
        text = text.replace(m.group(0), " ")

    ids.extend(TC_RE.findall(text))
    for tc in set(ids):
        text = text.replace(tc, " ")

    ids = [t for t in dict.fromkeys(ids)]
    prose = re.sub(r"[\s+/,、（）()]+", " ", text).strip()
    return ids, prose


def main() -> None:
    text = (CANON / "20_Test_Cases.md").read_text(encoding="utf-8")
    kinds = load_case_kinds()
    known = set(kinds)

    edges: list[dict] = []
    unresolved: list[dict] = []
    dangling: set[str] = set()

    for row in re.findall(r"^\|\s*QTM-[^|]+\|(.+)$", text, re.MULTILINE):
        cols = [c.strip() for c in row.split("|")]
        if len(cols) < 7:
            continue
        rq, _typ, topic, _prio, ts, designated = cols[0], cols[1], cols[2], cols[3], cols[4], cols[5]
        ids, prose = expand(designated, known)

        for tc in ids:
            if tc not in known:
                # Designated but non-existent. Almost all of these were minted by
                # prefixing "TC-" onto a requirement ID -- a naming convention
                # masquerading as a relation. Keep them out of `edges` so the
                # coverage numbers stay honest.
                dangling.add((rq, tc))
                continue
            edges.append({
                "requirement": rq,
                "case": tc,
                "kind": kinds.get(tc, "happy"),
                "ts": ts,
                "note": topic,
            })
        if not any(t in known for t in ids):
            unresolved.append({"requirement": rq, "design": prose or designated, "ts": ts, "note": topic})

    # de-duplicate: the same (rq, tc) can be designated by several QTM rows
    seen: set[tuple[str, str]] = set()
    deduped = []
    for e in edges:
        key = (e["requirement"], e["case"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    by_rq: dict[str, list[dict]] = defaultdict(list)
    for e in deduped:
        by_rq[e["requirement"]].append(e)

    lines = [
        "# RQ × TC 關聯表 —— 「哪條需求由哪些案例驗證」",
        "#",
        "# 真相源。由 _extract_rq_tc.py 從 20_Test_Cases.md §2.1 的「指定 TC」欄一次性攤平，",
        "# 之後改這裡，不改 markdown —— §2.1 已降級為本檔的生成視圖。",
        "#",
        "# kind 值域：happy | boundary | failure | recovery",
        "#   來自各 TC 自己的「類型」欄：happy→happy、權限/例外→failure、timeout→recovery、非功能→boundary",
        "#   kind 讓「這條需求有沒有測試」升級成「這條需求的失敗路徑有沒有測試」（V10）。",
        "#",
        "# note 欄目前帶的是 QTM 的需求主題，屬機器搬運。",
        "# ⚠️ 人工複審時請改寫成「這個案例的哪一句預期結果，證明了那條需求」——",
        "#    說不出來的邊就該刪掉，那正是這一欄存在的意義。",
        "",
        "version: 1",
        "",
        "edges:",
    ]
    for rq in sorted(by_rq):
        lines.append(f"  # {rq}")
        for e in sorted(by_rq[rq], key=lambda x: x["case"]):
            note = e["note"].replace('"', "'")
            lines.append(
                f'  - {{requirement: {e["requirement"]}, case: {e["case"]}, '
                f'kind: {e["kind"]}, ts: "{e["ts"]}", note: "{note}"}}'
            )

    lines += [
        "",
        "# ── 只有測試設計、還沒有具體案例的需求 ──────────────────────────",
        "#",
        "# 這些 QTM 列的「指定 TC」欄寫的是設計描述而不是 TC ID。",
        "# 規格完整 ≠ 案例存在。留白比塞一個假 ID 誠實。",
        "",
        "unresolved:",
    ]
    for u in sorted(unresolved, key=lambda x: x["requirement"]):
        design = u["design"].replace('"', "'")[:90]
        lines.append(
            f'  - {{requirement: {u["requirement"]}, design: "{design}", ts: "{u["ts"]}"}}'
        )

    lines += [
        "",
        "# ── 指定了不存在的案例 ──────────────────────────────────────────",
        "#",
        "# 這些 TC ID 在 20_Test_Cases.md 的詳細案例表裡找不到。",
        "# 多數是把需求 ID 前面加上 TC- 湊出來的——命名慣例偽裝成關聯（AP-1）。",
        "# 兩條出路：補寫真案例，或刪掉這筆指定並承認缺口。不要留著假 ID。",
        "",
        "dangling:",
    ]
    for rq, tc in sorted(dangling):
        lines.append(f'  - {{requirement: {rq}, designated_case: {tc}}}')

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{OUT.relative_to(HERE)}")
    print(f"  邊       {len(deduped)} 條（涵蓋 {len(by_rq)} 條需求）")
    print(f"  未解析   {len(unresolved)} 列（只有設計、沒有案例）")
    print(f"  懸空指定 {len(dangling)} 筆（指定了不存在的 TC）")
    dist = defaultdict(int)
    for e in deduped:
        dist[e["kind"]] += 1
    print(f"  kind 分布 {dict(sorted(dist.items()))}")


if __name__ == "__main__":
    main()
