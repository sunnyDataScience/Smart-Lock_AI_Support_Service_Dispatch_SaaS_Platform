"""2.3.2 審核服務元件測試(需 POSTGRES_URI scratch 庫;未設即 skip)。

⚠ 絕不對 UAT 庫(5433)跑。fake embed(不打真 Vertex)。
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_URI"), reason="需 POSTGRES_URI(scratch 庫)"
)

TID = "00000000-0000-0000-0000-000000000001"

os.environ.setdefault("REFINERY_TENANT_ID", TID)
# 跟隨外部 env(SIT 合跑時由呼叫端指定;未設才用測試預設)——寫死會與 env 不一致 401
SECRET = os.environ.setdefault("API_JWT_SECRET_KEY", "kr-test-secret")

FAKE_VEC = [0.001] * 768


def _token(*, sub: str, role: str = "reviewer", tenant: str = TID, typ: str = "access") -> str:
    from jose import jwt

    return jwt.encode(
        {"sub": sub, "role": role, "tenant_id": tenant, "type": typ,
         "iat": 1, "exp": 4102444800, "jti": str(uuid.uuid4())},
        SECRET, algorithm="HS256",
    )


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from refinery import embedding, service

    monkeypatch.setattr(embedding, "embed", lambda text: FAKE_VEC)
    monkeypatch.setattr(embedding, "embed_model", lambda: "fake/embed-768")
    return TestClient(service.app)


@pytest.fixture()
def conn():
    from refinery import db

    with db.connect() as c:
        yield c


def _mk_reviewer(conn) -> str:
    uid = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, tenant_id, email, role) VALUES (%s::uuid, %s, %s, 'reviewer')",
            (uid, TID, f"kr-rev-{uid[:8]}@example.com"),
        )
    conn.commit()
    return uid


def _mk_draft(conn, draft_type="case_entry", suffix="") -> int:
    from refinery import store
    from refinery.refine import draft_key

    payload = ({"symptom": f"症狀{suffix}", "resolution": f"解法{suffix}"}
               if draft_type == "case_entry"
               else {"proposal": f"SOP{suffix}", "target_skill": "locksmith-cs-sop",
                     "rationale": "測試"})
    fake_card = str(uuid.uuid4())
    store.insert_drafts(conn, TID, [{
        "draft_key": draft_key(fake_card, draft_type, payload),
        "draft_type": draft_type,
        "source_problem_card_id": None,  # 測試不建卡,FK 留空
        "source_conversation_id": None,
        "brand": "Chatlock", "model": "A90", "category": None,
        "title": f"測試{draft_type}{suffix}",
        "payload": payload,
        "provenance": {"problem_card_id": fake_card, "message_count": 2, "test": True},
        "confidence": 0.7,
    }])
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM knowledge_drafts WHERE tenant_id=%s ORDER BY id DESC LIMIT 1", (TID,))
        return cur.fetchone()[0]


def _cleanup(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM case_entries WHERE source = 'refinery' AND tenant_id = %s", (TID,))
        cur.execute("DELETE FROM knowledge_drafts WHERE tenant_id = %s AND provenance->>'test' = 'true'", (TID,))
        cur.execute("DELETE FROM users WHERE email LIKE 'kr-rev-%'")
    conn.commit()


# ── auth ─────────────────────────────────────────────────────────────────────

def test_auth_guards(client):
    assert client.get("/api/drafts").status_code == 401
    r = client.get("/api/drafts", headers={"Authorization": "Bearer " + _token(sub=str(uuid.uuid4()), role="technician")})
    assert r.status_code == 403
    r = client.get("/api/drafts", headers={"Authorization": "Bearer " + _token(sub=str(uuid.uuid4()), tenant=str(uuid.uuid4()))})
    assert r.status_code == 403 and r.json()["detail"]["error_code"] == "TENANT_MISMATCH"
    r = client.get("/api/drafts", headers={"Authorization": "Bearer " + _token(sub=str(uuid.uuid4()), typ="refresh")})
    assert r.status_code == 401


def test_health_and_ui(client):
    assert client.get("/health").json()["status"] == "ok"
    assert "知識精煉審核" in client.get("/").text


# ── 審核流 ───────────────────────────────────────────────────────────────────

def test_approve_case_entry_publishes(client, conn):
    reviewer = _mk_reviewer(conn)
    hdr = {"Authorization": "Bearer " + _token(sub=reviewer)}
    draft_id = _mk_draft(conn)
    try:
        r = client.get("/api/drafts?status=pending_review", headers=hdr)
        assert any(d["id"] == draft_id for d in r.json()["data"])

        r = client.post(f"/api/drafts/{draft_id}/approve", headers=hdr,
                        json={"comment": "驗證過"})
        assert r.status_code == 200, r.text
        pub = r.json()["data"]
        assert pub["kind"] == "case_entry" and pub["case_entry_id"]

        # case_entries 落地欄位(併形 095)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, problem_description, solution, source, verified, "
                "       embedding_status, embedding_model, approved_by::text, embedding IS NOT NULL "
                "FROM case_entries WHERE id = %s::uuid", (pub["case_entry_id"],))
            row = cur.fetchone()
        assert row[0].startswith("測試case_entry")
        assert row[3] == "refinery" and row[4] is True
        assert row[5] == "ready" and row[6] == "fake/embed-768"
        assert row[7] == reviewer and row[8] is True

        # draft 轉 approved + provenance.published
        d = client.get(f"/api/drafts/{draft_id}", headers=hdr).json()["data"]
        assert d["status"] == "approved"
        assert d["provenance"]["published"]["case_entry_id"] == pub["case_entry_id"]

        # 已核可不可再動作
        r = client.post(f"/api/drafts/{draft_id}/reject", headers=hdr, json={})
        assert r.status_code == 409
    finally:
        _cleanup(conn)


def test_reject_and_rerefine(client, conn):
    reviewer = _mk_reviewer(conn)
    hdr = {"Authorization": "Bearer " + _token(sub=reviewer)}
    d1 = _mk_draft(conn, suffix="-rej")
    d2 = _mk_draft(conn, suffix="-rr")
    try:
        r = client.post(f"/api/drafts/{d1}/reject", headers=hdr, json={"comment": "資訊不足"})
        assert r.status_code == 200
        assert client.get(f"/api/drafts/{d1}", headers=hdr).json()["data"]["status"] == "rejected"

        r = client.post(f"/api/drafts/{d2}/re-refine", headers=hdr, json={"comment": "補逐字稿"})
        assert r.status_code == 200
        assert client.get(f"/api/drafts/{d2}", headers=hdr).json()["data"]["status"] == "re_refine"

        # 拒絕後沒有落地(HITL 反向保證)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM case_entries WHERE source='refinery' AND tenant_id=%s", (TID,))
            assert cur.fetchone()[0] == 0
    finally:
        _cleanup(conn)


def test_approve_behavior_creates_patch_and_apply(client, conn, tmp_path):
    reviewer = _mk_reviewer(conn)
    hdr = {"Authorization": "Bearer " + _token(sub=reviewer)}
    draft_id = _mk_draft(conn, draft_type="behavior")
    try:
        r = client.post(f"/api/drafts/{draft_id}/approve", headers=hdr, json={})
        assert r.status_code == 200
        pub = r.json()["data"]
        assert pub["kind"] == "behavior_patch"
        assert pub["target_path"].startswith(
            "agent/lockcore/skills/locksmith-cs-sop/references/refined/")
        assert "SOP" in pub["content"]

        # 核可行為軌不寫 case_entries
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM case_entries WHERE source='refinery' AND tenant_id=%s", (TID,))
            assert cur.fetchone()[0] == 0

        # apply CLI:落檔到 --root、標 applied、append-only 不覆寫
        from refinery.apply_behavior import main as apply_main

        assert apply_main(["--root", str(tmp_path)]) == 0
        target = tmp_path / pub["target_path"]
        assert target.exists() and "SOP" in target.read_text()

        with conn.cursor() as cur:
            cur.execute("SELECT provenance->'published'->>'applied' FROM knowledge_drafts WHERE id=%s", (draft_id,))
            assert cur.fetchone()[0] == "true"

        # 再跑一次:已 applied → 不再處理;偽造未 applied + 檔案已存在 → 跳過不覆寫
        before = target.read_text()
        assert apply_main(["--root", str(tmp_path)]) == 0
        assert target.read_text() == before
    finally:
        _cleanup(conn)


# ── CR-0168：行為軌走 LiveSkill DB 汲取（merge draft）而非 git ──────────────────


def test_parse_skill_target():
    """target_path → (skill_name, rel_path)；非 skill 路徑回 None。"""
    from refinery.apply_behavior import _parse_skill_target

    assert _parse_skill_target(
        "agent/lockcore/skills/locksmith-cs-sop/references/refined/x.md"
    ) == ("locksmith-cs-sop", "references/refined/x.md")
    assert _parse_skill_target("some/other/path.md") is None
    assert _parse_skill_target("agent/lockcore/skills/only-skill-no-file") is None


def test_ingest_via_api_supports_service_principal(monkeypatch):
    from refinery import apply_behavior

    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"version": 1}}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr(apply_behavior.httpx, "post", _fake_post)
    apply_behavior._ingest_via_api(
        "http://api:8001",
        "slksp_refinery.secret",
        "00000000-0000-0000-0000-000000000001",
        "support",
        "references/refined/a.md",
        "content",
        "note",
        service_credential=True,
    )
    assert captured["headers"] == {
        "X-Service-Credential": "slksp_refinery.secret"
    }


def test_apply_behavior_via_ingest(client, conn, monkeypatch):
    """設 API 環境 → 走 /internal/skills/ingest（merge draft），不寫檔；標 channel=skill_ingest。"""
    from refinery import apply_behavior

    calls = []

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"version": 7, "status": "draft"}}

    def _fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResp()

    monkeypatch.setenv("LOCK_API_BASE_URL", "http://api:8001")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "tok-xyz")
    monkeypatch.setattr(apply_behavior.httpx, "post", _fake_post)

    reviewer = _mk_reviewer(conn)
    hdr = {"Authorization": "Bearer " + _token(sub=reviewer)}
    draft_id = _mk_draft(conn, draft_type="behavior")
    try:
        assert client.post(f"/api/drafts/{draft_id}/approve", headers=hdr, json={}).status_code == 200

        assert apply_behavior.main([]) == 0

        # 走了 ingest，且 merge=true、skill_name/rel_path 正確、帶 internal token
        assert len(calls) == 1
        c = calls[0]
        assert c["url"].endswith("/api/v1/internal/skills/ingest")
        assert c["headers"]["X-Internal-Token"] == "tok-xyz"
        assert c["json"]["merge"] is True
        assert c["json"]["skill_name"] == "locksmith-cs-sop"
        assert list(c["json"]["files"].keys())[0].startswith("references/refined/")

        # provenance 標 applied + channel=skill_ingest + draft_version（保留原 kind/content）
        with conn.cursor() as cur:
            cur.execute(
                "SELECT provenance->'published' FROM knowledge_drafts WHERE id=%s", (draft_id,))
            pub = cur.fetchone()[0]
        assert pub["applied"] is True
        assert pub["channel"] == "skill_ingest"
        assert pub["draft_version"] == 7
        assert pub["kind"] == "behavior_patch"  # 原溯源保留
        assert "content" in pub

        # 已 applied → 再跑不重複呼叫
        assert apply_behavior.main([]) == 0
        assert len(calls) == 1
    finally:
        _cleanup(conn)
