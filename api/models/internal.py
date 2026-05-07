"""內部 Pydantic models（OpenAPI 不該暴露的型別）。

也包含尚未由 datamodel-codegen 重生 generated.py 前的 transitional schemas，
這類型別應於下次 `./scripts/ci/generate-api-types.sh` + 後端 codegen 後，
從 generated.py 取代並移除此處的副本，避免兩處定義漂移。
"""

from __future__ import annotations

from pydantic import AnyUrl, BaseModel, Field


class JwtClaims(BaseModel):
    sub: str
    role: str
    tenant_id: str
    type: str
    iat: int
    exp: int
    jti: str


class SendChatMessageRequest(BaseModel):
    """客服接管後發送訊息的 request body（OpenAPI: SendChatMessageRequest）。

    對應 POST /api/v1/conversations/{id}/messages（operationId: sendChatMessage）。
    待 generated.py 重生後可從 internal 移到 generated。
    """

    content: str = Field(..., min_length=1, max_length=5000)
    media_uri: AnyUrl | None = None
