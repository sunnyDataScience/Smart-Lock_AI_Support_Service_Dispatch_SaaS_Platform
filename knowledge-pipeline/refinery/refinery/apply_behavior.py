"""行為軌落地 CLI — 把已核可的 behavior patch artifact 送進 skill（CR-0140 / CR-0168 LiveSkill）。

兩條落地路徑（依環境自動選）：
  A. **LiveSkill DB 汲取（預設，服務容器）**：設 LOCK_API_BASE_URL + INTERNAL_API_TOKEN 時，
     POST /internal/skills/ingest（merge=true）→ 品牌庫 **draft** → 品牌後台人工發佈 → ≤60s 生效。
     免重佈、免 repo checkout。**只進 draft，絕不 publish → 對 agent 回答品質零影響，
     須人工審核發佈後才生效**（HD-2）。
  B. **git 落檔（fallback，repo checkout）**：無 API 環境時，寫 refined 檔到 repo，人 git commit + 重佈（舊路徑）。

用法：
  REFINERY_TENANT_ID=<uuid> POSTGRES_URI=... \
  LOCK_API_BASE_URL=http://api:8001 INTERNAL_API_TOKEN=... \
    uv run python -m refinery.apply_behavior [--dry-run]

治理：
  - 只處理 status='approved' 且 provenance.published.kind='behavior_patch' 且未 applied 的 draft
  - 落地後標 provenance.published.applied=true（A 路徑記 skill/version，B 路徑記檔路徑）
"""

import argparse
import json
import os
from pathlib import Path

import httpx

from . import db

# publisher.behavior_patch_artifact 的 target_path 前綴（repo 內 skill 目錄根）
_SKILL_PREFIX = "agent/lockcore/skills/"


def _parse_skill_target(target_path: str) -> tuple[str, str] | None:
    """target_path → (skill_name, rel_path)；非 skill 路徑回 None（走 git fallback）。"""
    if not target_path.startswith(_SKILL_PREFIX):
        return None
    rest = target_path[len(_SKILL_PREFIX):]
    skill_name, _, rel_path = rest.partition("/")
    if not skill_name or not rel_path:
        return None
    return skill_name, rel_path


def _ingest_via_api(base: str, token: str, tenant: str, skill_name: str, rel_path: str,
                    content: str, note: str) -> dict:
    """POST /internal/skills/ingest（merge=true，加性）→ 回應 data（含 draft version）。"""
    resp = httpx.post(
        f"{base.rstrip('/')}/api/v1/internal/skills/ingest",
        headers={"X-Internal-Token": token},
        json={
            "tenant_id": tenant,
            "skill_name": skill_name,
            "files": {rel_path: content},
            "note": note,
            "merge": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="套用已核可的行為軌 patch")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", default=None, help="repo 根目錄（git fallback 用；測試可注入）")
    args = parser.parse_args(argv)

    tenant = db.tenant_id()
    api_base = os.environ.get("LOCK_API_BASE_URL")
    api_token = os.environ.get("INTERNAL_API_TOKEN")
    use_api = bool(api_base and api_token)
    # parents[3] = 專案根（本檔位於 knowledge-pipeline/refinery/refinery/）
    repo_root = Path(args.root) if args.root else Path(__file__).resolve().parents[3]
    applied = skipped = 0
    mode = "LiveSkill DB 汲取（draft）" if use_api else "git 落檔（fallback）"
    print(f"[apply] 落地路徑：{mode}")

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
        print(f"[apply] 待落地 behavior patch：{len(rows)} 筆")

        for draft_id, title, prov in rows:
            pub = prov["published"]
            target_path = pub["target_path"]
            parsed = _parse_skill_target(target_path) if use_api else None

            if use_api and parsed:
                skill_name, rel_path = parsed
                if args.dry_run:
                    print(f"[apply] (dry-run) #{draft_id}「{title}」→ ingest {skill_name}:{rel_path}（merge draft）")
                    applied += 1
                    continue
                try:
                    data = _ingest_via_api(
                        api_base, api_token, tenant, skill_name, rel_path, pub["content"],
                        note=f"refinery 行為軌 HITL 核可（draft #{draft_id}「{title}」）",
                    )
                except httpx.HTTPError as exc:
                    print(f"[apply] ✗ #{draft_id}「{title}」ingest 失敗（保留待重試）：{exc}")
                    skipped += 1
                    continue
                _mark_applied(cur, tenant, draft_id, {"kind": "behavior_patch", "applied": True,
                                                       "channel": "skill_ingest", "target_path": target_path,
                                                       "skill_name": skill_name, "draft_version": data.get("version")})
                conn.commit()
                print(f"[apply] ✅ #{draft_id}「{title}」→ {skill_name} draft v{data.get('version')}（待人工發佈）")
                applied += 1
                continue

            # ── git fallback ──
            target = repo_root / target_path
            if target.exists():
                print(f"[apply] ⚠ 跳過 #{draft_id}「{title}」：目標已存在（append-only）→ {target_path}")
                skipped += 1
                continue
            if args.dry_run:
                print(f"[apply] (dry-run) #{draft_id}「{title}」→ git {target_path}")
                applied += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(pub["content"], encoding="utf-8")
            _mark_applied(cur, tenant, draft_id, {"kind": "behavior_patch", "applied": True,
                                                  "channel": "git", "target_path": target_path})
            conn.commit()
            print(f"[apply] ✅ #{draft_id}「{title}」→ {target_path}")
            applied += 1

    print(f"[apply] 完成：{json.dumps({'applied': applied, 'skipped': skipped, 'mode': mode}, ensure_ascii=False)}")
    if applied and not args.dry_run and use_api:
        print("[apply] 已進品牌庫草稿。請至品牌後台『知識庫 > AI 技能』審核後發佈（發佈才生效）。")
    elif applied and not args.dry_run:
        print("[apply] 請 review 新檔並自行 git commit（skill 更新走 git 人審）。")
    return 0


def _mark_applied(cur, tenant: str, draft_id: int, patch: dict) -> None:
    """把 applied/channel 等併入既有 provenance.published（保留 kind/content/target_path 溯源）。"""
    cur.execute(
        """
        UPDATE knowledge_drafts
        SET provenance = jsonb_set(
                provenance, '{published}',
                COALESCE(provenance->'published', '{}'::jsonb) || %s::jsonb
            ),
            updated_at = now()
        WHERE tenant_id = %s AND id = %s
        """,
        (json.dumps(patch, ensure_ascii=False), tenant, draft_id),
    )


if __name__ == "__main__":
    raise SystemExit(main())
