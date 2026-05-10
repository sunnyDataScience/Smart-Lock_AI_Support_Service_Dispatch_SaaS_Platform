# Serverless 架構快速上線計畫 — 路線 D 漸進式架構

> **版本:** v1.0 | **日期:** 2026-04-21
> **目標:** 以 Jobber 為標竿，快速上線多租戶派工 SaaS，4 週交付第一個租戶
> **關聯文件:**
> - `docs/02-design/platform-multi-tenant/multi-tenant-architecture.md` — 多租戶架構
> - `docs/02-design/platform-multi-tenant/business-model-strategy.md` — 商業模式
> - `docs/02-design/platform-multi-tenant/external-factors-checklist.md` — 外部因素
> - `web_design_spec_prompt_pipeline/` — 前端設計規格全集 (28 頁 + Design System)

---

## 1. 決策背景

### 1.1 為什麼不選其他路線

| 路線 | 方案 | 否決原因 |
|------|------|---------|
| A | Vercel + Supabase (全託管) | Supabase DB 連線數上限 200，百租戶後瓶頸；雙 DB 同步噩夢 |
| B | 全 GCP Serverless | Cloud Run 前端需自配 Docker，無 CDN 優勢；缺內建 Auth |
| C | AWS Serverless | 已在 GCP 生態，遷移成本過高，無戰略價值 |
| **D** | **Vercel 前端 + Cloud Run 後端 + Cloud SQL (現有)** | **推薦 — 零遷移風險，漸進擴展** |

### 1.2 Jobber 架構參考

Jobber（$1B 估值，200K+ 租戶）至今仍使用：
- Ruby on Rails **單體**（非微服務）
- React + TypeScript 前端
- PostgreSQL (shared DB + tenant_id)
- AWS EKS (Kubernetes，後期才上)
- Sidekiq + Redis (背景任務)
- GraphQL API

**核心教訓：架構複雜度遠不如產品市場契合 (PMF) 重要。單體 + PostgreSQL 可以撐到 $1B。**

---

## 2. 推薦架構 — Phase 1 (0-100 租戶)

```
┌─────────────────────────────────────────────────────┐
│                 Phase 1 架構 (0-100 租戶)              │
│                                                      │
│  ┌────────────┐         ┌─────────────────────┐     │
│  │  Vercel    │  REST   │   Cloud Run         │     │
│  │  Next.js 14│────────→│   FastAPI 單體       │     │
│  │  (Frontend)│         │   (現有 + 擴充)      │     │
│  │            │         │                     │     │
│  │  Admin     │         │  ┌─ AI Agent ──────┐│     │
│  │  Panel     │         │  │ LINE Bot (V1.0) ││     │
│  │  +         │         │  │ LLM Gateway     ││     │
│  │  Tech PWA  │         │  │ Dispatch API    ││     │
│  │            │         │  │ Work Order API  ││     │
│  └─────┬──────┘         │  └─────────────────┘│     │
│        │                └──────────┬──────────┘     │
│        │ JWT Auth                  │ Cloud SQL Proxy │
│        ▼                           ▼                │
│  ┌──────────────────────────────────────────────┐   │
│  │          Cloud SQL PostgreSQL 16              │   │
│  │  ┌──────────┐ ┌───────────┐ ┌─────────────┐ │   │
│  │  │ pgvector │ │ RLS Policy│ │ tenant_id   │ │   │
│  │  │ (AI KB)  │ │ (隔離)    │ │ (每張表)    │ │   │
│  │  └──────────┘ └───────────┘ └─────────────┘ │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Cloud Tasks  │  │ GCS          │                 │
│  │ (派工通知)    │  │ (照片/媒體)   │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### 2.1 技術選型

| 層級 | 選型 | 理由 |
|------|------|------|
| **Frontend Hosting** | Vercel (Free → Pro $20/月) | Next.js 原生支援，全球 CDN，零配置部署 |
| **Frontend Framework** | Next.js 14 (App Router) + React 19 | 設計規格已定義，SSR + Edge 能力 |
| **UI Library** | shadcn/ui + Tailwind CSS 3.4 | Design System 已定義全部 token |
| **State Management** | TanStack Query + Zustand | Server state + Client state 分離 |
| **Backend** | Cloud Run + FastAPI (現有) | 零遷移，只擴充 endpoints |
| **Database** | Cloud SQL PostgreSQL 16 (現有) | 零遷移，已有 pgvector + checkpoint |
| **Auth** | 自建 JWT (FastAPI middleware) | 多租戶 RBAC 已設計，不依賴第三方 |
| **Realtime** | PostgreSQL LISTEN/NOTIFY → Phase 2 升級 Pub/Sub | 漸進式，Phase 1 用 polling 也可 |
| **Background Jobs** | Cloud Tasks | 派工通知、SLA 監控、報表生成 |
| **File Storage** | GCS (現有) | 完工照片、手冊 PDF |
| **Maps** | Google Maps API (@vis.gl/react-google-maps) | 派工地圖、技師定位 |
| **DnD** | @dnd-kit/core | Kanban 拖拉派工 |
| **Charts** | Recharts | Dashboard KPI 圖表 |
| **LLM** | 現有 multi-provider (Gemini/Claude/GPT) | 不變 |

### 2.2 不使用 Supabase DB 的原因

```
路線 A 的問題（雙 DB）：
  Frontend → Supabase DB (Auth + Realtime)
  FastAPI  → Cloud SQL   (AI + 業務邏輯)
  結果：工單資料要在兩個 DB 之間同步 = 噩夢

