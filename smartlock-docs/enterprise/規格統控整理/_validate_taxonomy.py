#!/usr/bin/env python3
"""對帳 Feature 層（G3）vs canon：171 個 Story 一條一組，不重不漏。

掛載表是人寫的，所以三種錯都可能發生：漏掛（Story 沒有 parent）、重掛（同一條掛兩組）、
幽靈（寫了 canon 沒有的 ID）。三種都會讓「18 Feature 蓋滿 171」這種宣稱變成
沒人驗過的口號——2026-08-05 的 EXPECTED 就是這樣寫死在常數裡的。

**這支是 `_feature_taxonomy.yaml` 的守線**：改過 yaml 一定要先跑這支再跑
`_build_workbooks.py`，否則漏掛會一路生成進四本 xlsx 的「無 parent」段落才被發現。

用法：
    cd smartlock-docs/enterprise/規格統控整理
    uv run python _validate_taxonomy.py           # 對帳
    uv run python _validate_taxonomy.py --md      # 對帳 + 重生 Feature層定義.md
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _canon as C  # noqa: E402

TAXONOMY = Path(__file__).with_name("_feature_taxonomy.yaml")


def load_taxonomy() -> dict:
    return yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))


def main() -> int:
    draft = load_taxonomy()
    epics, features = draft["epics"], draft["features"]

    canon_fr = [q.req_id for q in C.load_requirements()]
    canon_nfr = [n.req_id for n in C.load_nfrs()]
    canon = set(canon_fr) | set(canon_nfr)
    name_of = {q.req_id: q.name for q in C.load_requirements()}
    name_of.update({n.req_id: n.name for n in C.load_nfrs()})

    assigned: Counter[str] = Counter()
    owner: dict[str, str] = {}
    for key, meta in features.items():
        if meta["epic"] not in epics:
            print(f"✗ {key} 的 epic「{meta['epic']}」不存在")
            return 1
        for rid in list(meta["fr"]) + list(meta["nfr"]):
            assigned[rid] += 1
            owner.setdefault(rid, key)

    ghost = sorted(set(assigned) - canon)
    missing = sorted(canon - set(assigned))
    duped = sorted(r for r, n in assigned.items() if n > 1)

    print(f"Epic {len(epics)}／Feature {len(features)}／草案掛載 {len(assigned)} 條")
    print(f"canon: FR {len(canon_fr)} + NFR {len(canon_nfr)} = {len(canon)}")

    ok = True
    for label, items in (("幽靈 ID（canon 沒有）", ghost),
                         ("漏掛（canon 有、草案沒掛）", missing),
                         ("重掛（掛了不只一組）", duped)):
        if items:
            ok = False
            print(f"\n✗ {label}：{len(items)}")
            for rid in items:
                print(f"    {rid}  {name_of.get(rid, '')}")

    if ok:
        print("\n✓ 171 條一條一組，不重不漏")

    print("\n每組數量（FR + NFR）：")
    for key, meta in features.items():
        nfr, fr = len(meta["nfr"]), len(meta["fr"])
        flag = "  ← 無 NFR" if not nfr else ("  ← 無 FR" if not fr else "")
        print(f"    {key:<16} {meta['name']:<12} {fr:>2} + {nfr:>3} = {fr + nfr:>3}{flag}")

    if "--md" in sys.argv:
        out = Path(__file__).with_name("Feature層定義.md")
        out.write_text(render_md(draft, name_of, canon_fr, canon_nfr), encoding="utf-8")
        print(f"\n已輸出 {out.name}")

    return 0 if ok else 1


def render_md(draft: dict, name_of: dict, canon_fr: list, canon_nfr: list) -> str:
    epics, features = draft["epics"], draft["features"]
    lines = [
        "# Feature 層定義（G3）— 業務能力錨點",
        "",
        "> 狀態：**2026-08-08 審核通過**，已是拆解樹 L1/L2 的現行定義。",
        "> 機讀來源：`_feature_taxonomy.yaml`；對帳：`uv run python _validate_taxonomy.py`。",
        "> 本檔為生成物，不要手改——改 yaml 再重跑 `--md`。",
        "> 改動 yaml 等於改動四本 xlsx 與 Plane 的拆解樹，改完必須重跑 `_build_workbooks.py`。",
        "",
        "## 為什麼是新的一套",
        "",
        "| 代 | Feature 的定義 | 為什麼不用 |",
        "|:---|:---|:---|",
        "| G1（2026-07-30）| 32 個 `子系統·模組` 能力群 | 技術切法 |",
        "| G2（2026-08-05）| 19 條 SC 旅程 ＋ 18 個 NFR category 地板 | 情境切法＋品質屬性切法，FR 與 NFR 被拆到樹的兩側 |",
        "| **G3（現行）** | **業務能力（做什麼）** | — |",
        "",
        "G3 的主要收益是 **FR 與 NFR 掛同一組**：一個能力的功能面與品質面不分家。"
        "附帶效果是 G2 時代那 32 條「判不出主旅程」的 FR 全部有了 parent——"
        "衝突的成因（一條 FR 服務多條旅程、樹上 parent 只能有一個）隨錨點更換而消失。",
        "",
        f"{len(epics)} 個 Epic／{len(features)} 個 Feature，蓋滿 "
        f"{len(canon_fr)} FR + {len(canon_nfr)} NFR = {len(canon_fr) + len(canon_nfr)} 個 Story。",
        "",
        "## 總表",
        "",
        "| Epic | Feature | 一句話 | FR | NFR |",
        "|:---|:---|:---|---:|---:|",
    ]
    for key, meta in features.items():
        lines.append(
            f"| {meta['epic']} {epics[meta['epic']]['name']} | `{key}` {meta['name']} "
            f"| {meta['description']} | {len(meta['fr'])} | {len(meta['nfr'])} |")

    lines += ["", "## 逐條歸屬", ""]
    for key, meta in features.items():
        lines += [f"### `{key}` {meta['name']}", "",
                  f"{meta['description']}", "",
                  f"隸屬 `{meta['epic']}` {epics[meta['epic']]['name']}", ""]
        for label, ids in (("FR", meta["fr"]), ("NFR", meta["nfr"])):
            if not ids:
                lines += [f"**{label}**：無", ""]
                continue
            lines += [f"**{label}（{len(ids)}）**", ""]
            lines += [f"- `{rid}` {name_of.get(rid, '')}" for rid in ids]
            lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
