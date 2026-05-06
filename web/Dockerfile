# syntax=docker/dockerfile:1.7
#
# web/Dockerfile — Smart Lock Admin Dashboard 容器化（Next.js 15 standalone）
#
# Build context: 專案根目錄（與 agent / api 一致，可共用 .dockerignore）
# 範例：docker build --platform linux/amd64 -f web/Dockerfile -t smart-lock-web .
#
# 三階段：
#   deps    : 用 npm ci 純裝 node_modules（cache layer）
#   builder : next build → 產生 .next/standalone（含內嵌 minimal node_modules）
#   runtime : node:slim + 只 copy standalone + static + public，無 npm / build tool

ARG NODE_VERSION=20

# ────────────────────────────────────────────────────────────────────────────
# Stage 1 — Dependencies
# ────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS deps

WORKDIR /app

# 先 copy lockfile，享 layer cache（程式碼變動不需要重裝 deps）
COPY web/package.json web/package-lock.json* ./

RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# ────────────────────────────────────────────────────────────────────────────
# Stage 2 — Builder
# ────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS builder

WORKDIR /app

# 先用 deps 階段裝好的 node_modules
COPY --from=deps /app/node_modules ./node_modules

# Copy 全部 web/ 原始碼
COPY web/ ./

# 確保 public/ 至少存在（Next.js 不一定有，但 standalone runtime 要 copy）
RUN mkdir -p public

# 跑 next build（next.config.ts 設了 output: standalone）
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ────────────────────────────────────────────────────────────────────────────
# Stage 3 — Runtime
# ────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine

WORKDIR /app

# 用非 root user（Cloud Run 不強制但安全）
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Cloud Run 預設用 PORT 環境變數，Next.js standalone 也支援
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080 \
    HOSTNAME=0.0.0.0

# 從 builder 撈 standalone bundle（已含 minimal node_modules + server.js）
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# 靜態資源不在 standalone 內，要單獨 copy
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 8080

# standalone 模式產生的入口是 server.js
CMD ["node", "server.js"]