路線 D 的優勢（單一 DB）：
  Frontend → FastAPI → Cloud SQL (唯一 DB)
  Auth：FastAPI JWT middleware（tenant-aware）
  Realtime：Phase 1 用 polling + TanStack Query refetch
            Phase 2 用 PostgreSQL LISTEN/NOTIFY
            Phase 3 用 Cloud Pub/Sub
```

---

## 3. 漸進式擴展路徑

### Phase 1: 快速上線 (0-100 租戶)

| 元件 | 方案 | 月費 |
|------|------|------|
| Vercel (Next.js) | Free → Pro $20 | $0-20 |
| Cloud Run (FastAPI) | 現有，擴充 | $15-80 |
| Cloud SQL (PostgreSQL) | 現有，加 RLS | $10-100 |
| Cloud Tasks | 按量 | $1-5 |
| GCS | 現有 | $1-10 |
| Google Maps API | $200 免費額度 | $0-50 |
| **合計** | | **$30-250/月** |

### Phase 2: 穩定成長 (100-1K 租戶)

| 升級項目 | 做法 | 新增月費 |
|---------|------|---------|
| DB Read Replica | Cloud SQL 加副本 | +$100 |
| PgBouncer | 連線池（Cloud SQL 內建 pgbouncer） | $0 |
| Redis Cache | Memorystore (tenant config 快取) | +$50 |
| Cloud Pub/Sub | 替代 LISTEN/NOTIFY (跨域事件) | +$20 |
| Background Worker | 獨立 Cloud Run service (Celery-like) | +$50 |
| CDN | Cloud CDN for API responses | +$20 |
| **合計** | | **~$500-1,000/月** |

### Phase 3: 規模化 (1K-10K+ 租戶)

| 升級項目 | 做法 | 新增月費 |
|---------|------|---------|
| Kubernetes | Cloud Run → GKE Autopilot | 按量 |
| 微服務拆分 | Dispatch / Billing / Notification 獨立服務 | — |
| CQRS | 讀寫分離（報表走 BigQuery） | +$200 |
| 大租戶專用實例 | Enterprise 客戶獨立 Cloud SQL | 按合約 |
| 多區域部署 | asia-east1 + us-central1 | 2x 費用 |
| **合計** | | **$5,000+/月** |

### 擴展觸發條件

| 指標 | 閾值 | 動作 |
|------|------|------|
| DB 連線數 | > 150 concurrent | 加 PgBouncer |
| DB QPS | > 5K | 加 Read Replica |
| 單租戶流量 > 30% | — | 獨立實例 |
| Cloud Run 延遲 P95 > 2s | — | 水平擴展或拆服務 |
| 背景任務排隊 > 5 分鐘 | — | 獨立 Worker service |

---

## 4. 多租戶架構要點

### 4.1 數據隔離 — PostgreSQL RLS

```sql
-- 每張業務表都有 tenant_id
ALTER TABLE work_orders ADD COLUMN tenant_id UUID NOT NULL;
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON work_orders
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- FastAPI middleware 在每個請求設置 tenant context
SET app.current_tenant_id = '{tenant_uuid}';
```

### 4.2 Auth — JWT + RBAC

```json
{
    "sub": "user-uuid",
    "tenant_id": "tenant-uuid",
    "role": "tenant_admin",
    "permissions": ["work_orders:read", "work_orders:write", "technicians:manage"],
    "exp": 1714300000
}
```

角色層級：
```
platform_super_admin (平台管理員)
└── tenant_admin (租戶管理員)
    ├── tenant_reviewer (客服主管)
    ├── tenant_technician (技師)
    └── tenant_readonly (唯讀)
