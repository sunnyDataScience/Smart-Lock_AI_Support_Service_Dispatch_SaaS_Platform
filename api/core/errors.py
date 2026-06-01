"""統一錯誤格式 — RFC7807 problem+json superset。

Response body = RFC7807 fields + legacy extension members（零破壞）:
{
  // RFC7807 fields
  "type":     "urn:smartlock:error:validation_error",
  "title":    "Validation Error",
  "status":   422,
  "detail":   "Request validation failed",
  "instance": "/api/v1/auth/login",

  // Legacy extension members (RFC7807 §3.2 allows — backward-compat)
  "error_code": "VALIDATION_ERROR",
  "message":    "Request validation failed",
  "request_id": "req-xxx",
  "timestamp":  "2026-04-27T12:00:00Z",
  "details":    [...]
}

Content-Type: application/problem+json

Per D5 decision: type URI is an identifier string (not fetchable URL).
Format: urn:smartlock:error:{error_code_lowercase}

Reference: openapi-smart-lock-saas.yaml §1219 Error schema
           RFC7807 https://www.rfc-editor.org/rfc/rfc7807
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

# ---------------------------------------------------------------------------
# Error code → (HTTP status, human-readable title) map
# ---------------------------------------------------------------------------

_CODE_MAP: dict[str, tuple[int, str]] = {
    "BAD_REQUEST":       (400, "Bad Request"),
    "UNAUTHENTICATED":   (401, "Unauthenticated"),
    "FORBIDDEN":         (403, "Forbidden"),
    "NOT_FOUND":         (404, "Not Found"),
    "CONFLICT":          (409, "Conflict"),
    "VALIDATION_ERROR":  (422, "Validation Error"),
    "RATE_LIMITED":      (429, "Rate Limited"),
    "INTERNAL_ERROR":    (500, "Internal Server Error"),
}

# HTTP status → default error_code (used when converting HTTPException)
_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def _title_for(error_code: str) -> str:
    """Return a human-readable title for the given error_code."""
    entry = _CODE_MAP.get(error_code)
    if entry:
        return entry[1]
    # Fallback: convert snake_case to Title Case
    return error_code.replace("_", " ").title()


def _type_uri(error_code: str) -> str:
    """Return urn:smartlock:error:{error_code_lowercase} — not fetchable."""
    return f"urn:smartlock:error:{error_code.lower()}"


# ---------------------------------------------------------------------------
# Exception class & response model
# ---------------------------------------------------------------------------

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
    """RFC7807 superset error response schema.

    RFC7807 fields (new):
      type, title, status, detail, instance

    Legacy extension members (backward-compat, RFC7807 §3.2):
      error_code, message, request_id, timestamp, details
    """
    # RFC7807 fields
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None

    # Legacy extension members (backward-compat)
    error_code: str
    message: str
    request_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------

def _build_response(req: Request, err: ApiError) -> JSONResponse:
    """Build RFC7807 application/problem+json response (superset)."""
    request_id = getattr(req.state, "request_id", None)
    # instance = request_id if available, else fall back to request path
    instance: str | None = request_id or req.url.path

    body = ApiErrorResponse(
        # RFC7807 fields
        type=_type_uri(err.error_code),
        title=_title_for(err.error_code),
        status=err.status_code,
        detail=err.message,
        instance=instance,
        # Legacy extension members
        error_code=err.error_code,
        message=err.message,
        request_id=request_id,
        details=err.details,
    ).model_dump()

    return JSONResponse(
        status_code=err.status_code,
        content=body,
        media_type="application/problem+json",
    )


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(req: Request, err: ApiError):
        return _build_response(req, err)

    @app.exception_handler(HTTPException)
    async def handle_http(req: Request, err: HTTPException):
        error_code = _STATUS_CODE_MAP.get(err.status_code, "HTTP_ERROR")
        return _build_response(
            req,
            ApiError(
                error_code=error_code,
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
