---
id: DS-0000
title: "Brand System"
tier: 2-contracts
status: active
owner: HYBRID
last-reviewed: 2026-05-15
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
---

# Brand System: Smart Lock AI Support & Service Dispatch Platform

> 這是 `BASE_DESIGN_SYSTEM.md` 的具體實作，用於「電子鎖智能客服與派工平台」。
> 對應 `SYSTEM_DOCUMENT_SPEC.md` 的四層架構。
> 風格依據：`references/ui_style_benchmark_report.md` 推薦組合方案（A+B+C+E）。

---

## [GLOBAL ROLE]

你是「電子鎖智能客服與派工平台」的資深產品架構師。你負責確保所有 AI 生成的網頁符合品牌的安全可靠、營運效率、數據即時性特質。

本平台採三端架構，共用一套 Design Token，但各端有獨立的佈局策略：

| 端 | 技術 | 佈局策略 | 核心風格 |
|:---|:-----|:---------|:---------|
| **Admin Panel** | Next.js 14 + React 19 + shadcn/ui | Desktop-First, 12 欄 Grid | 風格 A（KPI 卡片）+ 風格 B（Kanban 派工）|
| **Technician PWA** | Next.js 14 + React 19 + shadcn/ui | Mobile-First, 單欄 | 風格 C（地圖中心）+ 風格 E（設備面板）|
| **Consumer** | LINE Messaging API | LINE 原生 UI | Flex Message + Quick Reply |

---

## [PRODUCT CONTEXT LAYER]

- **產品名稱**：電子鎖智能客服與派工平台 (Smart Lock AI Support & Service Dispatch SaaS)
- **產品一句話**：以 AI 驅動的電子鎖售後服務中樞，從客戶報修到師傅完工一站式閉環。
- **目標用戶**：
  - 主要：電子鎖品牌商/經銷商的客服主管與營運管理者（Admin Panel）
  - 次要：現場維修技師（Technician PWA）、報修的終端消費者（LINE Bot）
- **核心價值主張**：用 AI 取代 80% 人工客服判斷，用自動化派工取代電話調度，將平均報修到完工時間從 48 小時壓縮至 4 小時。
- **網站類型**：B2B SaaS 後台管理 + B2C 行動服務端
- **啟用模組**（對應 `E3x--module-breakdown.md`）：
  - M1 LINE Bot 接入 🟢 V1.0
  - M2 對話管理 🟢 V1.0
  - M3 ProblemCard 引擎 🟢 V1.0
  - M4 三層解決引擎 🟢 V1.0
  - M5 知識庫管理 🟢 V1.0
  - M6 Admin Panel V1.0 🟢 V1.0
  - M7 SOP 自動生成 🟢 V1.0
  - M8 LLM Gateway 🟢 V1.0
  - M9 派工引擎 🟠 V2.0
  - M10 報價引擎 🟠 V2.0
  - M11 帳務模組 🟠 V2.0
  - M12 技師 Web App 🟠 V2.0
  - M13 Admin Panel V2.0 🟠 V2.0
- **主要任務流**：
  1. 消費者透過 LINE 報修 → AI 診斷 → 產出 ProblemCard → 自助解決 或 觸發派工
  2. 派工引擎匹配技師 → 技師接單/到場/完工回報 → 客戶確認 → 帳務結算
  3. 知識沉澱：完工案例 → AI 生成 SOP 草稿 → 管理員審核 → 入庫 → 提升下次解決率

---

## [BRAND & VOICE LAYER]

### 設計原則

| # | 原則 | 說明 | 當衝突時 |
|---|------|------|---------|
| 1 | 效率至上 | 每個頁面只服務一個核心任務，減少切換與等待 | 砍裝飾保操作速度 |
| 2 | 狀態透明 | 工單、技師、設備的狀態必須即時可見、色彩明確 | 增加狀態標示，即使版面更擁擠 |
| 3 | 數據說話 | 用數字和圖表取代形容詞，KPI 卡片優先於文字摘要 | 顯示「完工 87 單 / 逾時 3 單」而非「表現良好」 |
| 4 | 行動引導 | 空狀態和異常狀態必須提供下一步操作建議 | 提供明確 CTA 而非僅顯示錯誤 |
| 5 | 角色適配 | Admin 重全局監控密度；技師重單任務完成速度 | Admin 多資訊並排；技師單欄大按鈕 |

### 品牌性格

