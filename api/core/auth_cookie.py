"""CR-0177 / CR-0190：登入 token 的 HttpOnly cookie 邊界。

**為什麼需要 env 控網域**：cookie 依「網域」共用而**不看 port**。
- 本機 web:3000 / api:8000 同為 `localhost` → 天然共用（所以本機測起來會像可行）。
- prod web 與 api 的 `*.run.app` hostname 不同，不能直接共享 host-only cookie。
- CR-0190 Web 改走同站 `/api-proxy`：瀏覽器只對 Web origin 收送 cookie，Next server
  將 cookie 轉送 API，因此 build-once promotion 不再依賴 staging hostname。
- 若繞過 proxy 直接打 API／WebSocket，仍須 `app.example.tw` + `api.example.tw` 與
  `AUTH_COOKIE_DOMAIN=.example.tw`。

本模組讓 code 先就緒：
- `AUTH_COOKIE_DOMAIN` 未設 → host-only（**現況行為不變**，本機可用）。
- 直連 API／WebSocket 時設 `AUTH_COOKIE_DOMAIN=.example.tw` → 跨子網域生效。
- `AUTH_COOKIE_SECURE` 未設 → 有設網域時自動 Secure（prod https），否則不設（本機 http）。

CR-0190 S2 將 refresh token 也移入 HttpOnly cookie；前端只可在單次 response 中
解 access token 產生非敏感 session claims，禁止持久化 access/refresh token。
"""

from __future__ import annotations

import os

from fastapi import Response

# 對齊 core/deps._ACCESS_TOKEN_COOKIE（api 端已支援從此 cookie 取 token）
ACCESS_COOKIE = "smartlock_access_token"
REFRESH_COOKIE = "smartlock_refresh_token"


def cookie_domain() -> str | None:
    """跨子網域共用網域（如 `.example.tw`）；未設 → None＝host-only。"""
    return (os.getenv("AUTH_COOKIE_DOMAIN") or "").strip() or None


def cookie_secure() -> bool:
    """明示 `AUTH_COOKIE_SECURE` 優先；否則「有設共用網域」即視為 prod → Secure。"""
    raw = (os.getenv("AUTH_COOKIE_SECURE") or "").strip().lower()
    if raw:
        return raw in ("1", "true", "yes", "on")
    return cookie_domain() is not None


def set_access_cookie(response: Response, token: str, max_age: int) -> None:
    """登入/刷新成功後寫 httpOnly access cookie（JS 不可讀 → XSS 偷不到）。"""
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",   # CSRF 緩解：另有 tenant-scoped 端點強制 X-Tenant-ID 自訂 header
        secure=cookie_secure(),
        path="/",
        domain=cookie_domain(),
    )


def set_refresh_cookie(response: Response, token: str, max_age: int) -> None:
    """refresh token 只進 HttpOnly cookie，不回到 browser storage。"""
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
        domain=cookie_domain(),
    )


def clear_session_cookies(response: Response) -> None:
    """登出時同時清除 access/refresh（domain 必須與寫入時一致）。"""
    response.delete_cookie(key=ACCESS_COOKIE, path="/", domain=cookie_domain())
    response.delete_cookie(key=REFRESH_COOKIE, path="/", domain=cookie_domain())


def clear_access_cookie(response: Response) -> None:
    """相容舊 caller；新登出流程應呼叫 clear_session_cookies。"""
    response.delete_cookie(key=ACCESS_COOKIE, path="/", domain=cookie_domain())
