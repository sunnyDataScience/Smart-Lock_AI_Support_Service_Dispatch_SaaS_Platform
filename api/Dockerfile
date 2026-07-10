# syntax=docker/dockerfile:1.7
#
# api/Dockerfile — Smart Lock REST API 容器化映像（uv workspace）
#
# Build context: 專案根目錄（不是 api/）
# 範例：docker build --platform linux/amd64 -f api/Dockerfile -t smart-lock-api .

ARG PYTHON_VERSION=3.11

# ────────────────────────────────────────────────────────────────────────────
# Stage 1 — Builder
# ────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_PROGRESS=1

WORKDIR /app

# Cache-friendly：先鎖定檔，再原始碼
COPY pyproject.toml uv.lock .python-version ./
COPY agent/pyproject.toml ./agent/pyproject.toml
COPY api/pyproject.toml ./api/pyproject.toml
COPY knowledge-pipeline/pyproject.toml ./knowledge-pipeline/pyproject.toml
COPY rag/pyproject.toml ./rag/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package smart-lock-api

COPY api/ ./api/

# ────────────────────────────────────────────────────────────────────────────
# Stage 2 — Runtime
# ────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/api /app/api

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app/api
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
