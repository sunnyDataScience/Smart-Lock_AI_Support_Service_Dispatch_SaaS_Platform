"""Casdoor OIDC token 驗證（2.3.2 收案遺留：interim auth Casdoor 化，劃歸 2.1.1）。

鏡射 api/core/oidc.py 的最小必要面（refinery 為獨立 uv workspace member，
不 import api 套件）：opt-in——`CASDOOR_ENDPOINT`＋`CASDOOR_CLIENT_ID`＋
`CASDOOR_JWT_PUBLIC_KEY(_FILE)` 三者齊備才啟用，未配置＝零行為變化
（HS256 interim auth 照舊）。

身分映射同 CR-0141 D2：claims 正規化為與自簽 JWT 同形
{sub, role, tenant_id, type='access'}——require_reviewer 的角色白名單與
tenant 檢查零改動。sub＝properties.smartlock_user_id（不 fallback Casdoor
原生 sub，未 bootstrap 的帳號一律拒絕）。
"""

from __future__ import annotations

import os
from functools import lru_cache

from jose import JWTError, jwt


class OIDCError(Exception):
    """OIDC 驗證失敗（呼叫端轉 401）。"""


def _public_key() -> str | None:
    inline = os.environ.get("CASDOOR_JWT_PUBLIC_KEY", "").strip()
    if inline:
        return inline
    path = os.environ.get("CASDOOR_JWT_PUBLIC_KEY_FILE", "").strip()
    if path and os.path.exists(path):
        return _read_key_file(path)
    return None


@lru_cache(maxsize=4)
def _read_key_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def oidc_enabled() -> bool:
    return bool(
        os.environ.get("CASDOOR_ENDPOINT")
        and os.environ.get("CASDOOR_CLIENT_ID")
        and _public_key()
    )


def verify_oidc_token(token: str) -> dict:
    """驗 Casdoor RS256 token → 正規化 payload（與自簽 JWT 同形）。

    回傳：{sub, role, tenant_id, type='access', jti, iat}
    失敗丟 OIDCError（簽章/過期/iss/aud 不符、身分映射缺漏）。
    """
    key = _public_key()
    client_id = os.environ.get("CASDOOR_CLIENT_ID", "")
    issuer = (os.environ.get("CASDOOR_ISSUER")
              or os.environ.get("CASDOOR_ENDPOINT", "")).rstrip("/")
    if not (key and client_id and issuer):
        raise OIDCError("OIDC 未配置")

    try:
        payload = jwt.decode(
            token, key, algorithms=["RS256"],
            audience=client_id, issuer=issuer,
        )
    except JWTError as e:
        raise OIDCError(f"OIDC token 驗證失敗：{e}") from e

    props = payload.get("properties") or {}
    user_id = props.get("smartlock_user_id", "")
    if not user_id:
        raise OIDCError("token 缺 smartlock_user_id 映射（帳號未同步）")

    role = props.get("smartlock_role", "")
    if not role:
        roles = payload.get("roles") or []
        if roles and isinstance(roles[0], dict):
            role = roles[0].get("name", "")
    if not role:
        raise OIDCError("token 缺角色映射")

    return {
        "sub": user_id,
        "role": role,
        "tenant_id": props.get("tenant_id", ""),
        "type": "access",
        "jti": payload.get("jti", ""),
        "iat": payload.get("iat"),
    }
