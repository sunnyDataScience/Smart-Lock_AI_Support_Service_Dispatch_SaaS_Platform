"""內部 Pydantic models（OpenAPI 不該暴露的型別）。"""

from __future__ import annotations

from pydantic import BaseModel


class JwtClaims(BaseModel):
    sub: str
    role: str
    tenant_id: str
    type: str
    iat: int
    exp: int
    jti: str