| 維度 | 我們是 | 我們不是 |
|------|--------|---------|
| 語氣 | 精準、可靠、有溫度 | 冷冰冰的系統通知 |
| 視覺 | 乾淨、專業、高資訊密度 | 花俏、裝飾性、低效 |
| 態度 | 效能導向、引導式 | 被動等待、資訊過載不整理 |
| 信任 | 安全感、穩定感 | 花哨、不穩定、廉價感 |

### 文案規則

- **稱呼用戶**：管理員稱「你」、技師稱「你」、消費者稱「您」（LINE Bot 較正式）
- **按鈕動詞**：主動語態 —「接受工單」「開始作業」「提交報告」「確認完工」
- **錯誤訊息**：先說發生什麼，再說怎麼修 —「派工失敗，該區域目前無可用技師，請手動指派」
- **空狀態**：引導行動 —「目前沒有待處理工單，查看歷史記錄」
- **狀態文字**：用精確動詞 —「已派工」「技師前往中」「作業中」「待確認」而非「處理中」
- **語言**：繁體中文為主，保留技術術語英文（ProblemCard, SLA, KPI, Kanban）
- **禁用詞**：
  - 避免空泛行銷話術（革命性、極致體驗、全方位）
  - 避免模糊狀態（處理中、稍等、盡快）— 改用具體時間或倒數
  - 避免雙重否定（不是不可以 → 可以）

---

## [VISUAL DESIGN SYSTEM LAYER]

### Color Tokens

#### 品牌色系

> 設計邏輯：主色選用深藍 (Trust Blue) 傳達安全與專業 — 電子鎖行業的核心信任色。
> 輔助色選用暗灰藍提供層次。強調色選用琥珀橙作為操作召喚色（CTA），
> 在大量藍灰介面中形成視覺焦點，符合派工系統「快速行動」的語義。

| Token | 色值 | 用途 | 語義 |
|-------|------|------|------|
| `color.primary` | #2563EB | 主要品牌色、導航、選中態 | Trust Blue — 安全與專業 |
| `color.primary.hover` | #1D4ED8 | 主色 hover | — |
| `color.primary.light` | #DBEAFE | 主色淺底、選中行背景 | — |
| `color.secondary` | #1E293B | 側邊導航背景、頁腳 | Slate Dark — 深度與權威 |
| `color.secondary.hover` | #334155 | 側邊導航 hover | — |
| `color.accent` | #F59E0B | CTA 按鈕、重要操作、徽章 | Amber — 行動召喚、注意力引導 |
| `color.accent.hover` | #D97706 | CTA hover | — |

#### 語義色系（工單狀態專用）

> 工單有 13 種狀態（對應 `E5x--workflow-work-order.md`），
> 以下定義 6 組語義色覆蓋所有狀態的視覺分類。

| Token | 色值 | 對應工單狀態 |
|-------|------|-------------|
| `color.status.pending` | #6366F1 (Indigo) | `created` 已建立 |
| `color.status.assigned` | #8B5CF6 (Violet) | `assigned` 已派工 |
| `color.status.active` | #3B82F6 (Blue) | `accepted` 已接受、`in_progress` 進行中 |
| `color.status.warning` | #F59E0B (Amber) | `scope_changed` 範圍變更、`material_pending` 缺料中、`delayed` 延遲中 |
| `color.status.success` | #10B981 (Emerald) | `completed` 已完工、`confirmed` 已確認、`archived` 已歸檔 |
| `color.status.danger` | #EF4444 (Red) | `rework_required` 返工中、`cancelled` 已取消、`disputed` 爭議中 |

#### 系統色系

| Token | 色值 | 用途 |
|-------|------|------|
| `color.success` | #10B981 | 成功、通過、正面指標 |
| `color.warning` | #F59E0B | 警告、SLA 即將逾時 |
| `color.error` | #EF4444 | 錯誤、逾時、負面指標 |
| `color.info` | #3B82F6 | 資訊提示、引導 |

#### 中性色系

| Token | 色值 | 用途 |
|-------|------|------|
| `color.bg.page` | #F8FAFC | 頁面底色（Slate 50） |
| `color.bg.surface` | #FFFFFF | 卡片/容器底色 |
| `color.bg.elevated` | #FFFFFF | Modal/Dropdown 底色 |
| `color.bg.sidebar` | #1E293B | Admin 側邊導航底色 |
| `color.text.primary` | #0F172A | 主要文字（Slate 900） |
| `color.text.secondary` | #64748B | 次要文字（Slate 500） |
| `color.text.disabled` | #94A3B8 | 停用文字（Slate 400） |
| `color.text.inverse` | #FFFFFF | 深色背景上的白字 |
| `color.border.default` | #E2E8F0 | 預設邊框（Slate 200） |
| `color.border.focus` | #2563EB | Focus 邊框（= Primary） |

