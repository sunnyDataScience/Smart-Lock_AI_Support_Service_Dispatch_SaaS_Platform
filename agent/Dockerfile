# syntax=docker/dockerfile:1.7
#
# agent/Dockerfile — Smart Lock LINE Bot Agent 容器化映像（uv workspace）
#
# Build context: 專案根目錄（不是 agent/）
# 範例：docker build --platform linux/amd64 -f agent/Dockerfile -t smart-lock-agent .
#
# 此映像由兩階段組成：
#   builder：拉 deps（用 uv，享 .uv/cache mount + bytecode 預編譯）
#   runtime：只帶 venv + agent 原始碼，不含 uv binary 與 build tools

ARG PYTHON_VERSION=3.11

# ────────────────────────────────────────────────────────────────────────────
# Stage 1 — Builder
# ────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# 從 Astral 官方 image 直接 COPY uv binary（比 pip install uv 快 + 體積小）
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

# uv 環境變數調校
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_PROGRESS=1

WORKDIR /app

# Stage 1a — 先只 copy 鎖定檔，跑 sync。Docker layer cache 友善，
# 之後只改 agent/ 程式不用重 sync deps（10 倍加速）
COPY pyproject.toml uv.lock .python-version ./
COPY agent/pyproject.toml ./agent/pyproject.toml
COPY api/pyproject.toml ./api/pyproject.toml
COPY data/pyproject.toml ./data/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package smart-lock-agent

# Stage 1b — 把 agent 程式碼搬進來（這層改動頻繁，獨立 cache）
COPY agent/ ./agent/

# ────────────────────────────────────────────────────────────────────────────
# Stage 2 — Runtime
# ────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm

# 只裝 runtime 必需的系統 lib（psycopg[binary] 自帶，多數套件無 C 依賴）
# 若日後加入需編譯的套件，把編譯放在 builder stage、runtime 維持 slim

WORKDIR /app

# 從 builder stage 抓 venv + 程式碼
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/agent /app/agent

# 用 venv 內的 binaries 而不依賴 system PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app/agent
EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
