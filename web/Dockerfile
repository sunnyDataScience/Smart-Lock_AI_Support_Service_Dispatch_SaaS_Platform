# syntax=docker/dockerfile:1.7
#
# web/Dockerfile — Smart Lock 四站台共用參數化建置（Next.js 15 standalone + npm workspaces）
#
# 2026-07-08 檔案層拆分（0707 AI #2 完整版）：web/ 轉 monorepo
#   apps/{dispatch,tech,landing,platform} + packages/shared
#   同一份 Dockerfile 以 ARG APP 選擇要建的站台。
#
# Build context: 專案根目錄（與 agent / api 一致，可共用 .dockerignore）
# 範例：docker build -f web/Dockerfile --build-arg APP=tech -t smart-lock-tech-web .
#
# 三階段：
#   deps    : npm ci 裝 workspaces node_modules（cache layer；只 copy 各 package.json）
#   builder : next build -w apps/$APP → .next/standalone（monorepo 佈局，含 minimal node_modules）
#   runtime : node:slim + 只 copy standalone + static + public，無 npm / build tool

ARG NODE_VERSION=20

# ────────────────────────────────────────────────────────────────────────────
# Stage 1 — Dependencies（workspaces）
# ────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS deps

WORKDIR /app

# 只 copy lockfile + 各 workspace 的 package.json，享 layer cache
# （程式碼變動不重裝 deps；新增 workspace 需在此補一行）
COPY web/package.json web/package-lock.json* ./
COPY web/apps/dispatch/package.json ./apps/dispatch/
COPY web/apps/tech/package.json ./apps/tech/
COPY web/apps/landing/package.json ./apps/landing/
COPY web/apps/platform/package.json ./apps/platform/
COPY web/packages/shared/package.json ./packages/shared/

RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# ────────────────────────────────────────────────────────────────────────────
# Stage 2 — Builder
# ────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS builder

# 要建哪個站台（dispatch | tech | landing | platform）
ARG APP=dispatch

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules

# Copy 全部 web/ 原始碼（monorepo root）
COPY web/ ./

# 確保 public/ 至少存在（standalone runtime copy 需要）
RUN mkdir -p apps/${APP}/public

# NEXT_PUBLIC_* 變數在 next build 時「烤」進前端 bundle（standalone 後無法再改），
# 故必須是 build-time ARG → ENV。各站台用到的子集不同，未用者留空無害。
ARG NEXT_PUBLIC_REALTIME_BASE_URL=""
ENV NEXT_PUBLIC_REALTIME_BASE_URL=${NEXT_PUBLIC_REALTIME_BASE_URL}
ARG NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
# APP_MODE 仍烤入（appMode.ts 的跨站導向/CTA 解析依賴；正常應與 ARG APP 一致）
ARG NEXT_PUBLIC_APP_MODE=""
ENV NEXT_PUBLIC_APP_MODE=${NEXT_PUBLIC_APP_MODE}
ARG NEXT_PUBLIC_PEER_PORTAL_URL=""
ENV NEXT_PUBLIC_PEER_PORTAL_URL=${NEXT_PUBLIC_PEER_PORTAL_URL}
ARG NEXT_PUBLIC_TECH_PORTAL_URL=""
ENV NEXT_PUBLIC_TECH_PORTAL_URL=${NEXT_PUBLIC_TECH_PORTAL_URL}
ARG NEXT_PUBLIC_DISPATCH_PORTAL_URL=""
ENV NEXT_PUBLIC_DISPATCH_PORTAL_URL=${NEXT_PUBLIC_DISPATCH_PORTAL_URL}
ARG NEXT_PUBLIC_PLATFORM_API_BASE_URL=""
ENV NEXT_PUBLIC_PLATFORM_API_BASE_URL=${NEXT_PUBLIC_PLATFORM_API_BASE_URL}
ARG NEXT_PUBLIC_PLATFORM_PORTAL_URL=""
ENV NEXT_PUBLIC_PLATFORM_PORTAL_URL=${NEXT_PUBLIC_PLATFORM_PORTAL_URL}
ARG NEXT_PUBLIC_GCP_MONITORING_URL=""
ENV NEXT_PUBLIC_GCP_MONITORING_URL=${NEXT_PUBLIC_GCP_MONITORING_URL}

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w apps/${APP}

# ────────────────────────────────────────────────────────────────────────────
# Stage 3 — Runtime
# ────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine

ARG APP=dispatch

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# APP 烤成 ENV 供 CMD 使用（standalone 的 server.js 位於 monorepo 相對路徑下）
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080 \
    HOSTNAME=0.0.0.0 \
    APP=${APP}

# monorepo standalone：輸出根含 node_modules + apps/${APP}/server.js
COPY --from=builder --chown=nextjs:nodejs /app/apps/${APP}/.next/standalone ./
# 靜態資源不在 standalone 內，要放到 app 相對路徑下
COPY --from=builder --chown=nextjs:nodejs /app/apps/${APP}/.next/static ./apps/${APP}/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/${APP}/public ./apps/${APP}/public

USER nextjs
EXPOSE 8080

CMD ["sh", "-c", "exec node apps/${APP}/server.js"]