```

### 4.3 LINE 多租戶路由

```
每個租戶擁有自己的 LINE Official Account
                    ↓
LINE Platform → POST /webhook (統一入口)
                    ↓
TenantResolver: destination (channel_id) → tenant_id
                    ↓
SET app.current_tenant_id → 所有後續查詢自動隔離
```

### 4.4 知識庫三層繼承

```
Platform Layer (所有租戶共享)
├── LLM Engine + ReAct Runtime
├── 通用 Skills (_common/)
├── 品牌 OEM SOP
│
└── Tenant Layer (租戶覆寫)
    ├── AI 人設 (agent_persona)
    ├── 品牌/型號清單
    ├── 安全詞彙
    ├── 自訂 SOP
    └── LINE OA 配置
```

### 4.5 定價方案

| Plan | 月費 | 對話額度 | 技師席位 | 超額 |
|------|------|---------|---------|------|
| Starter | NT$ 2,000 | 500 | 2 | NT$ 3/msg |
| Professional | NT$ 6,000 | 2,000 | 10 | NT$ 2/msg |
| Business | NT$ 15,000 | 10,000 | 不限 | NT$ 1.5/msg |
| Enterprise | 議價 | 專用實例 | 自訂 | 議價 |

---

## 5. 四週實施計畫

### Week 0: 基礎設施 (2 天)

```
□ Cloud SQL 執行 multi-tenant migration
  ├── CREATE TABLE tenants (...)
  ├── ALTER TABLE ... ADD COLUMN tenant_id
  ├── CREATE POLICY tenant_isolation ON ...
  └── 插入第一個測試租戶
□ Vercel 建立 Next.js 14 專案
  ├── npx create-next-app@latest --typescript --tailwind --app
  ├── 安裝 shadcn/ui + 配置 Design Tokens
  ├── 設定環境變數 (API_BASE_URL, MAPS_KEY)
  └── 首次部署確認
