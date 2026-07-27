"""CR-0167 SkillSync 測試。

三層覆蓋：
1. 物化 + 原子 symlink swap + SkillsLoader overlay 覆蓋 builtin（hermetic，無 DB）。
2. fail-soft：未配置（缺 URI/tenant）→ enabled=False、start() 不 raise、不動 overlay。
3. DB 往返：stamp 輪詢 + published 拉取（需 POSTGRES_URI 指向含 migration 106 的 scratch 庫；
   未設則 skip——絕不對 UAT 庫跑）。
"""

from __future__ import annotations

import os
import uuid

import pytest

from lockcore.agent.context import ContextBuilder
from lockcore.agent import skill_sync as skill_sync_module
from lockcore.agent.skill_sync import SkillSync

_SKILL_MD = "---\nname: {n}\ndescription: 品牌自訂客服 SOP\n---\n\n品牌覆蓋內容 {marker}\n"


def _skill_files(name: str, marker: str) -> dict:
    return {"SKILL.md": _SKILL_MD.format(n=name, marker=marker),
            "references/note.md": f"ref {marker}"}


@pytest.mark.asyncio
async def test_materialize_overlays_builtin(tmp_path):
    """物化一個與 builtin 同名的 skill → SkillsLoader 讀到品牌版本（overlay 覆蓋）。"""
    sync = SkillSync(workspace=tmp_path, uri="x", tenant_id=str(uuid.uuid4()))
    sync._materialize({"locksmith-cs-sop": _skill_files("locksmith-cs-sop", "V1")})

    skills_link = tmp_path / "skills"
    assert skills_link.is_symlink()  # 原子 symlink 換裝
    assert (skills_link / "locksmith-cs-sop" / "SKILL.md").exists()
    assert (skills_link / "locksmith-cs-sop" / "references" / "note.md").exists()

    # SkillsLoader overlay：workspace/skills 覆蓋 builtin 同名
    cb = ContextBuilder(workspace=tmp_path)
    content = cb.skills.load_skill("locksmith-cs-sop")
    assert "品牌覆蓋內容 V1" in content
    # builtin locksmith-product-knowledge 仍在（未被覆蓋者照舊）
    names = {s["name"] for s in cb.skills.list_skills(filter_unavailable=False)}
    assert "locksmith-product-knowledge" in names


@pytest.mark.asyncio
async def test_atomic_reswap_updates_content(tmp_path):
    """二次物化：symlink 重指到新版本目錄，舊版本被 GC，內容更新。"""
    sync = SkillSync(workspace=tmp_path, uri="x", tenant_id=str(uuid.uuid4()))
    sync._materialize({"brand-faq": _skill_files("brand-faq", "V1")})
    sync._materialize({"brand-faq": _skill_files("brand-faq", "V2")})

    cb = ContextBuilder(workspace=tmp_path)
    assert "品牌覆蓋內容 V2" in cb.skills.load_skill("brand-faq")
    # 舊版本目錄應被 GC（只留現行）
    version_dirs = list(tmp_path.glob(".skills-v*"))
    assert len(version_dirs) == 1


@pytest.mark.asyncio
async def test_materialize_rejects_path_traversal(tmp_path):
    """二次防禦：非法路徑不落盤到 skill_root 之外。"""
    sync = SkillSync(workspace=tmp_path, uri="x", tenant_id=str(uuid.uuid4()))
    sync._materialize({"evil": {"SKILL.md": "ok", "../escape.md": "pwned"}})
    assert not (tmp_path / "escape.md").exists()
    assert not (tmp_path.parent / "escape.md").exists()


@pytest.mark.asyncio
async def test_materialize_rejects_skill_name_traversal(tmp_path):
    """skill_name 含 traversal（DB 讀回不盡信）→ 不落盤到 version_dir 之外。"""
    sync = SkillSync(workspace=tmp_path, uri="x", tenant_id=str(uuid.uuid4()))
    sync._materialize({"../evil": {"SKILL.md": "pwned"}})
    assert not (tmp_path.parent / "evil").exists()
    assert not (tmp_path.parent / "SKILL.md").exists()


@pytest.mark.asyncio
async def test_materialize_bad_skill_does_not_wedge_others(tmp_path):
    """單一壞 skill（路徑衝突）不得 wedge 整批——其餘 skill 照物化。"""
    sync = SkillSync(workspace=tmp_path, uri="x", tenant_id=str(uuid.uuid4()))
    sync._materialize({
        "bad": {"references": "x", "references/a.md": "y"},  # 檔案/目錄衝突
        "good": _skill_files("good", "OK"),
    })
    cb = ContextBuilder(workspace=tmp_path)
    assert "品牌覆蓋內容 OK" in cb.skills.load_skill("good")


@pytest.mark.asyncio
async def test_poll_interval_clamped(tmp_path):
    """poll_interval=0/負值 → clamp 到 ≥1（防連線風暴）。"""
    assert SkillSync(workspace=tmp_path, uri="x", tenant_id="t", poll_interval=0).poll_interval == 1
    assert SkillSync(workspace=tmp_path, uri="x", tenant_id="t", poll_interval=-5).poll_interval == 1


@pytest.mark.asyncio
async def test_disabled_when_unconfigured(tmp_path):
    """未配置 → enabled=False；start() fail-soft 不 raise、不建立 overlay。"""
    sync = SkillSync(workspace=tmp_path, uri=None, tenant_id=None)
    assert sync.enabled is False
    await sync.start()  # 不應 raise
    assert not (tmp_path / "skills").exists()


