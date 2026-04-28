"""Smart Lock AI — Admin REST API entrypoint.

啟動：cd api && uvicorn main:app --reload --port 8001
所有設定從 config.toml 讀取，敏感值從 .env。
"""

import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# 載入專案根目錄 .env（與 agent/ 共用）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import load_config
from core.db import init_db, close_db, healthcheck
from core.errors import register_exception_handlers
from core.idempotency import IdempotencyReplay, handle_idempotency_replay
from middleware.request_id import RequestIdMiddleware
from routers import auth as auth_router
from routers import notifications as notifications_router
from routers import system_config as system_config_router
from routers import kb_cases as kb_cases_router
from routers import kb_manuals as kb_manuals_router
from routers import sop_drafts as sop_drafts_router
from routers import audit_logs as audit_logs_router
from routers import conversations as conversations_router
from routers import dashboard as dashboard_router
from routers import problem_cards as problem_cards_router
from routers import work_orders as work_orders_router
from routers import technicians as technicians_router
from routers import settlements as settlements_router
from routers import pricing_rules as pricing_rules_router

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

cfg = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: 連線 DB → 服務生命週期 → 關閉連線。"""
    await init_db(cfg.database)
    logger.info("API service ready (port=%s)", cfg.system["port"])
    yield
    await close_db()
    logger.info("API service stopped")


app = FastAPI(
    title="Smart Lock AI — Admin REST API",
    version="0.2.0",
    description="Phase 1 MVP. Contract SSOT: docs/02-design/specs/openapi.yaml",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.system.get("cors_origins", ["http://localhost:3000"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "RateLimit-Limit", "RateLimit-Remaining", "RateLimit-Reset"],
)
app.add_middleware(RequestIdMiddleware)

register_exception_handlers(app)
app.add_exception_handler(IdempotencyReplay, handle_idempotency_replay)

app.include_router(auth_router.router, prefix="/api/v1", tags=["auth"])
app.include_router(notifications_router.router, prefix="/api/v1", tags=["realtime"])
app.include_router(system_config_router.router, prefix="/api/v1", tags=["user_management"])
app.include_router(kb_cases_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(kb_manuals_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(sop_drafts_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(audit_logs_router.router, prefix="/api/v1", tags=["observability"])
app.include_router(conversations_router.router, prefix="/api/v1", tags=["customer_service"])
app.include_router(dashboard_router.router, prefix="/api/v1", tags=["reports"])
app.include_router(problem_cards_router.router, prefix="/api/v1", tags=["customer_service"])
app.include_router(work_orders_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(technicians_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(settlements_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(pricing_rules_router.router, prefix="/api/v1", tags=["accounting"])


@app.get("/health")
async def health():
    """Health check — DB 連線存活檢測。"""
    db_ok = await healthcheck()
    from fastapi.responses import JSONResponse
    status = "ok" if db_ok else "degraded"
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": status, "version": app.version, "checks": {"db": "ok" if db_ok else "disconnected"}},
    )
