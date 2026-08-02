"""共用 pytest fixtures for integration tests。

使用方式：
  cd api && API_JWT_SECRET_KEY=test-secret pytest tests/

設計：
  - 透過 httpx.AsyncClient + ASGITransport 直接打 FastAPI app（不啟 uvicorn）
  - 真實 DB（dev 環境的 lock_AI_data）+ 種子資料（test@lock-ai.com / demo-tech）
  - 測試前後若需要 fixtures，由各測試自管 setUp / tearDown
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 將 api/ 目錄加入 sys.path，讓 `from main import app` 可運作
API_ROOT = Path(__file__).resolve().parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# 載入 .env（與 main.py 對齊）
from dotenv import load_dotenv  # noqa: E402

PROJECT_ROOT = API_ROOT.parent
load_dotenv(PROJECT_ROOT / ".env")

# Tests require JWT secret; default to a stable dev value when unset
os.environ.setdefault("API_JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

# 種子帳號（對齊 SQL/seeds/_admin_user.sql + technicians.sql）
ADMIN_USER_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
# Dispatcher 帳號（對齊 SQL/seeds/dispatcher_user.sql — F-004 V2 獨立角色）
DISPATCHER_USER_ID = "d1893a7f-1c2e-4a6b-9e4d-2f5b8c6a1e02"
# Customer service 用 fake UUID（無 seed 要求 — token 驗證只看 claims）
CUSTOMER_SERVICE_USER_ID = "22222222-2222-2222-2222-222222222222"
# Technician 用既有 demo-tech seed（不存在也 OK，role 檢查在 DB 查詢前）
TECHNICIAN_USER_ID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def app():
    """載入 FastAPI app（含 lifespan startup / shutdown）。"""
    from main import app as fastapi_app

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://testserver"
    ) as _client:
        # 觸發 lifespan startup
        # (AsyncClient with ASGITransport handles this automatically)
        pass

    return fastapi_app


@pytest_asyncio.fixture
async def client(app):
    """非同步 HTTP client，每測試獨立。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


def _make_token(*, user_id: str, role: str, tenant_id: str = DEFAULT_TENANT_ID) -> str:
    """直接呼叫 core.auth.create_token 產 access token（不走 /auth/login）。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=user_id,
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    return token


@pytest.fixture(autouse=True)
def _isolate_db_conn():
    """防止 FakeConn 跨檔污染全域 db._conn（CR-0038 假綠根源之一）。

    ~21 個 Phase II 測試在 body 直接 `db_module._conn = FakeConn(...)` 且不還原，
    monkeypatch 只還原 `_ensure_conn` 不還原 `_conn` → 殘留 fake 被後續真 DB 測試撈到，
    導致併跑 21 fail（單檔過）。每測試後：若 `_conn` 不是真 psycopg AsyncConnection
    （即殘留 fake），清空 → 下個真 DB 測試 `_ensure_conn()` 重連；真連線則保留（快）。
    """
    yield
    import core.db as _db
    from psycopg import AsyncConnection

    if _db._conn is not None and not isinstance(_db._conn, AsyncConnection):
        _db._conn = None


@pytest.fixture
def admin_token() -> str:
    """admin 角色 access token。"""
    return _make_token(user_id=ADMIN_USER_ID, role="admin")


@pytest.fixture
def admin_headers(admin_token) -> dict[str, str]:
    """admin 通用 headers（Authorization + X-Tenant-ID）。"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


@pytest.fixture
def secondary_admin_headers() -> dict[str, str]:
    """第二位 admin（不同 user_id）— 用於雙簽測試。"""
    other_user_id = "11111111-1111-1111-1111-111111111111"
    token = _make_token(user_id=other_user_id, role="operations_manager")
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


@pytest.fixture
def dispatcher_headers() -> dict[str, str]:
    """Dispatcher 角色 headers（F-004 V2 新獨立角色）。"""
    token = _make_token(user_id=DISPATCHER_USER_ID, role="dispatcher")
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


