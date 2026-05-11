"""一次性把 agent/product_info/*.md 匯入本機 PostgreSQL。

agent/product_info/ 是 mirror，DB 是 SoT。本腳本將 mega-doc 匯入 product_docs 表。
重跑為 idempotent — ON CONFLICT DO NOTHING 不會覆寫已存在 row。

跑法：
    cd agent && uv run python scripts/seed_product_docs_from_agent.py
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

# 讀專案根目錄 .env（與 agent v1 共用同一份）
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter。回傳 (meta, body)。

    複製貼上版本，不 import 套件本身以避免循環依賴。
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_block = m.group(1)
    body = text[m.end():]
    meta: dict = {}
    for line in meta_block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip().strip('"').strip("'")
        meta[k.strip()] = v
    return meta, body


def _scan_md_files(root: Path) -> list[dict]:
    """掃 agent/product_info/ 所有 .md 檔，回傳 row 字典清單。"""
    rows: list[dict] = []
    for md_path in sorted(root.rglob("*.md")):
        rel = md_path.relative_to(root)
        parts = rel.with_suffix("").parts
        if len(parts) != 2:
            continue
        brand, model_or_topic = parts
        text = md_path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        if brand == "_common":
            doc_brand = "_common"
            doc_model = None
            name = f"_common/{model_or_topic}"
        else:
            doc_brand = brand
            doc_model = model_or_topic
            name = f"{brand}/{model_or_topic}"
        rows.append({
            "name": name,
            "brand": doc_brand,
            "model": doc_model,
            "description": meta.get("description", "(no description)"),
            "body": body.strip(),
        })
    return rows


async def main() -> None:
    import psycopg

    uri = os.getenv("POSTGRES_URI")
    if not uri:
        print("ERROR: POSTGRES_URI 未設定（請檢查專案根目錄 .env）")
        sys.exit(1)

    # agent/product_info/ 路徑（從 agent/scripts/ 出發）
    project_root = Path(__file__).resolve().parents[2]
    source_dir = project_root / "agent" / "product_info"

    if not source_dir.exists():
        print(f"ERROR: 找不到來源目錄 {source_dir}")
        sys.exit(1)

    print("=" * 60)
    print("seed product_docs from agent/product_info/")
    print(f"來源: {source_dir}")
    print(f"DB:   {uri}")
    print("=" * 60)
    print()

    rows = _scan_md_files(source_dir)
    print(f"掃到 {len(rows)} 個 mega-doc")
    print()

    inserted = 0
    skipped = 0
    async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as conn:
        for row in rows:
            cur = await conn.execute(
                """
                INSERT INTO product_docs (name, brand, model, description, body, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING
                """,
                (
                    row["name"],
                    row["brand"],
                    row["model"],
                    row["description"],
                    row["body"],
                    "seed",
                ),
            )
            if cur.rowcount == 1:
                inserted += 1
                print(f"    + {row['name']}")
            else:
                skipped += 1

    print()
    print("=" * 60)
    print(f"✓ Seed 完成：inserted={inserted}, skipped (already exists)={skipped}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
