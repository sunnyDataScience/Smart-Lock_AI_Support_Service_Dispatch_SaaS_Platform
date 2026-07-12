"""把 image builtin skills seed 進品牌庫（CR-0167 factory_seed）。

用途：讓品牌後台能「檢視/編輯/fork」出廠 skill（locksmith-cs-sop /
locksmith-product-knowledge）。把 lockcore/skills/<name>/ 的 SKILL.md ＋ references/**
讀成 files dict，寫入 saas.skill_revision 為 draft（source=factory_seed，version=1）。

冪等：已存在同 skill 的 factory_seed revision → 略過（不覆蓋品牌已編輯的內容）。
seed 為 draft 而非 published——品牌自行決定要不要發佈（發佈才會蓋掉 image builtin
的同名 overlay；不發佈則 agent 續用 image builtin，行為不變）。

用法：
    POSTGRES_URI=<品牌庫> AGENT_TENANT_ID=<租戶UUID> \
        uv run python scripts/seed_builtin_skills.py
    # 或指定 skill：... seed_builtin_skills.py locksmith-cs-sop
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg

from lockcore.agent.skills import BUILTIN_SKILLS_DIR

# SKILL.md 進 prompt 有大小預算；seed 只把「進 DB」的 references 也帶上（read_file 按需讀）。
_MAX_FILE_BYTES = 512 * 1024  # 單檔上限，避免異常大檔灌爆 jsonb


def _collect_files(skill_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            print(f"  略過非文字/不可讀檔：{rel}")
            continue
        if len(content.encode("utf-8")) > _MAX_FILE_BYTES:
            print(f"  略過過大檔（>{_MAX_FILE_BYTES}B）：{rel}")
            continue
        files[rel] = content
    return files


def _seed_skill(conn: psycopg.Connection, tenant_id: str, skill_name: str, files: dict) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM saas.skill_revision "
            "WHERE tenant_id = %s::uuid AND skill_name = %s AND source = 'factory_seed' LIMIT 1",
            (tenant_id, skill_name),
        )
        if cur.fetchone():
            return "skipped (already seeded)"
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM saas.skill_revision "
            "WHERE tenant_id = %s::uuid AND skill_name = %s",
            (tenant_id, skill_name),
        )
        version = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO saas.skill_revision "
            "  (tenant_id, skill_name, version, files, status, source, note) "
            "VALUES (%s::uuid, %s, %s, %s::jsonb, 'draft', 'factory_seed', %s)",
            (tenant_id, skill_name, version, json.dumps(files, ensure_ascii=False),
             "出廠範本（可編輯後發佈）"),
        )
    return f"seeded v{version}（{len(files)} 檔）"


def main() -> None:
    uri = os.environ.get("POSTGRES_URI")
    tenant_id = (
        os.environ.get("SKILL_SYNC_TENANT_ID")
        or os.environ.get("AGENT_TENANT_ID")
        or os.environ.get("RAG_TENANT_ID")
    )
    if not uri or not tenant_id:
        sys.exit("缺 POSTGRES_URI 或 tenant UUID（AGENT_TENANT_ID / SKILL_SYNC_TENANT_ID）")

    only = sys.argv[1] if len(sys.argv) > 1 else None
    skill_dirs = [
        d for d in sorted(BUILTIN_SKILLS_DIR.iterdir())
        if d.is_dir() and (d / "SKILL.md").exists() and (only is None or d.name == only)
    ]
    if not skill_dirs:
        sys.exit(f"BUILTIN_SKILLS_DIR 下找不到 skill{f'（{only}）' if only else ''}：{BUILTIN_SKILLS_DIR}")

    with psycopg.connect(uri, autocommit=True) as conn:
        for d in skill_dirs:
            files = _collect_files(d)
            result = _seed_skill(conn, tenant_id, d.name, files)
            print(f"[{d.name}] {result}")
    print("factory seed 完成。")


if __name__ == "__main__":
    main()
