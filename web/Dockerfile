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

# NEXT_PUBLIC_* 變數在 next build 時「烤」進前端 bundle（standalone 後無法再改），
# 故必須是 build-time ARG → ENV。即時推送（WebSocket）base：未傳則留空 = 前端顯示
# 「未配置」並走優雅降級（不訂閱、頁面仍以一般 fetch 運作）。
# 本機 docker：ws://localhost:8001（瀏覽器直連 api published port）；
# Cloud Run：wss://<api 網域>（同 arg 換值即可）。
ARG NEXT_PUBLIC_REALTIME_BASE_URL=""
ENV NEXT_PUBLIC_REALTIME_BASE_URL=${NEXT_PUBLIC_REALTIME_BASE_URL}

# API base URL：未傳（本機 compose）→ 空字串 → 前端 code 以 || fallback 到 localhost:8001；
# Cloud Run：web.sh 傳入 api 的 https URL（瀏覽器端呼叫）。
ARG NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

# CR-0112 雙 stack 拆分：部署模式（all|dispatch|tech，未傳 = all 零行為變化）
# 與對方 portal 絕對 URL（跨端連結/導向用；未傳 = 退回站內路由）。
ARG NEXT_PUBLIC_APP_MODE=""
ENV NEXT_PUBLIC_APP_MODE=${NEXT_PUBLIC_APP_MODE}
ARG NEXT_PUBLIC_PEER_PORTAL_URL=""
ENV NEXT_PUBLIC_PEER_PORTAL_URL=${NEXT_PUBLIC_PEER_PORTAL_URL}

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
