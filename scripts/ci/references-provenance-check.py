"""FR-REF-04：references 側 bronze provenance gate（雙路一致性的 references 半邊）。

背景：知識雙路（ADR-030）——事實走 pgvector corpus、行為/知識走 skill references。
corpus 側 bronze provenance 已由 `pipeline/silver_to_knowledge/audit_corpus.py` 稽核
（bronze_path + sha256 + facts 不含 gdrive）。本腳本補 **references 側** 的同源 gate。

檢查（任一違規 exit 1，可入 CI）：
  1. 結構完整：每個型號 reference 有 frontmatter brand / model / description。
  2. 來源一致：frontmatter brand 與所在品牌目錄一致（防錯置）。

註（sourcing rule，CLAUDE.md）：references 內容源自 bronze（YouTube/website/video）；
GDrive/PDF **只引 URL 不抄內容**——「引 URL」為允許（指標），故本 gate **不**擋 GDrive URL
引用（那是合法指標），只驗結構與 brand 對齊。references 無機讀 bronze provenance metadata
（內容鎖定、人工由 bronze 策展），故「源自 bronze」在 references 側靠 authoring 紀律 +
本結構 gate；corpus 側的完整 bronze provenance（bronze_path+sha256）由 audit_corpus.py 稽核。

用法：uv run python scripts/ci/references-provenance-check.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF_DIR = (
    ROOT / "agent" / "lockcore" / "skills"
    / "locksmith-product-knowledge" / "references"
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def main() -> int:
    if not REF_DIR.exists():
        print(f"ℹ️  references 目錄不存在（{REF_DIR}）→ 略過（可能 skill 未安裝）")
        return 0
    violations: list[str] = []
    checked = 0
    for md in sorted(REF_DIR.rglob("*.md")):
        rel = md.relative_to(REF_DIR)
        text = md.read_text(encoding="utf-8")
        # _common / _brand.md 屬品牌通用/共用，不強制 model
        is_model_ref = not md.name.startswith("_") and rel.parts[0] != "_common"
        if not is_model_ref:
            continue
        checked += 1
        fm = _frontmatter(text)
        # 1. 結構完整
        for field in ("brand", "model", "description"):
            if not fm.get(field):
                violations.append(f"{rel} — frontmatter 缺欄位 {field}")
        # 2. brand 與品牌目錄一致
        brand_dir = rel.parts[0]
        if fm.get("brand") and fm["brand"] != brand_dir:
            violations.append(
                f"{rel} — frontmatter brand='{fm['brand']}' 與目錄 '{brand_dir}' 不一致（錯置？）"
            )

    if violations:
        print(f"❌ references provenance gate 失敗（{len(violations)} 項）：")
        for v in violations[:30]:
            print(f"  - {v}")
        if len(violations) > 30:
            print(f"  ...（其餘 {len(violations) - 30} 項省略）")
        return 1
    print(
        f"✅ references provenance gate：{checked} 個型號 reference 結構完整、brand 對齊目錄"
        f"（corpus 側完整 bronze provenance 另由 audit_corpus.py 稽核）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