#### Dark Mode（V2.0 預留）

| Token | Light | Dark | 用途 |
|-------|-------|------|------|
| `color.bg.page` | #F8FAFC | #0F172A | 頁面底色 |
| `color.bg.surface` | #FFFFFF | #1E293B | 卡片底色 |
| `color.text.primary` | #0F172A | #F1F5F9 | 主要文字 |
| `color.border.default` | #E2E8F0 | #334155 | 邊框 |

> Dark Mode 主要服務技師夜間作業場景。品牌色與語義色在兩種模式下保持不變。

---

### Spacing Scale

| Token | 值 | 用途 |
|-------|-----|------|
| `space.1` | 4px | 元素內微間距（Badge 內 padding） |
| `space.2` | 8px | 元素內標準間距（按鈕 icon-text gap） |
| `space.3` | 12px | 標籤與文字間距 |
| `space.4` | 16px | 元件間距（卡片內 padding） |
| `space.5` | 20px | 列表項間距 |
| `space.6` | 24px | 區塊間距（Section 間） |
| `space.8` | 32px | 大區塊間距 |
| `space.12` | 48px | Section 間距（Admin 頁面段落） |
| `space.16` | 64px | 頁面級間距 |

---

### Typography

| Token | 字級 | 行高 | 字重 | 用途 |
|-------|------|------|------|------|
| `text.display` | 32px | 1.2 | 700 | Dashboard 主標題 |
| `text.heading.xl` | 28px | 1.2 | 700 | H1 頁面標題 |
| `text.heading.lg` | 24px | 1.3 | 600 | H2 區塊標題 |
| `text.heading.md` | 20px | 1.4 | 600 | H3 卡片標題 |
| `text.heading.sm` | 16px | 1.4 | 600 | H4 小節標題 |
| `text.body.lg` | 16px | 1.6 | 400 | 大段落（工單描述） |
| `text.body.md` | 14px | 1.5 | 400 | 標準段落（列表內容） |
| `text.body.sm` | 12px | 1.5 | 400 | 小字說明（時間戳、標籤） |
| `text.caption` | 11px | 1.4 | 400 | 標註（狀態更新記錄） |
| `text.kpi` | 36px | 1.1 | 700 | KPI 大數字（Dashboard 卡片） |

- **英文字體**：Inter（SaaS 標準，高可讀性）
- **中文字體**：Noto Sans TC（Google Fonts，繁中最佳選擇）
- **等寬字體**：JetBrains Mono（工單編號、API 回應、日誌）
- **字體降級**：Inter, "Noto Sans TC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif

---

### Border Radius

| Token | 值 | 用途 |
|-------|-----|------|
| `radius.sm` | 4px | Tag, Badge, Status Chip |
| `radius.md` | 6px | 按鈕、輸入框、Select |
| `radius.lg` | 8px | 卡片、容器、KPI Card |
| `radius.xl` | 12px | Modal、大容器、地圖容器 |
| `radius.full` | 9999px | Avatar、Pill Badge、進度條 |

> 圓角偏小 (4-8px) 營造專業、精準的工業感，避免過度圓潤的消費級風格。

---

### Elevation (Shadow)

| Token | 值 | 用途 |
|-------|-----|------|
| `shadow.sm` | 0 1px 2px rgba(0,0,0,0.05) | KPI 卡片、列表行 hover |
| `shadow.md` | 0 4px 6px -1px rgba(0,0,0,0.1) | 懸浮卡片、Kanban 拖拉中 |
| `shadow.lg` | 0 10px 15px -3px rgba(0,0,0,0.1) | Modal、Dropdown、地圖 Popup |
| `shadow.kanban` | 0 8px 16px rgba(37,99,235,0.15) | Kanban 卡片拖拉中（帶品牌色） |

---

### RWD / Grid

#### Admin Panel（Desktop-First）

| 屬性 | 值 |
|------|-----|
| 最大寬度 | 1440px |
| 欄數 | 12 |
| 欄間距 | 24px |
| 側邊導航寬度 | 240px（展開）/ 64px（收合） |
| 左右 Padding | 24px (Desktop) / 16px (Tablet) |