@pytest.mark.asyncio
async def test_connection_pool_is_reused_and_closed(monkeypatch, tmp_path):
    """SkillSync 每個 instance 只建一個 pool，stop 時釋放連線資源。"""
    created = []

    class FakePool:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.open_calls = []
            self.closed = False
            created.append(self)

        async def open(self, *, wait):
            self.open_calls.append(wait)

        async def close(self):
            self.closed = True

    monkeypatch.setattr(skill_sync_module, "AsyncConnectionPool", FakePool)
    sync = SkillSync(workspace=tmp_path, uri="postgresql://scratch", tenant_id="tenant")

    first = await sync._ensure_pool()
    second = await sync._ensure_pool()

    assert first is second
    assert len(created) == 1
    assert created[0].kwargs == {
        "conninfo": "postgresql://scratch",
        "min_size": 1,
        "max_size": 2,
        "timeout": 5,
        "kwargs": {"autocommit": True},
        "open": False,
    }
    assert created[0].open_calls == [False]

    await sync.stop()
    assert created[0].closed is True
    assert sync._pool is None


@pytest.mark.asyncio
async def test_builtin_roundtrip_byte_identical(tmp_path):
    """品質保證（CR-0167）：builtin skill 走 DB→SkillSync→SkillsLoader 後位元組級不變。

    防未來改動（seed/物化/loader）悄悄掉檔或改內容，害 agent 回答依據漂移。
    需 POSTGRES_URI（含 migration 106 的 scratch 庫）；未設則 skip。
    """
    uri = os.environ.get("POSTGRES_URI")
    if not uri:
        pytest.skip("需 POSTGRES_URI 指向 scratch 庫（含 migration 106）")

    import json
    import psycopg
    from lockcore.agent.skills import BUILTIN_SKILLS_DIR

    def _files(d):
        return {p.relative_to(d).as_posix(): p.read_bytes()
                for p in sorted(d.rglob("*")) if p.is_file()}

    tenant_id = str(uuid.uuid4())
    names = [d.name for d in sorted(BUILTIN_SKILLS_DIR.iterdir())
             if d.is_dir() and (d / "SKILL.md").exists()]
    assert names, "找不到 builtin skill"

    # seed builtin → DB（published）
    with psycopg.connect(uri, autocommit=True) as conn, conn.cursor() as cur:
        for name in names:
            files = {rel: b.decode("utf-8") for rel, b in _files(BUILTIN_SKILLS_DIR / name).items()}
            cur.execute(
                "INSERT INTO saas.skill_revision "
                "(tenant_id, skill_name, version, files, status, source) "
                "VALUES (%s::uuid,%s,1,%s::jsonb,'published','factory_seed')",
                (tenant_id, name, json.dumps(files, ensure_ascii=False)),
            )
        cur.execute("INSERT INTO saas.skill_bundle(tenant_id, published_stamp) VALUES (%s::uuid, 1)", (tenant_id,))

    sync = SkillSync(workspace=tmp_path, uri=uri, tenant_id=tenant_id, poll_interval=999)
    try:
        assert await sync._sync_once() is True

        # 逐檔位元組級比對 + SkillsLoader 內容等價
        mat_root = tmp_path / "skills"
        cb = ContextBuilder(workspace=tmp_path)
        for name in names:
            builtin = _files(BUILTIN_SKILLS_DIR / name)
            materialized = _files(mat_root / name)
            assert set(builtin) == set(materialized), f"{name} 物化檔集不一致（掉檔/多檔）"
            for rel in builtin:
                assert builtin[rel] == materialized[rel], f"{name}/{rel} 內容位元組不一致"
            # SkillsLoader 讀物化版 == builtin 原文
            assert cb.skills.load_skill(name) == (
                BUILTIN_SKILLS_DIR / name / "SKILL.md"
            ).read_text(encoding="utf-8")
    finally:
        await sync.stop()


@pytest.mark.asyncio
async def test_db_roundtrip_publish_then_sync(tmp_path):
    """DB 往返：直接寫 published revision + bump stamp，SkillSync 拉取物化。

    需 POSTGRES_URI 指向含 migration 106 的 scratch 庫；未設則 skip。
    """
    uri = os.environ.get("POSTGRES_URI")
    if not uri:
        pytest.skip("需 POSTGRES_URI 指向 scratch 庫（含 migration 106）")

    import psycopg

    tenant_id = str(uuid.uuid4())
    skill_name = "brand-sync-" + uuid.uuid4().hex[:6]
    import json
    files = _skill_files(skill_name, "FROM_DB")
    with psycopg.connect(uri, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO saas.skill_revision "
            "(tenant_id, skill_name, version, files, status, source) "
            "VALUES (%s::uuid,%s,1,%s::jsonb,'published','brand_edit')",
            (tenant_id, skill_name, json.dumps(files)),
        )
        cur.execute(
            "INSERT INTO saas.skill_bundle (tenant_id, published_stamp) VALUES (%s::uuid, 1)",
            (tenant_id,),
        )

    sync = SkillSync(workspace=tmp_path, uri=uri, tenant_id=tenant_id, poll_interval=999)
    try:
        changed = await sync._sync_once()
        assert changed is True
        cb = ContextBuilder(workspace=tmp_path)
        assert "FROM_DB" in cb.skills.load_skill(skill_name)

        # stamp 未變 → 第二次不換裝（no-op）
        assert await sync._sync_once() is False
    finally:
        await sync.stop()
