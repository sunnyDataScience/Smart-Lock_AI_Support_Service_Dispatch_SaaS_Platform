"""CR-0177 S3a：access token 的 httpOnly cookie 設定/清除（自訂網域就緒）。

**為什麼需要 env 控網域**：cookie 依「網域」共用而**不看 port**。
- 本機 web:3000 / api:8000 同為 `localhost` → 天然共用（所以本機測起來會像可行）。
- prod web=`smart-lock-web-*.run.app`、api=`smart-lock-api-*.run.app` 為**不同 hostname**，
  host-only cookie **送不到 api**；且 `run.app` 在 Public Suffix List，
  **無法**設 `.run.app` 共用父網域 cookie。
→ 故 S3 目標態（token 只存 httpOnly cookie、localStorage 全退場）**必須先做自訂網域**
  （web/api 同父網域，如 `app.example.tw` + `api.example.tw`）。業主 2026-07-21 選此方案。

本模組讓 code 先就緒：
- `AUTH_COOKIE_DOMAIN` 未設 → host-only（**現況行為不變**，本機可用）。
- 自訂網域上線後設 `AUTH_COOKIE_DOMAIN=.example.tw` → 跨子網域生效，**無需改 code**。
- `AUTH_COOKIE_SECURE` 未設 → 有設網域時自動 Secure（prod https），否則不設（本機 http）。

⚠️ 本階段（S3a）**localStorage 仍保留為過渡**；S3b（移除 localStorage）待自訂網域上線後才做，
否則 prod 會因 cookie 送不到 api 而全站 401。
"""

from __future__ import annotations

import os

from fastapi import Response

# 對齊 core/deps._ACCESS_TOKEN_COOKIE（api 端已支援從此 cookie 取 token）
ACCESS_COOKIE = "smartlock_access_token"


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


def clear_access_cookie(response: Response) -> None:
    """登出時清除（domain 需與寫入時一致，否則清不掉）。"""
    response.delete_cookie(key=ACCESS_COOKIE, path="/", domain=cookie_domain())
