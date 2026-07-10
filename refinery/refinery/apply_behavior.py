"""行為軌落檔 CLI — 把已核可的 behavior patch artifact 寫進 repo(CR-0140 D5)。

於 repo checkout 內執行(服務容器無 skills 檔案系統):
  REFINERY_TENANT_ID=<uuid> POSTGRES_URI=... \
    uv run python -m refinery.apply_behavior [--dry-run]

治理:
  - 只處理 status='approved' 且 provenance.published.kind='behavior_patch'
    且尚未標 applied 的 draft
  - append-only:目標檔已存在即跳過告警(絕不覆寫)
  - 落檔後標 provenance.published.applied=true;git commit 由人執行
    (符合「push 由使用者執行」慣例;CR-0140 §8-2)
"""

import argparse
import json
from pathlib import Path

from . import db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="套用已核可的行為軌 patch")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", default=None, help="repo 根目錄(預設自動推斷;測試用)")
    args = parser.parse_args(argv)

    tenant = db.tenant_id()
    repo_root = Path(args.root) if args.root else Path(__file__).resolve().parents[2]
    applied = skipped = 0

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, provenance
            FROM knowledge_drafts
            WHERE tenant_id = %s AND draft_type = 'behavior' AND status = 'approved'
              AND provenance->'published'->>'kind' = 'behavior_patch'
              AND COALESCE((provenance->'published'->>'applied')::boolean, FALSE) = FALSE
            ORDER BY reviewed_at
            """,
            (tenant,),
        )
        rows = cur.fetchall()
        print(f"[apply] 待落檔 behavior patch:{len(rows)} 筆")

        for draft_id, title, prov in rows:
            pub = prov["published"]
            target = repo_root / pub["target_path"]
            if target.exists():
                print(f"[apply] ⚠ 跳過 #{draft_id}「{title}」:目標已存在(append-only 不覆寫)→ {pub['target_path']}")
                skipped += 1
                continue
            if args.dry_run:
                print(f"[apply] (dry-run) #{draft_id}「{title}」→ {pub['target_path']}")
                applied += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(pub["content"], encoding="utf-8")
            cur.execute(
                """
                UPDATE knowledge_drafts
                SET provenance = jsonb_set(provenance, '{published,applied}', 'true'::jsonb),
                    updated_at = now()
                WHERE tenant_id = %s AND id = %s
                """,
                (tenant, draft_id),
            )
            conn.commit()
            print(f"[apply] ✅ #{draft_id}「{title}」→ {pub['target_path']}")
            applied += 1

    print(f"[apply] 完成:{json.dumps({'applied': applied, 'skipped': skipped}, ensure_ascii=False)}")
    if applied and not args.dry_run:
        print("[apply] 請 review 新檔並自行 git commit(skill 更新走 git 人審)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
