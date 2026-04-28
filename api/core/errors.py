"""統一錯誤格式 — 對齊 openapi.yaml 的 ApiErrorResponse schema。

Format:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Field 'email' is required",
  "request_id": "req-xxx",
  "timestamp": "2026-04-27T12:00:00Z",
  "details": [...]
}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("api.errors")


class ApiError(Exception):
    """應用層錯誤（業務錯誤）— 直接帶 error_code 與 status code。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: list[dict] | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class ApiErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: list[dict] = Field(default_factory=list)


def _build_response(req: Request, err: ApiError) -> JSONResponse:
    body = ApiErrorResponse(
        error_code=err.error_code,
        message=err.message,
        request_id=getattr(req.state, "request_id", None),
        details=err.details,
    ).model_dump()
    return JSONResponse(status_code=err.status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(req: Request, err: ApiError):
        return _build_response(req, err)

    @app.exception_handler(HTTPException)
    async def handle_http(req: Request, err: HTTPException):
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
        }
        return _build_response(
            req,
            ApiError(
                error_code=code_map.get(err.status_code, "HTTP_ERROR"),
                message=str(err.detail) if err.detail else "",
                status_code=err.status_code,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(req: Request, err: RequestValidationError):
        details: list[dict[str, Any]] = []
        for e in err.errors():
            details.append({
                "field": ".".join(str(x) for x in e.get("loc", [])),
                "issue": e.get("msg", ""),
                "type": e.get("type", ""),
            })
        return _build_response(
            req,
            ApiError(
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                status_code=422,
                details=details,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(req: Request, err: Exception):
        logger.exception("Unhandled error on %s %s", req.method, req.url.path)
        return _build_response(
            req,
            ApiError(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                status_code=500,
            ),
        )
