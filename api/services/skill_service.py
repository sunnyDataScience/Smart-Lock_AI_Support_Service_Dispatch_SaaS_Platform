"""Skill 熱更新業務邏輯（CR-0167 / LiveSkill）。

範圍：skill_revision 版控 CRUD + publish/rollback 狀態機 + 發佈驗證閘。
落庫：品牌庫 saas.skill_revision / saas.skill_bundle / saas.skill_audit_log。

狀態機（106-skill-revisions.sql）：
  draft ──publish──▶ published ──(新版 publish)──▶ retired
  rollback＝把舊 revision 重新 published（同機制，retire 當前 published）。

不變式：至多一個 published/(tenant,skill)——DB partial unique index 硬保證；
service 於同一 transaction 內先 retire 當前 published 再 publish 目標，避免違反。

發佈驗證閘（§5.6）：frontmatter 合規 + SKILL.md 存在且 ≤ 大小預算 +
skill_name/rel_path 合法（擋 path traversal）。draft 可暫存不合規內容，publish 才擋。
"""

from __future__ import annotations

import json as _json
import logging
import re

import psycopg
import yaml

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.skill_service")


async def _acquire_skill_lock(tenant_id: str, skill_name: str) -> None:
    """取 per-(tenant,skill) advisory xact-lock，序列化 save_draft/publish/rollback。

    CR-0167 review：check-then-insert 與 retire→publish 在 pool 啟用 + READ COMMITTED
    下並發會產生雙 draft、丟失發佈、或撞 unique index 裸 500。比照 audit_log_service
    的 hash-chain 鎖，用 xact-scoped advisory lock（commit/abort 自動釋放、與連線池相容）
    把同一 skill 的臨界區序列化。two-int 形式＝per-(tenant,skill) 粒度，不同 skill 不互擋。
    """
    await db_module._conn.execute("SET LOCAL lock_timeout = '3s'")
    await db_module._conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
        (tenant_id, skill_name),
    )

# ── 發佈驗證閘常數 ───────────────────────────────────────────────────────────
# SKILL.md 進 system prompt（每 turn），設大小預算避免 prompt 膨脹（references 走
# read_file 按需讀、不受此限）。16KB ≈ 5-6k 中文字，足夠一份 SOP。
_SKILL_MD_MAX_BYTES = 16 * 1024
# skill 目錄名＝ workspace/skills/<name>/：Agent Skills 標準 kebab-case，擋 path traversal
# \Z（非 $）：$ 會匹配結尾換行前，"foo\n" 會漏放行——用 \Z 鎖真正字串結尾（CR-0167 review）
_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")
# 檔案相對路徑：禁絕對路徑 / .. / 反斜線 / NUL，元件限白名單字元
_REL_PATH_SEG_RE = re.compile(r"^[A-Za-z0-9._-][A-Za-z0-9._ -]*\Z")


def validate_skill_name(skill_name: str) -> None:
    if not _SKILL_NAME_RE.match(skill_name or ""):
        raise ApiError(
            "INVALID_SKILL_NAME",
            "skill 名稱須為 kebab-case（a-z0-9-，開頭非 -，≤64 字元）",
            422,
        )


def _validate_rel_path(rel_path: str) -> None:
    """擋 path traversal：SkillSync 會把 files 的 key 當相對路徑落盤到 workspace。"""
    if not rel_path or rel_path.startswith("/") or "\\" in rel_path or "\x00" in rel_path:
        raise ApiError("INVALID_FILE_PATH", f"非法檔案路徑：{rel_path!r}", 422)
    segments = rel_path.split("/")
    for seg in segments:
        if seg in ("", ".", "..") or not _REL_PATH_SEG_RE.match(seg):
            raise ApiError("INVALID_FILE_PATH", f"非法檔案路徑元件：{rel_path!r}", 422)


def validate_publishable(skill_name: str, files: dict) -> None:
    """發佈閘：publish / rollback 前強制。draft 暫存不跑此閘（可存半成品）。"""
    validate_skill_name(skill_name)
    if not isinstance(files, dict) or not files:
        raise ApiError("EMPTY_SKILL", "skill 內容為空", 422)

    for rel_path, content in files.items():
        _validate_rel_path(rel_path)
        if not isinstance(content, str):
            raise ApiError("INVALID_FILE_CONTENT", f"檔案內容須為字串：{rel_path!r}", 422)

    _reject_path_collisions(files)

    skill_md = files.get("SKILL.md")
    if skill_md is None:
        raise ApiError("MISSING_SKILL_MD", "缺 SKILL.md（skill 進入點）", 422)
    if len(skill_md.encode("utf-8")) > _SKILL_MD_MAX_BYTES:
        raise ApiError(
            "SKILL_MD_TOO_LARGE",
            f"SKILL.md 超過大小預算（{_SKILL_MD_MAX_BYTES} bytes）；長知識請放 references/ 走 read_file",
            422,
        )
    _validate_frontmatter(skill_md)