□ Cloud Run FastAPI 擴充
  ├── 新增 /api/v1/auth/* endpoints
  ├── 新增 /api/v1/work-orders/* endpoints (CRUD)
  ├── JWT middleware + tenant_id extraction
  └── CORS 設定 Vercel domain
```

### Week 1: Auth + Admin 核心 (5 天)

```
□ 登入系統
  ├── POST /api/v1/auth/login (email + password → JWT)
  ├── POST /api/v1/auth/register (tenant_admin 自註冊)
  ├── Next.js login 頁面 + JWT token 管理
  └── Protected route middleware
□ Admin Dashboard
  ├── 使用 assembly/02_admin_dashboard_integrated.md → AI 產 code
  ├── KPI 卡片 (TanStack Query polling)
  ├── 趨勢圖表 (Recharts)
  └── 最近工單表格
□ Work Order 列表
  ├── 使用 assembly/03_dispatch_board_integrated.md → AI 產 code
  ├── 列表視圖 + 狀態篩選
  ├── API: GET /api/v1/work-orders?status=&tenant_id=
  └── 13 狀態 StatusBadge 元件
```

### Week 2: 派工 + 技師 (5 天)

```
□ Kanban 派工板
  ├── @dnd-kit 拖拉 + Optimistic UI
  ├── PATCH /api/v1/work-orders/{id}/assign
  ├── 技師匹配 API (35% 距離 + 30% 技能 + 20% 評分 + 15% 負載)
  └── Manual Assign Modal
□ 地圖視圖
  ├── Google Maps + 技師/工單圖釘
  ├── List + Map split view
  └── Pin click → popup → assign
□ 技師管理
  ├── 技師 CRUD API
  ├── 技師列表 + 詳情頁
  └── 技能矩陣 + 排班
□ Work Order Detail
  ├── 使用 assembly/08_admin_work_order_detail_integrated.md
  ├── 時間軸 + ProblemCard + 設備面板
  └── 狀態操作按鈕
```

### Week 3: Technician PWA + 完工 (5 天)

```
□ Tech Login
  ├── 手機 + OTP 登入
  ├── JWT with role=technician
  └── 自動導向 /pool
□ Case Pool (地圖)
  ├── 使用 assembly/04_tech_pool_integrated.md
  ├── Full-screen Map + BottomSheet
  ├── Swipe to accept/skip
  └── GPS 定位更新
□ My Orders + Completion
  ├── 使用 assembly/12_tech_my_orders_integrated.md
  ├── 進行中/待確認/歷史 三 tab
  ├── 完工報告表單 (照片+簽名+測試)
  └── GCS 照片上傳
□ PWA 配置
  ├── manifest.json + service-worker.js
  ├── Offline 基本支援 (cached order list)
  └── Add to Home Screen prompt
```

### Week 4: 整合測試 + 上線 (5 天)

```
□ 帳務基礎
  ├── Settlement 列表 + 詳情
  ├── Invoice 自動生成
  └── 月結報表
□ 知識庫管理
  ├── 案例庫 CRUD (遷移 V1.0)
  ├── SOP 審核佇列
  └── 手冊上傳
□ 多租戶測試
  ├── 建立 Tenant A + Tenant B
  ├── 驗證 RLS 隔離 (A 看不到 B 的資料)
  ├── 驗證 LINE webhook 路由
  └── 壓力測試 (10 concurrent users)
□ Production Deploy
  ├── Vercel production domain
  ├── Cloud Run 正式環境
  ├── DNS + SSL 設定
  └── 第一個真實租戶 onboarding
```

---

## 6. Assembly Prompt 使用指南

已產出的 12 個 Assembly 文件可直接餵給 AI (Claude / Cursor / Lovable) 產出頁面程式碼：

| Assembly 文件 | 對應頁面 | Week |
|--------------|---------|------|
| `assembly/02_admin_dashboard_integrated.md` | Dashboard | W1 |
| `assembly/03_dispatch_board_integrated.md` | 派工板 (Kanban+Map+List) | W1-W2 |
| `assembly/04_tech_pool_integrated.md` | 技師案件池 | W3 |
| `assembly/05_admin_conversations_integrated.md` | 對話管理 | W4+ |
| `assembly/06_admin_problem_cards_integrated.md` | 問題卡管理 | W4+ |
| `assembly/07_admin_knowledge_base_integrated.md` | 知識庫 | W4 |
| `assembly/08_admin_work_order_detail_integrated.md` | 工單詳情 | W2 |
| `assembly/09_admin_technicians_integrated.md` | 技師管理 | W2 |
| `assembly/10_admin_accounting_integrated.md` | 帳務結算 | W4 |
| `assembly/11_admin_advanced_integrated.md` | 進階管理 | W5+ |
| `assembly/12_tech_my_orders_integrated.md` | 技師工單 | W3 |
| `assembly/13_tech_account_integrated.md` | 技師帳戶 | W3 |

**使用方式：**
1. 複製 Assembly 文件內容
2. 貼入 Claude Code / Cursor
3. AI 產出完整 React + shadcn/ui + Tailwind 程式碼
4. 微調後整合進 Next.js 專案

---

## 7. 風險與緩解

| 風險 | 影響 | 緩解 |
|------|------|------|
| Cloud SQL 冷啟動 | 首次連線延遲 2-3s | 設定 Cloud SQL min instances = 1 |
| Cloud Run 冷啟動 | LLM 初始化 5-10s | 設定 min instances = 1 (非零) |
| LINE webhook 30s 回應限制 | AI 回應超時 | 現有 debounce 機制 + 先回 reply 再 push |
| 單 DB 效能 | 百租戶後查詢變慢 | 索引優化 + Phase 2 加 Read Replica |
| 前端 bundle size | 地圖 + 圖表 + DnD 太大 | Next.js dynamic import + code splitting |
| 多租戶資料洩漏 | RLS policy 漏洞 | 自動化 RLS 隔離測試 + 每次部署驗證 |

---

## 8. 成本預估

| 階段 | 租戶數 | Vercel | Cloud Run | Cloud SQL | 其他 GCP | 合計/月 |
|------|--------|--------|-----------|-----------|---------|---------|
| MVP | 1-5 | $0 | $15 | $10 | $5 | **~$30** |
| 驗證 | 5-30 | $20 | $30 | $30 | $20 | **~$100** |
| 成長 | 30-100 | $20 | $80 | $100 | $50 | **~$250** |
| 規模 | 100-500 | $20 | $300 | $400 | $200 | **~$900** |
| 企業 | 500+ | $20 | $1,000+ | $1,000+ | $500+ | **$2,500+** |

**對比 Jobber 定價**：Jobber 收 $40-200/月/技師。10 個租戶 × 平均 5 技師 = NT$ 300K/月收入，遠超基礎設施成本。

---

## 9. 與現有文件的關係

```
docs/
├── 01-define/
│   └── E3x--module-breakdown.md          ← 模組依賴，決定 API 擴充順序
├── 02-design/
│   ├── E5x--workflow-work-order  ← 工單狀態機，決定 API 行為
│   ├── E5x--frontend-information-arch     ← 28 頁 IA，已轉化為 page specs
│   ├── E5x--frontend-architecture         ← 前端技術規範
│   ├── platform-multi-tenant/
│   │   ├── multi-tenant-architecture.md   ← 多租戶核心設計（本計畫依此）
│   │   ├── business-model-strategy.md     ← 定價模型
│   │   └── external-factors-checklist.md  ← LINE 限制等外部因素
│   └── dispatch-integration-spec          ← AI Agent → 派工串接
├── 03-plan/
│   └── serverless-architecture-plan.md    ← ★ 本文件
└── web_design_spec_prompt_pipeline/
    ├── global/02_smartlock_dispatch_brand_system.md  ← Design Token 來源
    ├── pages/*.md                                    ← 28 頁規格
    ├── assembly/*.md                                 ← 12 個 AI Prompt
    └── design-system-specs/smartlock/*.md             ← 完整 Design System
```

---

**版本資訊：**
- 當前版本：v1.0
- 建立日期：2026-04-21
- 決策者：{PM / Tech Lead}
- 下次審查：Phase 1 完成後 (Week 4)
