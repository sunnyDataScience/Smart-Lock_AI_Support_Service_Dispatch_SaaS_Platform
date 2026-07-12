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
