"""HITL 審核服務 — FastAPI backend + 靜態審核 UI(WBS 2.3.2/CR-0140 D4)。

ADR-018:獨立容器服務 + 自有 web 操作介面(否決掛進既有 web/api)。
interim auth(Casdoor OIDC 隨 2.1.1 替換,CIA 記遺留):
  - 登入=代理 api `/api/v1/auth/login`(LOCK_API_BASE_URL,同 stack 網路)
  - 驗證=HS256 共驗 `API_JWT_SECRET_KEY`;角色白名單 admin/operations_manager/reviewer
  - token tenant 必須等於本服務 REFINERY_TENANT_ID(per-brand 隔離)

啟動:REFINERY_TENANT_ID=<uuid> POSTGRES_URI=... API_JWT_SECRET_KEY=... \
       uv run uvicorn refinery.service:app --port 8002
"""

import logging
import os
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel

from . import db, embedding, review

_REVIEW_ROLES = {"admin", "operations_manager", "reviewer"}
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(title="knowledge-refinery 審核服務", version="0.2.0")

# ── 可觀測性(CR-0156/ADR-007:opt-in,env 未設=no-op;任何失敗不可癱瘓服務) ──
try:
    from .observability import setup_observability

    setup_observability(app, service_name="knowledge-refinery")
except Exception:  # noqa: BLE001 — 防禦性:觀測層掛掉服務照常啟動
    logging.getLogger("refinery.service").exception(
        "observability 初始化失敗 → 降級略過(服務照常啟動)")


# ── auth ─────────────────────────────────────────────────────────────────────

def _decode(token: str) -> dict:
    secret = os.environ.get("API_JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(503, detail={"error_code": "AUTH_UNCONFIGURED",
                                         "message": "API_JWT_SECRET_KEY 未設定"})
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED",
                                         "message": "token 無效或過期"})


def require_reviewer(request: Request) -> dict:
    """Bearer JWT(與 api 同 secret/HS256)→ 審核角色白名單 + tenant 相符。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED",
                                         "message": "缺 Bearer token"})
    payload = _decode(auth.removeprefix("Bearer ").strip())
    if payload.get("type") != "access":
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED",
                                         "message": "非 access token"})
    role = payload.get("role", "")
    if role not in _REVIEW_ROLES:
        raise HTTPException(403, detail={"error_code": "FORBIDDEN",
                                         "message": f"角色 {role} 無審核權"})
    if payload.get("tenant_id") != db.tenant_id():
        raise HTTPException(403, detail={"error_code": "TENANT_MISMATCH",
                                         "message": "token tenant 與服務不符"})
    return payload


# ── 登入代理(免 CORS:UI 與 backend 同源) ─────────────────────────────────

class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
async def login_proxy(body: LoginBody):
    base = os.environ.get("LOCK_API_BASE_URL", "http://localhost:8001").rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{base}/api/v1/auth/login",
                                 json={"email": body.email, "password": body.password})
    return JSONResponse(status_code=resp.status_code, content=resp.json())


# ── 審核端點 ─────────────────────────────────────────────────────────────────

class ReviewBody(BaseModel):
    comment: str | None = None


def _conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/drafts")
def list_drafts(status: str | None = "pending_review",
                user: dict = Depends(require_reviewer), conn=Depends(_conn)):
    items = review.list_drafts(conn, db.tenant_id(),
                               status=status or None, limit=200)
    return {"data": items, "error": None}


@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: int, user: dict = Depends(require_reviewer), conn=Depends(_conn)):
    try:
        return {"data": review.get_draft(conn, db.tenant_id(), draft_id), "error": None}
    except review.ReviewError as e:
        raise HTTPException(e.http_status, detail={"error_code": e.code, "message": str(e)})


def _do_review(action, draft_id: int, body: ReviewBody, user: dict, conn):
    try:
        result = action(conn, db.tenant_id(), draft_id,
                        reviewer_id=user["sub"], comment=body.comment)
        return {"data": result if isinstance(result, dict) else {"ok": True}, "error": None}
    except review.ReviewError as e:
        conn.rollback()
        raise HTTPException(e.http_status, detail={"error_code": e.code, "message": str(e)})
    except Exception:
        conn.rollback()
        raise


@app.post("/api/drafts/{draft_id}/approve")
def approve_draft(draft_id: int, body: ReviewBody,
                  user: dict = Depends(require_reviewer), conn=Depends(_conn)):
    def action(conn, tenant, did, *, reviewer_id, comment):
        return review.approve(conn, tenant, did, reviewer_id=reviewer_id, comment=comment,
                              embed_fn=embedding.embed,
                              embed_model_name=embedding.embed_model())
    return _do_review(action, draft_id, body, user, conn)


@app.post("/api/drafts/{draft_id}/reject")
def reject_draft(draft_id: int, body: ReviewBody,
                 user: dict = Depends(require_reviewer), conn=Depends(_conn)):
    return _do_review(review.reject, draft_id, body, user, conn)


@app.post("/api/drafts/{draft_id}/re-refine")
def rerefine_draft(draft_id: int, body: ReviewBody,
                   user: dict = Depends(require_reviewer), conn=Depends(_conn)):
    return _do_review(review.re_refine, draft_id, body, user, conn)


# ── UI 與健康檢查 ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "knowledge-refinery"}


@app.get("/")
def index():
    return FileResponse(_STATIC_DIR / "index.html")
