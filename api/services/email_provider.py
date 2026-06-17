"""Email 送達抽象 — CR-0025 / ADR-0114。

預設 SMTP 實作，透過 env 設定（可指向 SendGrid / SES / 自架 SMTP）：
  SMTP_HOST / SMTP_PORT(587) / SMTP_USER / SMTP_PASSWORD / SMTP_FROM / SMTP_USE_TLS(true)

**Fail-safe**：未配置 SMTP（無 SMTP_HOST）時 `send_email` 回 False，不丟例外。
呼叫端（password reset）據此記 log 但仍回 200 —— 不可因寄信未配置而 500、
也不可洩漏帳號是否存在。

smtplib 為同步阻塞，呼叫端以 `asyncio.to_thread(send_email, ...)` 包裝避免卡事件迴圈。
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger("api.email_provider")


def _smtp_config() -> dict | None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    if not host:
        return None
    user = (os.getenv("SMTP_USER") or "").strip()
    return {
        "host": host,
        "port": int((os.getenv("SMTP_PORT") or "587").strip() or "587"),
        "user": user,
        "password": os.getenv("SMTP_PASSWORD") or "",
        "from_addr": (os.getenv("SMTP_FROM") or user or "no-reply@smartlock.local").strip(),
        "use_tls": (os.getenv("SMTP_USE_TLS") or "true").strip().lower() != "false",
    }


def is_configured() -> bool:
    """SMTP 是否已配置（供呼叫端判斷是否實際會送達）。"""
    return _smtp_config() is not None


def send_email(*, to: str, subject: str, body_text: str) -> bool:
    """同步寄一封純文字信。回傳是否送出成功。

    未配置或失敗皆回 False（記 log，不丟例外）—— fail-safe，由呼叫端決定後續。
    """
    cfg = _smtp_config()
    if not cfg:
        logger.warning("SMTP 未配置（缺 SMTP_HOST）— 略過寄信 to=%s subject=%r", to, subject)
        return False

    msg = EmailMessage()
    msg["From"] = cfg["from_addr"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            if cfg["use_tls"]:
                server.starttls(context=ssl.create_default_context())
            if cfg["user"]:
                server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        logger.info("reset 信已送出 to=%s", to)
        return True
    except Exception as e:  # noqa: BLE001 — 任何寄信錯誤都 fail-safe
        logger.error("SMTP 寄信失敗 to=%s: %r", to, e)
        return False
