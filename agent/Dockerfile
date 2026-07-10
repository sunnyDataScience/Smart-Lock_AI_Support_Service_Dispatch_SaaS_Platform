# syntax=docker/dockerfile:1.7
#
# agent/Dockerfile — LockCore CS Agent（LINE gateway）容器化映像（uv workspace）
#
# Build context: 專案根目錄（不是 agent/）
# 範例：docker build --platform linux/amd64 -f agent/Dockerfile -t smart-lock-agent .
#
# 對齊 api/Dockerfile 的 multi-stage uv build。差異：
#   - 同步 lock-cs-agent package + line / vertex 兩個 optional extra（LINE 通道 + Vertex AI）。
#   - 入口是 scripts/line_gateway.py（aiohttp webhook），讀 PORT 環境變數（Cloud Run 設 8080）。
#   - 機密（LINE_CHANNEL_* / POSTGRES_URI）由 Cloud Run Secret Manager 注入，不入映像；
#     Vertex 認證走 Cloud Run service account ADC（無 credentials.json 時自動 fallback）。
#   - 機密 / 本機 DB / 快取由 agent/Dockerfile.dockerignore 擋在 build context 外。

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

# Cache-friendly：先鎖定檔與各 workspace member 的 pyproject，再原始碼
COPY pyproject.toml uv.lock .python-version ./
COPY agent/pyproject.toml ./agent/pyproject.toml
COPY api/pyproject.toml ./api/pyproject.toml
COPY knowledge-pipeline/pyproject.toml ./knowledge-pipeline/pyproject.toml
COPY rag/pyproject.toml ./rag/pyproject.toml
COPY refinery/pyproject.toml ./refinery/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package lock-cs-agent --extra line --extra vertex

COPY agent/ ./agent/

# ────────────────────────────────────────────────────────────────────────────
# Stage 2 — Runtime
# ────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/agent /app/agent

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/app/agent

WORKDIR /app/agent
EXPOSE 8080

# line_gateway 以「腳本」方式跑（非安裝的套件），sys.path[0]=scripts/ 不含 /app/agent，
# 故 PYTHONPATH=/app/agent 讓 `import lockcore` 從 COPY 進來的原始碼解析
# （workspace 套件在 build 階段 wheel 不含 lockcore 原始碼，改由原始碼樹提供）。
CMD ["python", "scripts/line_gateway.py"]