def _reject_path_collisions(files: dict) -> None:
    """擋「一個路徑是另一個路徑的祖先」——如 files={"references":..., "references/x.md":...}。

    SkillSync 落盤時會先把 "references" 當檔案寫，再對 "references/x.md" mkdir("references/")
    → FileExistsError，卡死該 skill 的物化（CR-0167 review finding 5）。發佈前擋掉。
    """
    keys = list(files.keys())
    prefixes = {tuple(k.split("/")) for k in keys}
    for k in keys:
        parts = k.split("/")
        for i in range(1, len(parts)):
            if tuple(parts[:i]) in prefixes:
                raise ApiError(
                    "PATH_COLLISION",
                    f"檔案路徑衝突：{'/'.join(parts[:i])!r} 同時是檔案與目錄前綴",
                    422,
                )


def _validate_frontmatter(skill_md: str) -> None:
    """Agent Skills 標準 frontmatter：name + description 必填、YAML 可解析。"""
    if not skill_md.startswith("---"):
        raise ApiError("MISSING_FRONTMATTER", "SKILL.md 缺 YAML frontmatter（--- 開頭）", 422)
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?", skill_md, re.DOTALL)
    if not m:
        raise ApiError("MALFORMED_FRONTMATTER", "SKILL.md frontmatter 未正確閉合（--- 收尾）", 422)
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise ApiError("MALFORMED_FRONTMATTER", f"frontmatter YAML 解析失敗：{exc}", 422) from exc
    if not isinstance(meta, dict):
        raise ApiError("MALFORMED_FRONTMATTER", "frontmatter 非 key-value 結構", 422)
    for field in ("name", "description"):
        if not str(meta.get(field, "")).strip():
            raise ApiError("MISSING_FRONTMATTER_FIELD", f"frontmatter 缺必填欄位：{field}", 422)


# ── 讀取 ─────────────────────────────────────────────────────────────────────


def _revision_summary(row: tuple) -> dict:
    """(skill_name, latest_version, published_version, latest_status, latest_source, latest_updated)"""
    return {
        "skill_name": row[0],
        "latest_version": row[1],
        "published_version": row[2],
        "latest_status": row[3],
        "latest_source": row[4],
        "updated_at": row[5].isoformat() if row[5] else None,
    }


async def list_skills(*, tenant_id: str) -> dict:
    """每個 skill 一列：最新版本 / 目前發佈版本 / 狀態 / 來源。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        """
        SELECT r.skill_name,
               MAX(r.version)                                              AS latest_version,
               MAX(r.version) FILTER (WHERE r.status = 'published')        AS published_version,
               (ARRAY_AGG(r.status ORDER BY r.version DESC))[1]            AS latest_status,
               (ARRAY_AGG(r.source ORDER BY r.version DESC))[1]           AS latest_source,
               MAX(r.created_at)                                          AS updated_at
          FROM saas.skill_revision r
         WHERE r.tenant_id = %s::uuid
         GROUP BY r.skill_name
         ORDER BY r.skill_name
        """,
        (tenant_id,),
    )
    rows = await cur.fetchall()
    return {"items": [_revision_summary(r) for r in rows]}


async def get_skill(*, tenant_id: str, skill_name: str, version: int | None = None) -> dict:
    """取指定 version（None＝最新版本，不論狀態）的檔案樹。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    validate_skill_name(skill_name)
    if version is None:
        cur = await db_module._conn.execute(
            "SELECT version, files, status, source, note, created_at, published_at "
            "FROM saas.skill_revision "
            "WHERE tenant_id = %s::uuid AND skill_name = %s "
            "ORDER BY version DESC LIMIT 1",
            (tenant_id, skill_name),
        )
    else:
        cur = await db_module._conn.execute(
            "SELECT version, files, status, source, note, created_at, published_at "
            "FROM saas.skill_revision "
            "WHERE tenant_id = %s::uuid AND skill_name = %s AND version = %s",
            (tenant_id, skill_name, version),
        )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Skill not found", 404)
    return {
        "skill_name": skill_name,
        "version": row[0],
        "files": row[1],
        "status": row[2],
        "source": row[3],
        "note": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
        "published_at": row[6].isoformat() if row[6] else None,
    }


