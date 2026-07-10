"""Casdoor OIDC token 驗證(WBS 2.1.1/CR-0141 D3)— opt-in,未配置=零行為變化。

ADR-004:Casdoor 為身分/租戶/角色單一真相源;ADR-005:claim 來源=Casdoor,
resource-level enforce 留在 api(role_required deny-by-default 不變)。

啟用條件(三者齊備,缺一即停用):
  CASDOOR_ENDPOINT              — IdP origin(iss 校驗基準;可用 CASDOOR_ISSUER 覆蓋)
  CASDOOR_CLIENT_ID             — 本服務 application 的 client_id(aud 校驗)
  CASDOOR_JWT_PUBLIC_KEY(_FILE) — 簽章驗證公鑰 PEM(cert-built-in;bootstrap 腳本可匯出)

身分映射(CR-0141 D2):Casdoor 原生 sub ≠ 我們的 users.id,FK 體系全繫 users.id;
bootstrap 把 `smartlock_user_id`/`tenant_id`/`smartlock_role` 寫進 Casdoor user
properties,本模組把 claims 正規化為與自簽 JWT 同形 payload——下游
(deps.get_current_user 的 jti/A2/A3 重查、role_required)零改動。
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from jose import JWTError, jwt

logger = logging.getLogger("api.oidc")


class OIDCError(Exception):
    """OIDC 驗證失敗(呼叫端轉 401)。"""


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
    """驗 Casdoor RS256 token → 正規化 payload(與自簽 JWT 同形)。

    回傳:{sub, role, tenant_id, type='access', jti, iat}
    失敗丟 OIDCError(簽章/過期/iss/aud 不符、身分映射缺漏)。
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
        raise OIDCError(f"OIDC token 驗證失敗:{e}") from e

    props = payload.get("properties") or {}
    user_id = props.get("smartlock_user_id", "")
    if not user_id:
        # 未經 bootstrap 映射的 Casdoor 帳號一律拒絕——身分無法對回 users.id
        # (FK/audit 體系),不可 fallback 到 Casdoor 原生 sub。
        raise OIDCError("token 缺 smartlock_user_id 映射(帳號未同步)")

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