| 斷點名稱 | 寬度 | 欄數 | 側邊導航 | 說明 |
|----------|------|------|---------|------|
| Desktop LG | > 1440px | 12 | 展開 240px | 完整 Dashboard + 右側面板 |
| Desktop | 1024px - 1440px | 12 | 展開 240px | 標準工作區 |
| Tablet | 768px - 1023px | 8 | 收合 64px | 簡化佈局 |
| Mobile | < 768px | 4 | 隱藏（漢堡選單） | 緊急存取用 |

#### Technician PWA（Mobile-First）

| 屬性 | 值 |
|------|-----|
| 最大寬度 | 480px（單欄） |
| 欄數 | 1 |
| 左右 Padding | 16px |
| 底部導航高度 | 56px + safe-area-inset |
| 最小觸控區域 | 44px × 44px |

| 斷點名稱 | 寬度 | 說明 |
|----------|------|------|
| Mobile | < 480px | 主要使用場景 |
| Tablet | 480px - 768px | 平板輔助（少數場景） |

---

## [UX PATTERN LAYER]

### 常用佈局 Pattern

#### Admin Panel

- **Dashboard（風格 A — KPI 卡片儀表板）**：
  左側深色導航 (240px, #1E293B) + 主內容區
  - 頂部：4 欄 KPI 卡片列（今日工單數 / 完工率 / 逾時數 / 在線技師）
  - 中部：左側 2/3 工單趨勢折線圖 + 右側 1/3 技師狀態餅圖
  - 底部：最近工單列表（可展開）

- **派工板（風格 B+C — Kanban + 地圖 toggle）**：
  上方工具列：篩選器 + 視圖切換 Toggle（看板 | 列表 | 地圖）
  - **Kanban 視圖**：垂直欄位（待指派 → 已派工 → 進行中 → 已完工），卡片可拖拉，每張卡片顯示：工單號 + 客戶 + 鎖型 + 技師 + SLA 倒數
  - **地圖視圖**：左側 1/3 工單列表 + 右側 2/3 Google Maps，技師藍點 + 客戶紅點 + 路線灰線
  - **列表視圖**：可排序表格，支援批次操作

- **工單詳情（風格 E — 嵌入鎖具狀態面板）**：
  左側 2/3 主內容（時間軸 + ProblemCard + 對話記錄）
  + 右側 1/3 側面板（鎖具設備狀態卡：型號 / 電量 / 連線 / 最近事件 + 技師資訊卡 + 操作按鈕）

- **列表頁（通用）**：上方篩選列（搜尋 + 狀態篩選 + 日期範圍）+ 中間表格/卡片 + 底部分頁

#### Technician PWA

- **案件池首頁（風格 C — 地圖優先）**：
  全屏地圖底圖 + 底部上滑面板（可接工單卡片列表）
  - 地圖顯示：技師當前位置（藍色脈衝點）+ 可接工單（紅色圖釘 + 距離標籤）
  - 點擊圖釘 → 地圖 Popup（工單摘要 + 「查看詳情」按鈕）

- **工單卡（風格 A — 大卡片 + 滑動操作）**：
  全寬卡片，大字顯示：客戶地址 + 鎖型 + 問題摘要 + 預估工時
  - 向右滑 → 接受工單（綠色）
  - 向左滑 → 拒絕工單（紅色）
  - 點擊 → 進入工單詳情

- **鎖具操作面板（風格 E — TTLock 風格）**：
  大圖示鎖具狀態卡（型號圖片 + 電量環形圖 + 連線狀態燈）
  + 操作記錄時間軸（最近 10 筆）
  + 大按鈕操作區（遠端開鎖 / 重置密碼 / 查看密碼記錄）

---

### 狀態設計規則

| 狀態 | 規則 |
|------|------|
| Loading | Skeleton screen 優先；長任務（派工匹配）顯示步驟進度條 + 預估秒數 |
| Empty | 引導圖示 + 說明文字 + CTA —「目前沒有待派工單，查看已完工記錄」 |
| Error | 紅色提示橫幅 + 具體錯誤 + 建議動作 + 重試按鈕 —「技師指派失敗：該區域無可用技師。建議：擴大搜尋半徑或手動指派」 |
| Disabled | 灰度 + cursor not-allowed + tooltip 說明原因 —「需先完成報價才能派工」 |
| SLA 即將逾時 | 卡片邊框變為 Amber + 脈衝動畫 + 倒數計時器 |
| SLA 已逾時 | 卡片邊框變為 Red + 紅色 Badge「逾時」+ 自動排序至最前 |
| AI 建議 | Indigo (#6366F1) Badge「AI」+ 虛線邊框 + tooltip「AI 建議：指派技師 A，因距離最近且評分最高」 |

---

### 元件狀態定義（核心元件）

| 元件 | Variants | States | Sizes |
|------|----------|--------|-------|
| Button | Primary(Blue) / CTA(Amber) / Secondary(Slate) / Ghost / Danger(Red) | Default / Hover / Active / Disabled / Loading | sm / md / lg |
| Input | Text / Password / Search / Textarea | Default / Focus(Blue ring) / Error(Red ring) / Disabled | sm / md / lg |
| Select | Single / Multi / Async Search | Default / Focus / Open / Disabled | sm / md / lg |
| Card | KPI Card / Work Order Card / Kanban Card / Device Status Card | Default / Hover(shadow-md) / Dragging(shadow-kanban) / Selected(Blue border) | — |
| StatusBadge | 6 語義色 × 13 工單狀態 | Default | sm / md |
| Modal | Default / Destructive / Confirmation | Open / Closing | sm / md / lg |
| Toast | Success / Warning / Error / Info | Entering / Visible / Exiting | — |
| Table | Default / Sortable / Selectable / Expandable | Default / Loading(Skeleton) / Empty | — |
| Map | Full-screen / Split-view / Embedded | Loading / Loaded / Error | — |
| Timeline | Vertical (工單歷程) / Horizontal (SLA 進度) | Default / Highlighted | — |
| BottomSheet | Technician PWA 專用上滑面板 | Collapsed / Half / Full | — |

---

## [INTERACTION & ACCESSIBILITY]

### 回饋樣式

- **Button/Link**：背景色加深 10% on Hover，按下時加深 15%
- **Card — KPI**：Hover 時 shadow-sm → shadow-md，無位移（避免 Dashboard 晃動）
- **Card — Kanban**：拖拉時 shadow-kanban（帶品牌藍暈），目標欄高亮 Primary Light
- **Card — Work Order (Technician)**：左滑/右滑時顯示底層操作色塊（綠/紅）
- **Sidebar Item**：Hover 時背景變為 Secondary Hover，Active 時左邊框 3px Primary
- **Map Pin**：Hover 放大 1.2x + tooltip；可接工單脈衝動畫（每 2s）
- **Status 轉換**：卡片狀態變更時 300ms ease 色彩漸變動畫

### 錯誤訊息格式

```
「[問題描述]。[建議動作]。」
```

- 表單驗證：「手機號碼格式不正確，請輸入 09 開頭的 10 位數字」
- API 錯誤：「工單更新失敗（伺服器回應 500），請稍後重試或聯繫管理員」
- 業務規則：「無法取消此工單，技師已開始作業。如需取消請聯繫管理員」

### 資料載入策略

- 優先 Skeleton Screen（Dashboard、列表頁）
- 地圖使用漸進式載入：先顯示底圖 → 逐步加載圖釘
- Kanban 使用 Optimistic UI：拖拉立即生效 → 背景 API 同步 → 失敗時回滾 + Toast

### 鍵盤與無障礙

- Tab 順序：側邊導航 → 頂部工具列 → 主內容區 → 右側面板
- Enter/Space 可觸發所有可互動元素
- Escape 關閉 Modal / Dropdown / BottomSheet
- Kanban 支援鍵盤：Arrow Keys 移動焦點，Space 拾起/放下卡片
- 色彩對比度：所有文字達 WCAG 2.1 AA 標準（4.5:1 正文 / 3:1 大字）
- 狀態不僅依賴顏色：所有狀態 Badge 同時包含文字標籤

---

## [TECH & CONSTRAINT LAYER]

### 技術棧

| 層級 | 選型 |
|------|------|
| Frontend Framework | Next.js 14 (App Router) + React 19 |
| UI Library | shadcn/ui + Radix UI Primitives |
| Styling | Tailwind CSS 3.4 |
| State | TanStack Query (Server State) + Zustand (Client State) + URL State |
| Forms | React Hook Form + Zod |
| Data Viz | Recharts（Dashboard 圖表） |
| Maps | @vis.gl/react-google-maps + Google Maps API |
| DnD | @dnd-kit/core（Kanban 拖拉） |
| Backend | FastAPI + Uvicorn / Pydantic v2 / JWT + RBAC |
| Database | PostgreSQL 16 + pgvector 0.7 / Redis 7 |
| Hosting | Docker Compose (Self-hosted) |

### 效能指標

| 指標 | Admin Panel | Technician PWA |
|------|-------------|----------------|
| LCP | < 2.5s | < 2.0s |
| FID | < 100ms | < 100ms |
| CLS | < 0.1 | < 0.1 |
| TTI | < 3.5s | < 2.5s |
| Lighthouse Score | > 80 | > 90 |

### 禁用項目

- 禁止 Inline styles（統一使用 Tailwind utility classes）
- 禁止自訂 CSS 動畫超過 500ms（操作回饋控制在 150-300ms）
- 禁止 Layout Shift（所有圖片/地圖必須預留空間）
- 禁止繞過 shadcn/ui 元件自造輪子（除非有明確理由）
- 禁止在 Technician PWA 使用 Desktop-only 的 hover 效果

---

## [DATA PATTERN LAYER]

| 類型 | 格式 | 範例 |
|------|------|------|
| 日期時間 | `YYYY-MM-DD HH:mm` | 2026-04-21 14:30 |
| 僅日期 | `YYYY-MM-DD` | 2026-04-21 |
| 相對時間 | `X 分鐘前` / `X 小時前` / 超過 24h 改絕對 | 15 分鐘前 |
| 數字 | 千分位逗號 | 1,234 |
| 百分比 | 一位小數 | 87.3% |
| 金額 | `NT$ + 千分位` | NT$ 3,500 |
| 電話 | `09XX-XXX-XXX` | 0912-345-678 |
| 工單編號 | `WO-YYYYMMDD-XXXX` | WO-20260421-0001 |
| 地址 | 完整地址，可點擊開啟地圖 | 台北市信義區松仁路 100 號 |
| 距離 | `X.X km`（< 1km 顯示公尺） | 2.3 km / 800 m |
| SLA 倒數 | `剩餘 HH:mm` / 逾時改紅色 `逾時 HH:mm` | 剩餘 01:23 / 逾時 00:15 |
| 電量 | 百分比 + 色彩（> 50% 綠 / 20-50% 黃 / < 20% 紅） | 78% |

---

## [EXAMPLE PATTERNS]

### Pattern 1: KPI Dashboard Card（風格 A）

- **核心區塊**：頂部標題（text.body.sm, Secondary）+ 中部大數字（text.kpi, Primary Text）+ 底部趨勢指標（向上箭頭 + Success 或 向下箭頭 + Error + 百分比）
- **交互設計**：Hover 時 shadow 加深，點擊跳轉至對應列表頁
- **尺寸**：最小寬度 200px，等分撐滿容器

```
┌─────────────────────┐
│  今日派工數           │  ← text.body.sm, color.text.secondary
│                     │
│     47              │  ← text.kpi, color.text.primary
│                     │
│  ↑ 12.5% vs 昨日    │  ← text.body.sm, color.success
└─────────────────────┘
```

### Pattern 2: Kanban Work Order Card（風格 B）

- **核心區塊**：頂部（工單號 + 狀態 Badge）+ 中部（客戶名 + 地址 + 鎖型）+ 底部（技師 Avatar + SLA 倒數）
- **交互設計**：可拖拉（shadow-kanban），點擊開啟工單詳情 Modal/Drawer
- **SLA 視覺**：正常=無標示，< 30min=Amber 邊框脈衝，逾時=Red 邊框+紅色 Badge

```
┌─────────────────────────┐
│ WO-0421-0023  [已派工]   │  ← heading.sm + StatusBadge(Violet)
│                         │
│ 王小明                   │  ← body.md, bold
│ 台北市信義區松仁路 100 號  │  ← body.sm, secondary
│ Yale YDM4109+            │  ← body.sm, secondary
│                         │
│ 👤 李師傅    ⏱ 剩餘 01:23│  ← Avatar + caption
└─────────────────────────┘
```

### Pattern 3: Device Status Panel（風格 E）

- **核心區塊**：鎖具圖示 + 型號名稱 + 三項即時指標（電量/連線/上次操作）+ 快捷操作按鈕
- **交互設計**：電量低於 20% 時環形圖變紅色 + 脈衝動畫；離線時連線圖示變灰 + 「離線」Badge

```
┌─────────────────────────┐
│  🔒 Yale YDM4109+       │  ← heading.md
│                         │
│  ┌──────┐ ┌──────┐ ┌──────┐
│  │ 🔋   │ │ 📶   │ │ 🕐   │
│  │ 78%  │ │ 在線  │ │ 2 hr │
│  │ 電量  │ │ 連線  │ │ 前操作│
│  └──────┘ └──────┘ └──────┘
│                         │
│  [遠端開鎖]  [重置密碼]   │  ← Button.CTA(Amber)
└─────────────────────────┘
```

### Pattern 4: Technician Map View（風格 C）

- **核心區塊**：全屏 Google Maps + 底部 BottomSheet（可上滑展開工單列表）
- **交互設計**：
  - 技師位置：藍色脈衝點（每 2s）
  - 可接工單：紅色圖釘 + 距離標籤（2.3 km）
  - 點擊圖釘 → Popup（工單摘要卡）→ 「查看詳情」按鈕
  - 底部面板三段式：Collapsed (96px 顯示數量) → Half (50%) → Full (90%)

---

## [INFORMATION ARCHITECTURE]

> 對應 `E5x--frontend-information-arch.md` 的完整頁面矩陣。

### Admin Panel 導航結構

```
Admin Panel (/admin)
├── 🏠 儀表板 (/dashboard)                    ← V1.0, Level 1
├── 💬 對話管理
│   ├── 對話列表 (/conversations)              ← V1.0, Level 2
│   └── 對話詳情 (/conversations/[id])         ← V1.0, Level 3
├── 🎯 問題卡
│   ├── 問題卡列表 (/problem-cards)            ← V1.0, Level 2
│   └── 問題卡詳情 (/problem-cards/[id])       ← V1.0, Level 3
├── 📚 知識庫
│   ├── 案例庫 (/knowledge-base/cases)         ← V1.0, Level 2
│   ├── 手冊管理 (/knowledge-base/manuals)     ← V1.0, Level 2
│   └── SOP 審核 (/knowledge-base/sop-drafts)  ← V1.0, Level 2
├── 📋 工單管理                                 ← V2.0 Section
│   ├── 工單列表 (/work-orders)                ← V2.0, Level 2
│   ├── 派工板 (/work-orders/dispatch)         ← V2.0, Level 2
│   └── 工單詳情 (/work-orders/[id])           ← V2.0, Level 3
├── 👷 技師管理                                 ← V2.0 Section
│   ├── 技師列表 (/technicians)                ← V2.0, Level 2
│   └── 技師詳情 (/technicians/[id])           ← V2.0, Level 3
├── 💰 帳務管理 (/accounting)                   ← V2.0, Level 2
├── 🔧 進階管理                                 ← V2.0 Section
│   ├── 退款審批 (/admin/refunds)
│   ├── 庫存管理 (/admin/inventory)
│   ├── 保固索賠 (/admin/warranty-claims)
│   ├── 爭議仲裁 (/admin/disputes)
│   ├── 稽核日誌 (/admin/audit-events)
│   └── 角色權限 (/admin/roles)
└── ⚙️ 系統設定 (/settings)                    ← V1.0, Level 2
```

### Technician PWA 導航結構

```
Technician App
├── 🗺️ 案件池 (/pool)          ← 底部導航 Tab 1, 地圖+工單列表
├── 📋 我的工單 (/my-orders)    ← 底部導航 Tab 2, 進行中工單列表
├── 💰 帳戶中心 (/account)      ← 底部導航 Tab 3, 收入統計
└── 工單詳情 (/my-orders/[id])  ← 從列表點入, 含完工回報+鎖具面板
```

---

**版本資訊**：

- 當前版本：v1.0
- 最後更新：2026-04-21
- 此文件為「電子鎖智能客服與派工平台」全站設計靈魂，任何 Page-Level Prompt 均以此為基石。
- 相關文件：
  - `SYSTEM_DOCUMENT_SPEC.md`（四層文件模板）
  - `BASE_DESIGN_SYSTEM.md`（通用模板）
  - `01_sunny_brand_system.md`（品牌範例參考）
  - `references/ui_style_benchmark_report.md`（風格參考報告）
  - `docs/01-define/E3x--module-breakdown.md`（模組分解）
  - `docs/02-design/E5x--frontend-information-arch.md`（前端資訊架構）
  - `docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md`（工單互動流程）
