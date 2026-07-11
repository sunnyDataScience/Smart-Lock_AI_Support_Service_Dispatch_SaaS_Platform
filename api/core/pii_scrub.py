"""PII 遮蔽共用工具（CR-0166 R1-8）。

原實作在 core/observability.py（OTel span 用）；本模組昇格為共用 util，供
audit payload 遮蔽（入 hash 鏈前）、log filter 等接管道使用。observability
改 import 此處，避免兩份 regex drift。

兩個變體：
  - scrub_text：全遮蔽（含地址啟發式）——log / OTel span 用。
  - scrub_audit_value：高置信樣式（email/電話/身分證/LINE uid，不含地址啟發式）——
    audit payload 用，避免地址啟發式誤殺稽核證據力（CR-0166 §8-D10 裁決）。
"""

from __future__ import annotations

import hashlib
import re

# 順序有意義：LINE uid 先於 token（U 開頭 33 字元）；電話先於地址（門牌數字）。
_LINE_UID_RE = re.compile(r"\bU[0-9a-f]{32}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 台灣手機（09xxxxxxxx / +8869xxxxxxxx）與市話（0x-xxxxxxxx）
_PHONE_RE = re.compile(
    r"(?:\+886[-\s]?9\d{2}|09\d{2})[-\s]?\d{3}[-\s]?\d{3}"
    r"|\b0\d{1,2}-\d{6,8}\b"
)
# 台灣身分證：1 大寫英文字母 + 1/2 開頭 + 8 位數字（CR-0166 R1-8 新增）
_NATIONAL_ID_RE = re.compile(r"\b[A-Z][12]\d{8}\b")
# 台灣地址啟發式（保守，寧漏勿誤殺）——僅 scrub_text 用，audit 不用
_ADDR_RE = re.compile(
    r"\S{1,6}[縣市]\S{0,12}?[區鄉鎮市]?\S{0,20}?(?:路|街|大道|巷|弄)[\S]{0,12}?號?"
)
_TOKEN_PARAM_RE = re.compile(r"((?:access_|refresh_)?token=)[^&\s]+")


def _hash_line_uid(m: re.Match) -> str:
    return "U#" + hashlib.sha256(m.group(0).encode()).hexdigest()[:12]


def _scrub_common(value: str) -> str:
    """LINE uid / token / 身分證 / email / 電話（不含地址）。"""
    value = _LINE_UID_RE.sub(_hash_line_uid, value)
    value = _TOKEN_PARAM_RE.sub(r"\1[TOKEN]", value)
    value = _NATIONAL_ID_RE.sub("[ID]", value)
    value = _EMAIL_RE.sub("[EMAIL]", value)
    value = _PHONE_RE.sub("[PHONE]", value)
    return value


def scrub_text(value: str) -> str:
    """全遮蔽（含地址啟發式）——log / OTel span 用。非 PII 內容原樣保留。"""
    if not isinstance(value, str):
        return value
    value = _scrub_common(value)
    value = _ADDR_RE.sub("[ADDR]", value)
    return value


def scrub_audit_value(value):
    """audit payload 值遮蔽：高置信樣式，不含地址啟發式（保稽核證據力）。
    非字串原樣回傳。"""
    if not isinstance(value, str):
        return value
    return _scrub_common(value)


def scrub_audit_payload(payload):
    """遞迴遮蔽 dict/list 內所有字串值（audit payload 專用，入 hash 前呼叫）。"""
    if isinstance(payload, dict):
        return {k: scrub_audit_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [scrub_audit_payload(v) for v in payload]
    return scrub_audit_value(payload)
