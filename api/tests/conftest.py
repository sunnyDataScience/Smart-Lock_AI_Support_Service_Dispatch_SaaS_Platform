"""共用 pytest fixtures for integration tests。

使用方式：
  cd api && API_JWT_SECRET_KEY=test-secret pytest tests/

設計：
  - 透過 httpx.AsyncClient + ASGITransport 直接打 FastAPI app（不啟 uvicorn）
  - 真實 DB（dev 環境的 lock_AI_data）+ 種子資料（admin@example.com / demo-tech）
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