async def list_revisions(*, tenant_id: str, skill_name: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    validate_skill_name(skill_name)
    cur = await db_module._conn.execute(
        "SELECT version, status, source, note, created_by, created_at, published_at "
        "FROM saas.skill_revision "
        "WHERE tenant_id = %s::uuid AND skill_name = %s "
        "ORDER BY version DESC",
        (tenant_id, skill_name),
    )
    rows = await cur.fetchall()
    return {
        "items": [
            {
                "version": r[0],
                "status": r[1],
                "source": r[2],
                "note": r[3],
                "created_by": str(r[4]) if r[4] else None,
                "created_at": r[5].isoformat() if r[5] else None,
                "published_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]
    }


# ── 寫入 ─────────────────────────────────────────────────────────────────────


async def _next_version(tenant_id: str, skill_name: str) -> int:
    cur = await db_module._conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM saas.skill_revision "
        "WHERE tenant_id = %s::uuid AND skill_name = %s",
        (tenant_id, skill_name),
    )
    return (await cur.fetchone())[0]


async def save_draft(
    *,
    tenant_id: str,
    skill_name: str,
    files: dict,
    note: str | None = None,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    source: str = "brand_edit",
) -> dict:
    """存草稿：at-most-one draft/(tenant,skill)——有 draft 則覆蓋，否則新開版本號。

    draft 暫存不跑發佈閘（可存半成品），但 skill_name / rel_path 仍驗（擋落盤攻擊）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    validate_skill_name(skill_name)
    if not isinstance(files, dict) or not files:
        raise ApiError("EMPTY_SKILL", "skill 內容為空", 422)
    for rel_path, content in files.items():
        _validate_rel_path(rel_path)
        if not isinstance(content, str):
            raise ApiError("INVALID_FILE_CONTENT", f"檔案內容須為字串：{rel_path!r}", 422)

    files_json = _json.dumps(files, ensure_ascii=False)
    try:
        async with db_module._conn.transaction():
            # advisory lock 序列化同一 skill 的 check-then-insert（pool + READ COMMITTED
            # 下無 gap lock，兩並發都讀「無 draft」會產生雙 draft/version 撞 unique）
            await _acquire_skill_lock(tenant_id, skill_name)
            cur = await db_module._conn.execute(
                "SELECT version FROM saas.skill_revision "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND status = 'draft' "
                "ORDER BY version DESC LIMIT 1 FOR UPDATE",
                (tenant_id, skill_name),
            )
            existing = await cur.fetchone()
            if existing:
                version = existing[0]
                await db_module._conn.execute(
                    "UPDATE saas.skill_revision "
                    "SET files = %s::jsonb, note = %s, source = %s, created_at = NOW(), "
                    "    created_by = %s::uuid "
                    "WHERE tenant_id = %s::uuid AND skill_name = %s AND version = %s",
                    (files_json, note, source, actor_user_id, tenant_id, skill_name, version),
                )
                action = "update_draft"
            else:
                version = await _next_version(tenant_id, skill_name)
                await db_module._conn.execute(
                    "INSERT INTO saas.skill_revision "
                    "  (tenant_id, skill_name, version, files, status, source, note, created_by) "
                    "VALUES (%s::uuid, %s, %s, %s::jsonb, 'draft', %s, %s, %s::uuid)",
                    (tenant_id, skill_name, version, files_json, source, note, actor_user_id),
                )
                action = "create_draft"
    except psycopg.errors.UniqueViolation:
        # advisory lock 已序列化正常路徑；仍撞 unique＝極端並發殘餘 → 乾淨 409 非裸 500
        raise ApiError("DRAFT_CONFLICT", "草稿並發衝突，請重新載入後再存", 409) from None

    await _write_audit(
        tenant_id, skill_name, action, version, None,
        {"files": list(files.keys()), "source": source}, actor_user_id, actor_role,
    )
    return {"skill_name": skill_name, "version": version, "status": "draft"}


async def publish(
    *,
    tenant_id: str,
    skill_name: str,
    version: int,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> dict:
    """發佈：驗證閘 → retire 當前 published → 目標 published → bump stamp（單一交易）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    validate_skill_name(skill_name)

    try:
        async with db_module._conn.transaction():
            # 序列化同一 skill 的 publish/rollback：並發發佈兩個不同版本會在 retire→publish
            # 之間各自漏 retire、撞 uq_skill_revision_published 裸 500（CR-0167 review finding 2）
            await _acquire_skill_lock(tenant_id, skill_name)
            cur = await db_module._conn.execute(
                "SELECT files, status FROM saas.skill_revision "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND version = %s FOR UPDATE",
                (tenant_id, skill_name, version),
            )
            row = await cur.fetchone()
            if not row:
                raise ApiError("NOT_FOUND", "Skill revision not found", 404)
            files, status = row[0], row[1]
            if status == "published":
                raise ApiError("ALREADY_PUBLISHED", "此版本已是發佈中版本", 409)

            validate_publishable(skill_name, files)  # 發佈閘（在交易內，失敗自動 rollback）

            # 先 retire 當前 published，避免撞 partial unique index
            await db_module._conn.execute(
                "UPDATE saas.skill_revision SET status = 'retired' "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND status = 'published'",
                (tenant_id, skill_name),
            )
            await db_module._conn.execute(
                "UPDATE saas.skill_revision SET status = 'published', published_at = NOW() "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND version = %s",
                (tenant_id, skill_name, version),
            )
            stamp = await _bump_stamp(tenant_id)
    except psycopg.errors.UniqueViolation:
        raise ApiError("PUBLISH_CONFLICT", "並發發佈衝突，請重試", 409) from None

    await _write_audit(
        tenant_id, skill_name, "publish", version, None,
        {"published_stamp": stamp}, actor_user_id, actor_role,
    )
    return {"skill_name": skill_name, "version": version, "status": "published", "published_stamp": stamp}


async def rollback(
    *,
    tenant_id: str,
    skill_name: str,
    target_version: int,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> dict:
    """回滾：把舊 version 重新設為 published（同 publish 機制，含發佈閘）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    validate_skill_name(skill_name)

    try:
        async with db_module._conn.transaction():
            await _acquire_skill_lock(tenant_id, skill_name)
            cur = await db_module._conn.execute(
                "SELECT files, status FROM saas.skill_revision "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND version = %s FOR UPDATE",
                (tenant_id, skill_name, target_version),
            )
            row = await cur.fetchone()
            if not row:
                raise ApiError("NOT_FOUND", "Skill revision not found", 404)
            files, status = row[0], row[1]
            if status == "published":
                raise ApiError("ALREADY_PUBLISHED", "此版本已是發佈中版本", 409)
            validate_publishable(skill_name, files)

            await db_module._conn.execute(
                "UPDATE saas.skill_revision SET status = 'retired' "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND status = 'published'",
                (tenant_id, skill_name),
            )
            await db_module._conn.execute(
                "UPDATE saas.skill_revision SET status = 'published', published_at = NOW() "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND version = %s",
                (tenant_id, skill_name, target_version),
            )
            stamp = await _bump_stamp(tenant_id)
    except psycopg.errors.UniqueViolation:
        raise ApiError("PUBLISH_CONFLICT", "並發發佈衝突，請重試", 409) from None

    await _write_audit(
        tenant_id, skill_name, "rollback", target_version, None,
        {"published_stamp": stamp}, actor_user_id, actor_role,
    )
    return {"skill_name": skill_name, "version": target_version, "status": "published", "published_stamp": stamp}


async def ingest_revision(
    *,
    tenant_id: str,
    skill_name: str,
    files: dict,
    note: str | None = None,
) -> dict:
    """knowledge-pipeline 自動汲取通道（HD-2=a：一律進 draft，人工發佈）。"""
    return await save_draft(
        tenant_id=tenant_id,
        skill_name=skill_name,
        files=files,
        note=note or "pipeline 自動汲取",
        actor_user_id=None,
        actor_role="pipeline",
        source="pipeline_ingest",
    )


async def _bump_stamp(tenant_id: str) -> int:
    cur = await db_module._conn.execute(
        "INSERT INTO saas.skill_bundle (tenant_id, published_stamp, updated_at) "
        "VALUES (%s::uuid, 1, NOW()) "
        "ON CONFLICT (tenant_id) DO UPDATE "
        "  SET published_stamp = saas.skill_bundle.published_stamp + 1, updated_at = NOW() "
        "RETURNING published_stamp",
        (tenant_id,),
    )
    return (await cur.fetchone())[0]


async def _write_audit(
    tenant_id: str,
    skill_name: str,
    action: str,
    revision_version: int | None,
    before_state: dict | None,
    after_state: dict | None,
    actor_user_id: str | None,
    actor_role: str | None,
) -> None:
    """best-effort：audit 失敗不阻擋主操作（比照 kb_v2._write_audit_log）。"""
    try:
        await db_module._conn.execute(
            "INSERT INTO saas.skill_audit_log "
            "  (tenant_id, skill_name, action, revision_version, "
            "   before_state, after_state, actor_user_id, actor_role) "
            "VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, %s::uuid, %s)",
            (
                tenant_id,
                skill_name,
                action,
                revision_version,
                _json.dumps(before_state, ensure_ascii=False) if before_state is not None else None,
                _json.dumps(after_state, ensure_ascii=False) if after_state is not None else None,
                actor_user_id,
                actor_role,
            ),
        )
    except Exception:
        logger.warning("skill_audit_log write failed (non-fatal)", exc_info=True)
