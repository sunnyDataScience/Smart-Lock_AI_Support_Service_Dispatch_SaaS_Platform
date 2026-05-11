"""把 product_docs 表的內容匯出回 agent/product_info/{Brand}/{Model}.md mirror。

用途：
- DB 是 source of truth，但 git 上保留可讀 mirror（方便 review、PR diff、新人查閱）
- 任何 DB 寫入後（透過 admin API、update_product_doc.py 等）都可跑這支同步 mirror

行為：
- 對每筆 product_docs row 寫一份 .md（含 frontmatter）到 agent/product_info/{name}.md
- name = "Dormakaba/AS850" → product_info/Dormakaba/AS850.md
- name = "_common/dispatch" → product_info/_common/dispatch.md
- 若 mirror 已存在且內容一致則跳過（不更新 mtime）
- 預設刪掉 DB 已不存在的 mirror 檔（孤兒）— 加 --no-prune 保留

跑法：
    cd agent
    uv run python scripts/sync_product_info_from_db.py --dry-run
    uv run python scripts/sync_product_info_from_db.py
    uv run python scripts/sync_product_info_from_db.py --no-prune  # 不刪 DB 沒有的孤兒檔
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")


MIRROR_ROOT = Path(__file__).resolve().parent.parent / "product_info"


def render_doc(name: str, brand: str, model: str | None, description: str, body: str) -> str:
    """組 frontmatter + body。

    格式對齊既有 agent/product_info/ 慣例：
    - 有 model 才寫 model 行（_common/* 通常沒寫）
    - description 用雙引號包
    """
    desc_escaped = description.replace('"', '\\"')
    fm_lines = ["---", f"brand: {brand}"]
    if model:
        fm_lines.append(f"model: {model}")
    fm_lines.append(f'description: "{desc_escaped}"')
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append(body.rstrip())
    fm_lines.append("")
    return "\n".join(fm_lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-prune", action="store_true", help="不刪 DB 已不存在的 mirror 檔")
    args = parser.parse_args()

    import psycopg

    uri = os.getenv("POSTGRES_URI")
    if not uri:
        print("ERROR: POSTGRES_URI 未設定")
        return

    async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT name, brand, model, description, body FROM product_docs ORDER BY brand, name"
            )
            rows = await cur.fetchall()

    print(f"DB 共 {len(rows)} 份 doc")
    if not rows:
        print("（無資料，跳過）")
        return

    written = 0
    skipped_same = 0
    db_names: set[str] = set()

    for name, brand, model, description, body in rows:
        db_names.add(name)
        target = MIRROR_ROOT / f"{name}.md"
        rendered = render_doc(name, brand, model, description, body)

        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            skipped_same += 1
            continue

        if args.dry_run:
            print(f"  [dry-run] WRITE {name}.md ({len(body)} body chars)")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        written += 1
        print(f"  ✓ {name}.md")

    print(f"\n寫入 {written}、無變化跳過 {skipped_same}")

    # Prune 孤兒檔（DB 已沒有但 mirror 還在）
    if not args.no_prune:
        pruned = 0
        if MIRROR_ROOT.exists():
            for md_path in MIRROR_ROOT.rglob("*.md"):
                rel = md_path.relative_to(MIRROR_ROOT).with_suffix("")
                doc_name = "/".join(rel.parts)
                if doc_name not in db_names:
                    if args.dry_run:
                        print(f"  [dry-run] DELETE 孤兒 {doc_name}.md")
                    else:
                        md_path.unlink()
                        print(f"  ✗ 刪 {doc_name}.md (DB 已無)")
                    pruned += 1
        if pruned:
            print(f"刪除孤兒檔 {pruned} 份")


if __name__ == "__main__":
    asyncio.run(main())
