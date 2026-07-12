"""Skill 熱更新 router（CR-0167 / LiveSkill）—— 品牌後台 skill 版控與發佈。

掛載：/api/v1 prefix（與 knowledge-base 家族 kb_cases / kb_manuals / sop_drafts 同）。
surface：dispatch/all（品牌面）；tech/platform surface 由路由過濾自動排除。

角色閘（HD-5=a）：
  編輯（listSkills/getSkill/saveSkillDraft/listRevisions）＝ OPS_ROLES
  發佈（publishSkill/rollbackSkill）＝ admin（FULL_ACCESS_ROLES）
  自動汲取（ingestSkillRevision）＝ INTERNAL_API_TOKEN（knowledge-pipeline 用）

讀取端點也用 OPS_ROLES（非純 require_tenant）：skill 是 agent 回答依據，
內容治理層級對齊 config/audit，不對一般客服開放唯讀。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field

from core.deps import (
    FULL_ACCESS_ROLES,
    OPS_ROLES,
    CurrentUser,
    require_internal_token,
    role_required,
)
from services import skill_service

router = APIRouter()


# ── request bodies ───────────────────────────────────────────────────────────


class SaveDraftRequest(BaseModel):
    # files: { rel_path: content }，須含 SKILL.md（發佈時強制；存草稿放寬）
    files: dict[str, str] = Field(..., description="檔案樹 {相對路徑: 內容}，含 SKILL.md 與 references/*")
    note: str | None = Field(default=None, description="版本備註")


class PublishRequest(BaseModel):
    version: int = Field(..., ge=1, description="要發佈的版本號")


class RollbackRequest(BaseModel):
    target_version: int = Field(..., ge=1, description="要回滾到的版本號")


class IngestRequest(BaseModel):
    tenant_id: str = Field(..., description="租戶 UUID")
    skill_name: str = Field(..., description="skill 目錄名（kebab-case）")
    files: dict[str, str]
    note: str | None = None
    # merge=True：只送新增/更新檔，後端讀現有基準併入（refinery 行為軌加單一 refined reference）
    merge: bool = Field(default=False, description="加性合併進現有 skill（保留既有檔，只新增/更新）")


def _envelope(data: dict) -> dict:
    return {"data": data, "error": None}


# ── 讀取（OPS_ROLES）─────────────────────────────────────────────────────────


@router.get(
    "/knowledge-base/skills",
    operation_id="listSkills",
    summary="AI 技能列表（每 skill 最新/發佈版本＋狀態）",
    tags=["knowledge_base"],
)
async def list_skills(
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    result = await skill_service.list_skills(tenant_id=user.tenant_id)
    return _envelope(result)


@router.get(
    "/knowledge-base/skills/{name}",
    operation_id="getSkill",
    summary="取得 skill 檔案樹（預設最新版本，可指定 version）",
    tags=["knowledge_base"],
)
async def get_skill(
    name: str = Path(),
    version: int | None = Query(default=None, ge=1),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    result = await skill_service.get_skill(
        tenant_id=user.tenant_id, skill_name=name, version=version
    )
    return _envelope(result)


@router.get(
    "/knowledge-base/skills/{name}/revisions",
    operation_id="listSkillRevisions",
    summary="skill 版本歷史（diff / rollback 選單）",
    tags=["knowledge_base"],
)
async def list_skill_revisions(
    name: str = Path(),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    result = await skill_service.list_revisions(tenant_id=user.tenant_id, skill_name=name)
    return _envelope(result)


# ── 編輯（OPS_ROLES）─────────────────────────────────────────────────────────


@router.put(
    "/knowledge-base/skills/{name}",
    operation_id="saveSkillDraft",
    summary="存 skill 草稿（at-most-one draft/skill，覆蓋既有草稿）",
    tags=["knowledge_base"],
)
async def save_skill_draft(
    body: SaveDraftRequest,
    name: str = Path(),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    result = await skill_service.save_draft(
        tenant_id=user.tenant_id,
        skill_name=name,
        files=body.files,
        note=body.note,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return _envelope(result)


# ── 發佈 / 回滾（admin）──────────────────────────────────────────────────────


@router.post(
    "/knowledge-base/skills/{name}/publish",
    operation_id="publishSkill",
    summary="發佈 skill 版本（驗證閘＋bump stamp→SkillSync 60s 內生效）",
    status_code=status.HTTP_200_OK,
    tags=["knowledge_base"],
)
async def publish_skill(
    body: PublishRequest,
    name: str = Path(),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    result = await skill_service.publish(
        tenant_id=user.tenant_id,
        skill_name=name,
        version=body.version,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return _envelope(result)


@router.post(
    "/knowledge-base/skills/{name}/rollback",
    operation_id="rollbackSkill",
    summary="回滾至指定 skill 版本（重新發佈舊版本）",
    status_code=status.HTTP_200_OK,
    tags=["knowledge_base"],
)
async def rollback_skill(
    body: RollbackRequest,
    name: str = Path(),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    result = await skill_service.rollback(
        tenant_id=user.tenant_id,
        skill_name=name,
        target_version=body.target_version,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return _envelope(result)


# ── 自動汲取（INTERNAL_API_TOKEN）────────────────────────────────────────────


@router.post(
    "/internal/skills/ingest",
    operation_id="ingestSkillRevision",
    summary="內部：knowledge-pipeline 汲取 skill 為 draft（HD-2：人工發佈）",
    tags=["internal"],
)
async def ingest_skill_revision(
    body: IngestRequest,
    _auth: None = Depends(require_internal_token),
) -> dict:
    result = await skill_service.ingest_revision(
        tenant_id=body.tenant_id,
        skill_name=body.skill_name,
        files=body.files,
        note=body.note,
        merge=body.merge,
    )
    return _envelope(result)