@pytest.fixture
def customer_service_headers() -> dict[str, str]:
    """Customer service 角色 headers（PM Q6=A — 可繞過自動派工 + audit log）。"""
    token = _make_token(user_id=CUSTOMER_SERVICE_USER_ID, role="customer_service")
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


@pytest.fixture
def technician_headers() -> dict[str, str]:
    """Technician 角色 headers — 應被 manual dispatch 端點 403。"""
    token = _make_token(user_id=TECHNICIAN_USER_ID, role="technician")
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


#: 平台管理員 user_id（fake — 不需 seed;require_platform_admin 只看 token role，
#: 安全狀態查無此 user 時 fail-open。CR-0114 R3）
PLATFORM_ADMIN_USER_ID = "44444444-4444-4444-4444-444444444444"


@pytest.fixture
def platform_admin_headers() -> dict[str, str]:
    """平台管理員 headers（CR-0114）。非 tenant-scoped，不帶 X-Tenant-ID。"""
    token = _make_token(user_id=PLATFORM_ADMIN_USER_ID, role="platform_admin")
    return {"Authorization": f"Bearer {token}"}


async def seed_accepted_quote(pc_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> str:
    """CR-0128 報價先行 gate 測試前置：直接落一筆 accepted 報價（模擬客戶已 LINE 確認）。

    convert（create_from_problem_card）自 CR-0128 起要求 PC 有客戶已確認報價
    （或 emergency_class 急件 carve-out）；既有下游功能測試以本 helper 滿足前置。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    row = await (await db_module._conn.execute(
        "INSERT INTO quote (problem_card_id, state, tenant_id, version) "
        "VALUES (%s::uuid, 'accepted', %s::uuid, "
        "        (SELECT COALESCE(MAX(version), 0) + 1 FROM quote WHERE problem_card_id = %s::uuid)) "
        "RETURNING id",
        (pc_id, tenant_id, pc_id),
    )).fetchone()
    return str(row[0])


async def seed_required_kyc_docs(tech_id: str) -> None:
    """塞齊 CR-0195 核准所需的 KYC 文件（身分證正反面）的 metadata 列。

    CR-0195 起 `:onboard-approve` 對文件不齊者回 422（除非顯式條件式核准）。
    測試若不是在測「文件閘」本身，就該先把文件補齊，讓核准回到單純的
    生命週期轉移——用 conditional=True 繞過會讓那些測試的事件型別變成
    `onboarding_approved_conditional`，等於偷換了它們原本在驗的東西。

    只寫 metadata、不寫實體檔（核准閘只查表）。
    """
    import uuid as _uuid

    import core.db as db_module
    from core.db import _ensure_conn
    from services.technician_kyc_service import REQUIRED_DOC_TYPES

    await _ensure_conn()
    row = await (await db_module._conn.execute(
        "SELECT tenant_id FROM technicians WHERE id = %s::uuid", (tech_id,)
    )).fetchone()
    if not row:
        raise AssertionError(f"technician {tech_id} 不存在，無法塞 KYC 文件")
    for doc_type in REQUIRED_DOC_TYPES:
        await db_module._conn.execute(
            "INSERT INTO technician_registration_document "
            "  (id, technician_id, tenant_id, doc_type, filename, content_type, "
            "   size_bytes, storage_path, sha256) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)",
            (str(_uuid.uuid4()), tech_id, str(row[0]), doc_type,
             f"{doc_type}.png", "image/png", 100,
             f"kyc-registration/{tech_id}/{doc_type}.png", _uuid.uuid4().hex * 2),
        )


async def audit_privileged_exec(sql: str, params: tuple = ()) -> None:
    """CR-0164：audit_events 加 append-only trigger（migration 100）後，測試的
    清理/竄改注入需 session_replication_role='replica' 特權繞過（ORIGIN 觸發器
    於 replica 模式不觸發——模擬 DBA/retention purge 特權路徑）。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    await db_module._conn.execute("SET session_replication_role = 'replica'")
    try:
        await db_module._conn.execute(sql, params)
    finally:
        await db_module._conn.execute("SET session_replication_role = 'origin'")


# ─────────────────────────────────────────────────────────────────────────
# 測試庫 schema 同步守衛（2026-08-02）
#
# **為什麼要這個**：2026-08-02 追 SC-13～19 探針時，全套失敗數長期停在 129 支，
# 一直被當成「既有失敗清單」。實際補上測試庫缺的 migration 122/125 之後，
# 失敗數掉到 26 —— **那 100 支根本不是 code 壞，是測試庫 schema 落後 repo**。
#
# 假基線比沒有基線更糟：它讓真正的新回歸藏在一片紅裡看不出來，
# 而且每個人都以為「本來就這樣」。
#
# 本守衛在 session 開始時比對測試庫的 public.schema_migrations 與
# SQL/migrations/*.sql，落後就**直接中止**並印出補法。
# 逃生門：ALLOW_TEST_DB_DRIFT=1（給刻意要在舊 schema 上重現問題的情境）。
# ─────────────────────────────────────────────────────────────────────────

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "SQL" / "migrations"


def _repo_migration_versions(target: str = "brand") -> set[str]:
    """repo 內**落庫目標含 `target`** 的 migration 版本號。

    必須尊重檔頭的 `-- migrate-targets:` 宣告，否則會把 platform／tech 專屬的
    migration 也要求品牌測試庫套用 —— 初版就犯了這個錯，被 121
    service-principal-credentials（platform 專屬）打臉。
    未標注者依 apply-schema-routed.sh 的慣例視為 brand（向下相容）。
    """
    import re as _re

    out: set[str] = set()
    if not _MIGRATIONS_DIR.is_dir():
        return out
    for f in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        head = f.name.split("-", 1)[0]
        if not head.isdigit():
            continue
        targets = {"brand"}
        try:
            for line in f.read_text(encoding="utf-8").splitlines()[:5]:
                if "migrate-targets:" in line:
                    raw = line.split("migrate-targets:", 1)[1].strip()
                    raw = _re.split(r"[^a-zA-Z,]", raw, maxsplit=1)[0]
                    targets = {t.strip() for t in raw.split(",") if t.strip()}
                    break
        except OSError:
            pass
        if target in targets:
            out.add(str(int(head)))
    return out


@pytest.fixture(scope="session", autouse=True)
def _assert_test_db_schema_synced():
    """測試庫 schema 落後 repo → 中止並說明，不讓假基線繼續長大。"""
    if os.environ.get("ALLOW_TEST_DB_DRIFT") == "1":
        return
    uri = os.environ.get("POSTGRES_URI", "")
    if not uri:
        return  # 沒有 DB 的純單元測試情境不干涉

    try:
        import psycopg

        with psycopg.connect(uri, connect_timeout=10) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            if cur.fetchone()[0] is None:
                applied: set[str] = set()
            else:
                cur.execute("SELECT version FROM public.schema_migrations")
                applied = {str(r[0]).lstrip("0") or "0" for r in cur.fetchall()}
    except Exception as exc:  # noqa: BLE001 — 連不上 DB 不該由本守衛決定成敗
        print(f"\n[test-db-guard] 略過 schema 同步檢查（DB 不可用：{exc!r}）")
        return

    missing = sorted(_repo_migration_versions("brand") - applied, key=int)
    if not missing:
        return

    pytest.exit(
        "\n"
        "══════════════════════════════════════════════════════════════\n"
        " 測試庫 schema 落後 repo，測試結果不可信 —— 已中止\n"
        "══════════════════════════════════════════════════════════════\n"
        f"  未套用的 migration（{len(missing)} 支）：{', '.join(missing)}\n"
        "\n"
        "  為什麼硬擋：2026-08-02 的實例——測試庫缺 migration 122/125 讓全套失敗數\n"
        "  虛報成 129 支（實際 26 支）。假基線會把真正的新回歸藏在一片紅裡。\n"
        "\n"
        "  補法（對測試庫執行）：\n"
        "    POSTGRES_URI=<測試庫> ./scripts/db/apply-schema-routed.sh\n"
        "\n"
        "  若刻意要在舊 schema 上重現問題：ALLOW_TEST_DB_DRIFT=1 pytest ...\n"
        "══════════════════════════════════════════════════════════════",
        returncode=3,
    )
