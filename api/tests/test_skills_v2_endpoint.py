"""CR-0167 skill 熱更新端點整合測試。

覆蓋：save draft → publish（admin）→ list/get → 版本迭代 → rollback → revisions；
發佈驗證閘（缺 SKILL.md / 缺 frontmatter / 過大 / path traversal）；角色閘（ops 不能發佈、
technician 不能編輯）；stamp 遞增（SkillSync 變更偵測基礎）。

DB：需 POSTGRES_URI 指向 scratch 庫（含 migration 106）；conftest 不 mock，走真連線。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID, _make_token

pytestmark = pytest.mark.asyncio


def _ops_headers() -> dict:
    tok = _make_token(user_id=str(uuid.uuid4()), role="operations_manager")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-ID": DEFAULT_TENANT_ID}


def _tech_headers() -> dict:
    tok = _make_token(user_id=str(uuid.uuid4()), role="technician")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-ID": DEFAULT_TENANT_ID}


def _skill_md(name: str, desc: str = "測試技能", body: str = "內容") -> str:
    return f"---\nname: {name}\ndescription: {desc}\nversion: 1.0.0\n---\n\n{body}\n"


def _unique_name() -> str:
    return "test-skill-" + uuid.uuid4().hex[:8]


async def test_full_lifecycle_save_publish_rollback(client):
    name = _unique_name()
    ops, admin = _ops_headers(), _admin_headers()

    # 1) ops 存草稿 v1
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name, body="第一版")}, "note": "初版"},
        headers=ops,
    )
    assert r.status_code == 200, r.text
    v1 = r.json()["data"]["version"]
    assert r.json()["data"]["status"] == "draft"

    # 2) admin 發佈 v1
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish",
        json={"version": v1}, headers=admin,
    )
    assert r.status_code == 200, r.text
    stamp1 = r.json()["data"]["published_stamp"]
    assert r.json()["data"]["status"] == "published"

    # 3) list 顯示 published_version
    r = await client.get("/api/v1/knowledge-base/skills", headers=ops)
    assert r.status_code == 200
    row = next(x for x in r.json()["data"]["items"] if x["skill_name"] == name)
    assert row["published_version"] == v1

    # 4) get 最新版本回 published 內容
    r = await client.get(f"/api/v1/knowledge-base/skills/{name}", headers=ops)
    assert r.status_code == 200
    assert "第一版" in r.json()["data"]["files"]["SKILL.md"]
    assert r.json()["data"]["status"] == "published"

    # 5) 存草稿 v2（有 published 在，save 開新版本）
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name, body="第二版")}}, headers=ops,
    )
    assert r.status_code == 200, r.text
    v2 = r.json()["data"]["version"]
    assert v2 > v1

    # 6) 發佈 v2 → stamp 遞增
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish",
        json={"version": v2}, headers=admin,
    )
    assert r.status_code == 200, r.text
    stamp2 = r.json()["data"]["published_stamp"]
    assert stamp2 == stamp1 + 1  # SkillSync 變更偵測依賴此遞增

    # 7) 回滾到 v1（admin）
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/rollback",
        json={"target_version": v1}, headers=admin,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["published_stamp"] == stamp2 + 1

    # 8) 現在 published 版本應回到 v1 的內容
    r = await client.get(f"/api/v1/knowledge-base/skills/{name}", headers=ops)
    files = r.json()["data"]["files"]
    # get 回最新 version（v2，狀態現為 retired）—— 明確查 published 版本用 revisions 判斷
    r2 = await client.get(f"/api/v1/knowledge-base/skills/{name}/revisions", headers=ops)
    revs = {x["version"]: x for x in r2.json()["data"]["items"]}
    assert revs[v1]["status"] == "published"
    assert revs[v2]["status"] == "retired"


async def test_publish_gate_rejects_missing_skill_md(client):
    name = _unique_name()
    ops, admin = _ops_headers(), _admin_headers()
    # 存草稿（只有 references，無 SKILL.md）—— draft 放行
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"references/a.md": "some ref"}}, headers=ops,
    )
    assert r.status_code == 200, r.text
    v = r.json()["data"]["version"]
    # 發佈被閘擋
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish",
        json={"version": v}, headers=admin,
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "MISSING_SKILL_MD"


async def test_publish_gate_rejects_bad_frontmatter(client):
    name = _unique_name()
    ops, admin = _ops_headers(), _admin_headers()
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": "no frontmatter here"}}, headers=ops,
    )
    v = r.json()["data"]["version"]
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish",
        json={"version": v}, headers=admin,
    )
    assert r.status_code == 422
    assert r.json()["error_code"] in ("MISSING_FRONTMATTER", "MALFORMED_FRONTMATTER")


async def test_save_rejects_path_traversal(client):
    name = _unique_name()
    ops = _ops_headers()
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"../../etc/passwd": "x", "SKILL.md": _skill_md(name)}}, headers=ops,
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "INVALID_FILE_PATH"


async def test_save_accepts_builtin_real_filenames(client):
    """回歸:出廠 references 實檔名(中文/括號/加號)須可存草稿與發佈。

    曾為 ASCII 白名單把 Kaadas 中文型號檔、3E「F(T7).md」、Milre「7150+.md」
    擋掉;seed 直 SQL 繞過驗證入庫 → 品牌後台對產品知識庫「存草稿/發佈」全
    422(整樹 PUT 撞驗證閘),違反 CR-0167 HD-1 品牌完整編輯權。
    """
    name = _unique_name()
    ops, admin = _ops_headers(), _admin_headers()
    files = {
        "SKILL.md": _skill_md(name),
        "references/Kaadas/藍寶堅尼3D人臉辨識.md": "# Kaadas 藍寶堅尼\n內容",
        "references/3E/F(T7).md": "# 3E F(T7)\n內容",
        "references/Milre/7150+.md": "# Milre 7150+\n內容",
    }
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": files}, headers=ops,
    )
    assert r.status_code == 200, r.text
    v = r.json()["data"]["version"]
    # 發佈閘同樣須放行(validate_publishable 也跑 _validate_rel_path)
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish",
        json={"version": v}, headers=admin,
    )
    assert r.status_code == 200, r.text


async def test_save_still_rejects_dangerous_chars(client):
    """黑名單制放寬後,控制字元與危險符號仍須擋(每個獨立驗證)。"""
    ops = _ops_headers()
    bad_paths = [
        "references/a?.md",       # 萬用字元
        "references/a*.md",       # 萬用字元
        "references/a:b.md",      # Windows 磁碟分隔
        "references/a\nb.md",     # 控制字元(換行,亦擋 \Z 結尾繞過)
        "references/<a>.md",      # 重導向符
    ]
    for bad in bad_paths:
        name = _unique_name()
        r = await client.put(
            f"/api/v1/knowledge-base/skills/{name}",
            json={"files": {bad: "x", "SKILL.md": _skill_md(name)}}, headers=ops,
        )
        assert r.status_code == 422, f"{bad!r} 未被擋: {r.status_code}"
        assert r.json()["error_code"] == "INVALID_FILE_PATH", bad


async def test_invalid_skill_name_rejected(client):
    ops = _ops_headers()
    r = await client.put(
        "/api/v1/knowledge-base/skills/Bad_Name!",
        json={"files": {"SKILL.md": _skill_md("x")}}, headers=ops,
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "INVALID_SKILL_NAME"


async def test_role_gate_ops_cannot_publish(client):
    name = _unique_name()
    ops = _ops_headers()
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name)}}, headers=ops,
    )
    v = r.json()["data"]["version"]
    # ops 嘗試發佈 → 403（發佈限 admin）
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish",
        json={"version": v}, headers=ops,
    )
    assert r.status_code == 403


async def test_role_gate_technician_cannot_edit(client):
    name = _unique_name()
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name)}}, headers=_tech_headers(),
    )
    assert r.status_code == 403


async def test_publish_gate_rejects_path_collision(client):
    """一路徑是另一路徑祖先（會 wedge SkillSync 物化）→ 發佈閘擋。"""
    name = _unique_name()
    ops, admin = _ops_headers(), _admin_headers()
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name), "references": "x",
                        "references/a.md": "y"}}, headers=ops,
    )
    v = r.json()["data"]["version"]
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish", json={"version": v}, headers=admin,
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "PATH_COLLISION"


async def test_skill_name_trailing_newline_rejected(client):
    """\\Z（非 $）：結尾換行不得被放行（正規化繞過）。"""
    ops = _ops_headers()
    r = await client.put(
        "/api/v1/knowledge-base/skills/ok-name%0a",  # url-encoded trailing \n
        json={"files": {"SKILL.md": _skill_md("x")}}, headers=ops,
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "INVALID_SKILL_NAME"


async def test_save_draft_is_single_draft(client):
    """存兩次草稿（無中間發佈）→ 仍只有一個 draft（覆蓋，不新增版本）。"""
    name = _unique_name()
    ops = _ops_headers()
    r1 = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name, body="A")}}, headers=ops,
    )
    r2 = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name, body="B")}}, headers=ops,
    )
    assert r1.json()["data"]["version"] == r2.json()["data"]["version"]  # 同版本覆蓋
    r = await client.get(f"/api/v1/knowledge-base/skills/{name}/revisions", headers=ops)
    drafts = [x for x in r.json()["data"]["items"] if x["status"] == "draft"]
    assert len(drafts) == 1


async def test_double_publish_conflict(client):
    name = _unique_name()
    ops, admin = _ops_headers(), _admin_headers()
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": _skill_md(name)}}, headers=ops,
    )
    v = r.json()["data"]["version"]
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish", json={"version": v}, headers=admin,
    )
    assert r.status_code == 200
    # 重複發佈同版本 → 409
    r = await client.post(
        f"/api/v1/knowledge-base/skills/{name}/publish", json={"version": v}, headers=admin,
    )
    assert r.status_code == 409


def _admin_headers() -> dict:
    tok = _make_token(user_id=str(uuid.uuid4()), role="admin")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-ID": DEFAULT_TENANT_ID}


# ── internal ingest merge（refinery 行為軌用；CR-0168）──────────────────────────

INTERNAL_HEADERS = {"X-Internal-Token": "test-internal-token"}


def _internal_ready() -> bool:
    import os
    return os.environ.get("INTERNAL_API_TOKEN") == "test-internal-token"


async def test_ingest_merge_is_additive(client):
    """merge：只送一個 refined reference → 基準所有檔保留、SKILL.md 不動、只多那一檔。"""
    if not _internal_ready():
        pytest.skip("需 INTERNAL_API_TOKEN=test-internal-token")
    name = _unique_name()
    ops, admin = _ops_headers(), _admin_headers()
    # 建立並發佈基準（SKILL.md + 一個既有 reference）
    base_md = _skill_md(name, body="基準 SOP")
    r = await client.put(
        f"/api/v1/knowledge-base/skills/{name}",
        json={"files": {"SKILL.md": base_md, "references/a.md": "既有參考"}}, headers=ops,
    )
    v = r.json()["data"]["version"]
    await client.post(f"/api/v1/knowledge-base/skills/{name}/publish", json={"version": v}, headers=admin)

    # refinery merge 汲取一個 refined reference
    r = await client.post(
        "/api/v1/internal/skills/ingest",
        json={"tenant_id": DEFAULT_TENANT_ID, "skill_name": name,
              "files": {"references/refined/x.md": "新淬鍊話術"}, "merge": True},
        headers=INTERNAL_HEADERS,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "draft"  # 只進 draft，未 publish（品質零影響）

    # 草稿＝基準 ∪ 新檔（加性）：SKILL.md 原封、既有 reference 保留、新增 refined
    draft = (await client.get(f"/api/v1/knowledge-base/skills/{name}", headers=ops)).json()["data"]
    assert draft["status"] == "draft"
    assert draft["files"]["SKILL.md"] == base_md            # SKILL.md 不動
    assert draft["files"]["references/a.md"] == "既有參考"  # 既有保留
    assert draft["files"]["references/refined/x.md"] == "新淬鍊話術"  # 新增

    # 發佈中版本仍是基準（draft 未發佈前 agent 用的還是舊的）
    revs = (await client.get(f"/api/v1/knowledge-base/skills/{name}/revisions", headers=ops)).json()["data"]["items"]
    assert next(x for x in revs if x["version"] == v)["status"] == "published"


async def test_ingest_merge_requires_existing_skill(client):
    """merge 無基準（skill 不存在）→ 404，不憑空產不完整 skill。"""
    if not _internal_ready():
        pytest.skip("需 INTERNAL_API_TOKEN=test-internal-token")
    r = await client.post(
        "/api/v1/internal/skills/ingest",
        json={"tenant_id": DEFAULT_TENANT_ID, "skill_name": _unique_name(),
              "files": {"references/refined/x.md": "孤兒"}, "merge": True},
        headers=INTERNAL_HEADERS,
    )
    assert r.status_code == 404
    assert r.json()["error_code"] == "SKILL_NOT_FOUND"


async def test_ingest_no_merge_replaces(client):
    """merge=false（預設）：整包取代語意不變。"""
    if not _internal_ready():
        pytest.skip("需 INTERNAL_API_TOKEN=test-internal-token")
    name = _unique_name()
    r = await client.post(
        "/api/v1/internal/skills/ingest",
        json={"tenant_id": DEFAULT_TENANT_ID, "skill_name": name,
              "files": {"SKILL.md": _skill_md(name)}},
        headers=INTERNAL_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "draft"
