# syntax=docker/dockerfile:1.7
#
# refinery/Dockerfile — knowledge-refinery 審核服務容器（uv workspace）
#
# Build context: 專案根目錄
# 範例：docker build --platform linux/amd64 -f refinery/Dockerfile -t smart-lock-refinery .
# ADR-018：License 開通附加系統；compose 走 profile "refinery"（預設不啟動）。

ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_PROGRESS=1

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY agent/pyproject.toml ./agent/pyproject.toml
COPY api/pyproject.toml ./api/pyproject.toml
COPY knowledge-pipeline/pyproject.toml ./knowledge-pipeline/pyproject.toml
COPY rag/pyproject.toml ./rag/pyproject.toml
COPY refinery/pyproject.toml ./refinery/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package smart-lock-refinery

COPY refinery/ ./refinery/

FROM python:${PYTHON_VERSION}-slim-bookworm

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/refinery /app/refinery

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app/refinery
EXPOSE 8080

CMD ["sh", "-c", "uvicorn refinery.service:app --host 0.0.0.0 --port ${PORT}"]
