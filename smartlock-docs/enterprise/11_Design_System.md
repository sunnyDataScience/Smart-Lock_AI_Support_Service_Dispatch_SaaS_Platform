---
title: "11 Design System — 設計系統（Token / 元件庫 / 工程對接）"
version: 1.0
status: active
owner: Design System Lead（前端 + UI/UX 共同維護）
last-updated: 2026-07-07
upstream:
  - smartlock-docs/web/P1/05_architecture_and_design.md
  - smartlock-docs/technician-platform/P1/05_architecture_and_design.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P005_per-brand授權部署_大單體內部容器.md
---

# 11 Design System — 設計系統

> 全站的物理定律。品牌營運後台（Admin Panel，dispatch portal）、師傅工作台（Technician PWA，technician-platform 獨立師傅 web）、客戶 token 公開頁三端共享同一套設計語言。本文件為 Design Token 與元件庫的 Single Source of Truth；頁面如何組裝元件見 [10_UI_Spec.md](./10_UI_Spec.md)，無障礙合規細則交叉 [05_NFR.md](./05_NFR.md)。

## 1. 設計原則

1. **Token 為單一真相**：所有色彩、字體、間距、圓角、陰影、動效值一律引用 token，不寫 magic number。
2. **雙 Grid、單語言**：Admin（desktop-first，1440 container）與 Tech PWA（mobile-first，480 container）為兩套版面系統，但共用同一套色彩／字體／元件規格。師傅 web 為 technician-platform 的獨立部署（跨品牌共用，不進品牌 bundle），仍遵循本設計系統。
3. **狀態三重指示**：任何狀態（工單狀態、SLA、連線）必須同時以「色彩 + 圖示 + 文字」表達，不得僅靠顏色。
4. **light 為 V1 現行模式**；dark / high-contrast / 白標品牌皮膚為 🔜 規劃中（token 已預留，見 §2.11）。

## 2. Foundations（基礎 Token）

### 2.1 Grid & Layout

#### Admin Panel（desktop-first）

| 屬性 | 值 |
|---|---|
| `layout.admin.container.max-width` | 1440px |
| `layout.admin.container.padding` | 24px |
| Sidebar 展開 / 收合 | 240px / 64px（`space.sidebar` / `space.sidebar.collapsed`）|
| Page Header 高度 | 64px（sticky，`z.sticky`）|

| 斷點 | 欄數 | Gutter | Sidebar |
|---|---|---|---|
| Mobile（< 768px，`breakpoint.admin.md`）| 4 | 16px | 隱藏（hamburger）|
| Tablet（768–1023px）| 8 | 20px | 收合 64px |
| Desktop（1024–1439px，`breakpoint.admin.lg`）| 12 | 24px | 展開 240px |
| Wide（≥ 1440px，`breakpoint.admin.xl`）| 12 | 24px | 展開 240px，container 鎖 1440px |

Layout primitives：Admin Shell `grid-cols-[240px_1fr]`；Content Area `max-w-[1200px] mx-auto px-6`；Dashboard Grid `grid-cols-4 gap-6`（tablet 2 欄 / mobile 1 欄）；Kanban Board `flex overflow-x-auto gap-4` 每欄 320px；Split Detail `grid-cols-[1fr_400px]`（mobile 堆疊）。

#### Technician PWA（mobile-first）

| 屬性 | 值 |
|---|---|
| `layout.tech.container.max-width` | 480px（`breakpoint.tech.sm` 唯一斷點）|
| `layout.tech.container.padding` | 16px |
| Bottom Nav 高度 | 56px + `env(safe-area-inset-bottom)`（`space.bottomnav.total`）|
| Top Bar 高度 | 56px（`space.topbar`）|
| 最小觸控目標 | 44×44px（`space.touch-target`，WCAG 2.5.5）|

Layout primitives：PWA Shell `min-h-screen flex flex-col pb-bottomnav-safe`；Card Stack `flex flex-col gap-3 px-4`；Map Full `h-[calc(100vh-56px-56px-env(safe-area-inset-bottom))]`；Bottom Sheet `fixed bottom-0 inset-x-0 rounded-t-2xl z-bottomsheet`。

#### 共通 RWD 規則

- Admin：Sidebar 三段（展開 / 收合 / hamburger）；Table 於 tablet 隱藏次要欄、mobile 轉卡片列表；Form 於 mobile 單欄堆疊；Modal 於 mobile 轉 bottom sheet；Kanban 於 mobile 改列表視圖。
- Tech PWA：永遠單欄；地圖全螢幕 + 底部 Sheet；手勢（下拉重新整理、左右滑動切換工單狀態）。
- 圖片：Admin 用 `next/image` srcset；工單照片 max 1920px、縮圖 200px；PWA 壓縮優先（離線快取考量）。

### 2.2 Color System

#### Brand Colors

| Token | Light 值 | 用途 | 對比（vs #FFFFFF）|
|---|---|---|---|
| `color.brand.primary` | #2563EB | Trust Blue — 主品牌色、Primary CTA、Active、Focus ring | 4.6:1 AA |
| `color.brand.primary.hover` / `.active` / `.light` | #1D4ED8 / #1E40AF / #DBEAFE | hover 加深一階 / pressed / 淺色底（tag、selected row）| 5.9 / 7.1 / — |
| `color.brand.accent` | #F59E0B | Amber CTA — 派工按鈕、緊急操作 | 2.1:1（**必須配深色文字 #0F172A**）|
| `color.brand.accent.hover` / `.active` / `.light` | #D97706 / #B45309 / #FEF3C7 | — | — |
| `color.brand.secondary` | #1E293B | Slate — Sidebar 背景、深色區域 | 14.5:1 AAA |
| `color.brand.secondary.hover` / `.active` | #334155 / #475569 | — | — |

#### 工單狀態 6 色系（每系含 main / bg / text 三件套）

| 色系 | Token | main | bg | text | 語意 |
|---|---|---|---|---|---|
| Pending | `color.status.pending` | #6366F1 | #EEF2FF | #3730A3 | 新建、待指派 |
| Assigned | `color.status.assigned` | #8B5CF6 | #F5F3FF | #5B21B6 | 已指派、待出發 |
| Active | `color.status.active` | #3B82F6 | #EFF6FF | #1E40AF | 前往中、施工中 |
| Warning | `color.status.warning` | #F59E0B | #FEF3C7 | #92400E | 範圍變更、待料、延遲 |
| Success | `color.status.success` | #10B981 | #ECFDF5 | #065F46 | 完工、確認、歸檔 |
| Danger | `color.status.danger` | #EF4444 | #FEF2F2 | #991B1B | 返工、取消、爭議 |

#### 13 態工單狀態 → 6 色系對應

工單 `status` 值域由 Flow DSL 宣告（見 [../00_platform/P1/07_workorder_platform_design.md](../00_platform/P1/07_workorder_platform_design.md) §5，非寫死 enum）；UI 層以下列 13 態 → 6 色系映射呈現：

| status | 中文標籤 | 色系 |
|---|---|---|
| `created` | 已建立 | Pending |
| `assigned` | 已指派 | Assigned |
| `accepted` | 已接受 | Active |
| `in_progress` | 進行中 | Active |
| `scope_changed` | 範圍變更 | Warning |
| `material_pending` | 待料中 | Warning |
| `delayed` | 延遲 | Warning |
| `completed` | 已完工 | Success |
| `confirmed` | 已確認 | Success |
| `archived` | 已歸檔 | Success |
| `rework_required` | 需返工 | Danger |
| `cancelled` | 已取消 | Danger |
| `disputed` | 爭議中 | Danger |

#### 通用語意色 / Surface / Text / Border（Light 值）

| 類別 | Token → 值 |
|---|---|
| 語意 | `color.success` #10B981 · `color.warning` #F59E0B · `color.error` #EF4444 · `color.info` #3B82F6（各含 `.bg` / `.text` 三件套）|
| Surface | `bg.page` #F8FAFC · `bg.surface` #FFFFFF · `bg.elevated` #FFFFFF · `bg.muted` #F1F5F9 · `bg.sidebar` #1E293B · `bg.overlay` rgba(15,23,42,0.6) · `bg.selected` #DBEAFE · `bg.hover` #F1F5F9 |
| Text | `text.primary` #0F172A · `text.secondary` #64748B · `text.disabled` #94A3B8 · `text.inverse` #FFFFFF · `text.link` #2563EB · `text.on-primary` #FFFFFF · `text.on-accent` #0F172A · `text.sidebar` #CBD5E1 · `text.sidebar.active` #FFFFFF |
| Border | `border.default` #E2E8F0 · `border.hover` #CBD5E1 · `border.focus` #2563EB · `border.error` #EF4444 · `border.success` #10B981 |
| SLA 交通燈 | `border.sla.green` #10B981（剩餘 > 50%）· `border.sla.amber` #F59E0B（20–50%）· `border.sla.red` #EF4444（< 20%）；逾時（black 級）用 `#1E293B` 深底白字 |

#### 對比度規則（WCAG 2.1 AA）

- 一般文字（< 18px）≥ 4.5:1：`text.primary` vs surface = 15.4:1 ✅；`text.secondary` = 5.0:1 ✅；`text.disabled` = 2.9:1（僅限 disabled，豁免）。
- 大文字 ≥ 3:1：`brand.primary` vs 白 = 4.6:1 ✅；`brand.accent` vs 白 = 2.1:1 ❌ → **Amber 按鈕上一律用深色文字 #0F172A**。
- UI 元件邊框 ≥ 3:1：`border.default` = 1.5:1 ⚠️ → 以 shadow 補強視覺區分。
- Status Badge text vs bg：pending 8.2 / assigned 7.6 / active 8.9 / warning 6.3 / success 7.1 / danger 7.8，全數 ✅。
- 驗證工具：Figma Contrast Checker、webaim.org contrastchecker、CI axe-core。

### 2.3 Typography

| 用途 | 字體 | Fallback |
|---|---|---|
| 英文 | Inter（variable，`font-display: swap`）| -apple-system, Segoe UI, sans-serif |
| 中文 | Noto Sans TC（400/600/700）| PingFang TC, Microsoft JhengHei |
| 代碼／工單編號 | JetBrains Mono | Fira Code, Consolas |

| Token | 字級 / 行高 / 字重 | 用途 |
|---|---|---|
| `text.display` | 32px / 1.2 / 700 | Dashboard 大標題 |
| `text.heading.h1`–`h4` | 28 / 24 / 20 / 16px | 頁面主標 → 小節標 |
| `text.body.lg` / `.md` / `.sm` | 16 / 14 / 12px（400）| 段落 / 標準內文（表格）/ 輔助 |
| `text.caption` | 11px / 1.4 | 時間戳、Badge 內文字 |
| `text.overline` | 12px / 600 / 0.05em | 上標分類（大寫英文）|
| `text.kpi` | 36px / 1.1 / 700 | KPI 數字（`tabular-nums` + JetBrains Mono）|

中英混排：行高 1.5–1.6；全形中文標點；數字與英文間半形空格（例：共 3 個工單）；金額千分位（$12,500）；電話 0912-345-678；**工單編號一律 monospace，格式 `WO-YYYYMMDD-NNN`**。RWD 字級（僅 Admin）：display 32→28→24、h1 28→24→22、kpi 36→32→28（Desktop→Tablet→Mobile）；Tech PWA 不做字級 RWD。

### 2.4 Spacing（4px 基數）

Scale：`space.0.5`=2 · `1`=4 · `1.5`=6 · `2`=8 · `3`=12 · `4`=16 · `5`=20 · `6`=24 · `8`=32 · `10`=40 · `12`=48 · `16`=64 · `20`=80 · `24`=96px。

平台專用：`space.sidebar` 240 / `space.sidebar.collapsed` 64 / `space.page-header` 64 / `space.bottomnav` 56 / `space.safe-area` env(safe-area-inset-bottom) / `space.topbar` 56 / `space.touch-target` 44 / `space.kanban.column` 320 / `space.kanban.gap` 16px。

規則：鄰近原則（相關元素間距 < 不相關）；同層級一致；元素內部 4–12px、元件間 16–24px、Section 間 32–48px、頁面級 64–96px；Padding 用於容器內、Margin 用於容器外；Tech PWA 可點擊元素 ≥ 44×44px（不足以 padding 補）。

### 2.5 Border & Radius

| Token | 值 | 用途 |
|---|---|---|
| `border.width.default` / `.thick` / `.status` | 1px / 2px / 3px | 標準邊框 / Focus ring、Active Tab / **Kanban 卡片左側 status stripe** |
| `radius.sm` / `.md` / `.lg` / `.xl` / `.2xl` / `.full` | 4 / 6 / 8 / 12 / 16 / 9999px | Tag、Badge / 按鈕、輸入框 / 卡片 / Modal / Bottom Sheet 頂部 / 圓形、Pill |

規則：外層圓角 > 內層圓角（內層 ≈ 外層 − padding）；Admin 卡片主用 `radius.lg`，Tech PWA 主用 `radius.xl`（觸控友善）；Kanban 卡片拖曳中 radius 不變、靠 shadow 表示浮起。

### 2.6 Elevation & Shadow

| Token | 值 | 用途 |
|---|---|---|
| `shadow.xs`–`shadow.2xl` | `0 1px 2px rgba(0,0,0,0.05)` … `0 25px 50px rgba(0,0,0,0.25)` | Input → 卡片（sm）→ hover（md）→ Dropdown（lg）→ Modal（xl）→ Toast（2xl）|
| `shadow.kanban` | `0 8px 16px rgba(37,99,235,0.15)` | Kanban 卡片拖曳（帶品牌色暈染，僅限拖曳使用）|
| `shadow.bottomsheet` | `0 -4px 16px rgba(0,0,0,0.12)` | Bottom Sheet 向上投影 |
| `shadow.sidebar` / `shadow.map-control` | `4px 0 8px rgba(0,0,0,0.08)` / `0 2px 6px rgba(0,0,0,0.2)` | Sidebar 收合 hover / 地圖浮動控制 |
| `shadow.focus-ring` | `0 0 0 3px rgba(37,99,235,0.3)` | Focus 外發光（搭配 `border.focus`）|

### 2.7 Z-Index

Base 0 → Elevated 5 → Sticky 10（header / sidebar / table header）→ **Kanban Drag 15** → Dropdown 20 → **Bottom Sheet 25** → Overlay 30 → Map Controls 35 → Modal 40 → Toast 50 → Tooltip 60 → Command 70。規則：不自創層級；Bottom Sheet 在 Map Controls 之下（避免遮擋地圖操作）；新增層級須經 Design System Lead 審核。

### 2.8 Iconography

- 圖標庫：**lucide-react**，Outline 風格、線寬 1.5px、`currentColor` 繼承；尺寸 16（行內）/ 20（按鈕、導航）/ 24（Sidebar、空狀態）/ 32px（Dashboard 大圖示）。
- 平台自定義 icon：`icon.lock.locked/unlocked/error/offline`（Lucide Lock 系 + overlay）、`icon.battery.full/medium/low/charging`（< 25% 紅色）、`icon.connectivity.wifi/bluetooth/offline/z-wave`（Z-Wave 自繪）、`icon.technician.available/busy/offline/en-route`（User 系 + 8px 狀態圓點，右下角偏移 −2px、2px 白描邊；色：#10B981 / #F59E0B / #94A3B8 / #3B82F6）。
- 規則：純 icon 按鈕必有 `aria-label`；裝飾性 icon `aria-hidden="true"`；狀態 icon 必配文字。

### 2.9 Motion & Animation

| Token | 值 | 用途 |
|---|---|---|
| `motion.duration.instant/fast/normal/slow/slower/pulse` | 100 / 150 / 200 / 300 / 500 / 2000ms | hover / checkbox / 按鈕、Tab / Modal、Sidebar、Bottom Sheet / 頁面切換 / SLA 脈搏週期 |
| `motion.ease.default/in/out/in-out` | `cubic-bezier(0.4,0,0.2,1)` 等 | 通用 / 離場 / 進場 / 位移 |
| `motion.ease.spring` | `cubic-bezier(0.34,1.56,0.64,1)` | Kanban 放下、通知 badge 彈跳 |

平台專用動效（CSS 為已驗證成品，工程直接取用）：

```css
/* SLA 三階段 + 逾時脈搏 */
.sla-green { border-left: 3px solid var(--color-border-sla-green); }
.sla-amber { border-left: 3px solid var(--color-border-sla-amber); }
.sla-red   { border-left: 3px solid var(--color-border-sla-red); }
@keyframes sla-pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
  50%     { box-shadow: 0 0 0 4px rgba(239,68,68,0); }
}
.sla-red.overdue { animation: sla-pulse 2s ease-in-out infinite; border-width: 2px; }

/* Kanban 拖曳浮起 / 放置區高亮 */
.kanban-card-dragging { transform: rotate(2deg) scale(1.02); box-shadow: var(--shadow-kanban);
  opacity: .95; z-index: var(--z-kanban-drag); }
.kanban-column-drop-target { background: var(--color-brand-primary-light);
  border: 2px dashed var(--color-brand-primary); }

/* Bottom Sheet 三段 snap */
@keyframes bottomsheet-slide-up { from { transform: translateY(100%); } to { transform: translateY(0); } }
.bottomsheet-peek { transform: translateY(calc(100% - 120px)); }
.bottomsheet-half { transform: translateY(50%); }
.bottomsheet-full { transform: translateY(0); }

/* 地圖進行中工單 pin 脈動 */
@keyframes map-pin-pulse { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.3); opacity: 0; } }
.map-pin-active::after { background: var(--color-status-active); animation: map-pin-pulse 2s ease-in-out infinite; }

/* Sidebar 展開/收合 */
.sidebar-expanded  { width: var(--space-sidebar); transition: width 300ms cubic-bezier(0.4,0,0.2,1); }
.sidebar-collapsed { width: var(--space-sidebar-collapsed); transition: width 300ms cubic-bezier(0.4,0,0.2,1); }
```

動效規則：必須有功能目的（不做純裝飾）；可被使用者中斷；遵守 `prefers-reduced-motion`（SLA pulse → 靜態紅框、slide → fade）；只 animate transform / opacity（Sidebar 寬度為例外，加 `will-change: width`）；Tech PWA 以 60fps 為底線；WebSocket 狀態同步——狀態變更邊框變色 200ms、新工單 slide-down + fade-in 300ms、被他人拖走 fade-out 200ms + placeholder。

### 2.10 Token 命名規範

結構 `{category}.{property}.{variant}.{state}`；小寫 + 點分隔；語意化而非描述值（✅ `color.status.pending`、❌ `color.indigo.500`）；佈局類加平台前綴（`layout.admin.*` / `breakpoint.tech.*`）；狀態色一定有 main / bg / text 三件套；避免非公認縮寫。類別 prefix：`color.* / space.* / text.* / radius.* / shadow.* / border.* / motion.* / layout.* / breakpoint.* / z.* / icon.*`。

### 2.11 Token Mode 管理

| Mode | 說明 | 狀態 |
|---|---|---|
| `light` | 淺色模式（預設）| **V1 現行** |
| `dark` | 深色模式（技師夜間作業，`prefers-color-scheme` / 手動 toggle）| 🔜 規劃中（token 對照表已預留，如 `bg.page` #F8FAFC→#0F172A、`brand.primary` #2563EB→#3B82F6）|
| `high-contrast` | 高對比（`prefers-contrast`）| 🔜 規劃中 |
| `brand-yale` / `brand-gateman` / `brand-samsung` | 白標品牌皮膚（per-brand 授權部署下的租戶級覆蓋，僅覆蓋 `color.brand.*` 五個 token，其餘繼承；例 Yale primary #003DA5 + accent #FFD700）| 🔜 規劃中（歸屬對齊 [../00_platform/P2/04_adr/ADR-P005_per-brand授權部署_大單體內部容器.md](../00_platform/P2/04_adr/ADR-P005_per-brand授權部署_大單體內部容器.md)）|

## 3. 元件庫（Atomic 分層）

分層：**Atoms**（Button、Input、Select、Badge、Avatar、Checkbox/Radio/Switch、Tag、Divider + 平台 StatusBadge、SLACountdown、AIRecommendationBadge、SkillBadge）→ **Molecules**（SearchBar、FormField、KPICard、WorkOrderCard、DeviceStatusCard、SignaturePad、PhotoGallery）→ **Organisms**（DataTable、KanbanBoard、MapView、BottomSheet、Modal/Dialog、Toast、Tabs、WorkTimeline、CompletionReportForm、DeviceStatusPanel）。每元件採規格卡：Purpose / Anatomy / Props / States / Interaction / Accessibility / Do & Don't。以下為關鍵元件規格卡（完整 props 明細以本節為準）。

### 3.1 Button

- **Variants**：primary（#2563EB / 白字 / hover #1D4ED8）、**cta**（#F59E0B Amber，派工／接受工單等立即行動；文字依對比規則用深色）、secondary（#1E293B）、ghost（透明 / hover #F1F5F9）、danger（#EF4444）、link。
- **尺寸**：sm 32px / md 36px / lg 44px（**Tech PWA 一律 lg**，觸控 ≥ 44px）；radius.md；min-width 64px。
- **States**：default / hover（加深一階）/ active（再加深 + `scale(0.98)`）/ focus（`ring-2 ring-offset-2` 藍）/ disabled（`opacity-50`）/ loading（spinner 取代 leading icon + `pointer-events-none`，防重複提交）。
- **A11y**：`Enter`/`Space` 觸發；icon-only 必有 `aria-label`；loading 時 `aria-busy`。
- **Do/Don't**：一頁最多一個 primary + 一個 cta；文案動詞開頭（「派工」「接受工單」，禁「確定」）；破壞性操作用 danger + 確認 Dialog。

### 3.2 Input / Select

- Input：type text/password/email/number/search/tel/textarea；尺寸同 Button；label 永遠可見（禁只放 placeholder）；error 顯示於下方 inline（`role="alert"`）+ 紅框，不得只靠 toast；search 300ms debounce；必填 `*` 標示；電話用 `type="tel"`。
- Select：single / multi / combobox；品牌型號用分組選單（Yale / Gateman / Samsung 分組）；技師選擇用 combobox 可搜尋；選項 > 10 啟用搜尋；多選顯示「已選 N 項」；dropdown `shadow.lg` + max-height 240px；完整鍵盤操作（Arrow / Enter / Esc）+ `role="combobox"/"listbox"/"option"`。

### 3.3 Card 家族（4 平台變體）

- **KPICard**：標題 14px Slate-500 + 數值 36px/700 + 趨勢箭頭（▲ green / ▼ red / ─ slate）；padding 24px。
- **WorkOrderCard**：工單號 + StatusBadge + 客戶/地址（truncate）+ 鎖具型號/問題摘要 + SLACountdown + 技師 + SLA 進度條；**左邊框 4px 色帶依 SLA 交通燈**；mobile 表格降級的載體。
- **KanbanCard**：緊湊（p-3）；工單號 mono 14px/600 + 客戶名（≤ 8 字）+ 鎖具型號 + StatusBadge + SLA；拖曳中 `shadow.kanban` + `scale(1.02) rotate(2deg)`；placeholder 虛線框。
- **DeviceStatusCard**：鎖具型號 + 電量/連線/最後操作三指標 + 操作按鈕（遠端開鎖為高危操作，必經確認 Dialog）。

### 3.4 StatusBadge（平台 Atom）

13 態 → 6 色群（見 §2.2 對應表），pill 形（radius.full），**8px 色點 + 中文標籤**（禁只顯示色點或英文 status code）；尺寸 sm 22px / md 28px；可附 SLA 倒計時（`│ 02:30`）；逾時 dot 閃爍 + 文字「逾時」；`role="status"` + `aria-label="工單狀態：進行中"`。

### 3.5 SLACountdown（平台 Atom）

交通燈四級：**Green**（> 50% 剩餘，靜態）→ **Amber**（20–50%，邊框脈動 2s）→ **Red**（< 20%，pulse 1.5s）→ **Black**（已逾時，#1E293B 深底白字 + 閃爍 1s）；另有 Paused（工單暫停如待料中，灰底 + 暫停圖示，**不繼續倒數**）。文字「剩餘 02:30」/「逾時 00:45」；< 5 分鐘每秒更新；級別轉換色彩漸變 300ms；逾時觸發 `onExpire`（Tech PWA 加震動）；`role="timer"` + `aria-live="polite"`。

### 3.6 AIRecommendationBadge / SkillBadge

- AIRecommendationBadge：Indigo 系（#EEF2FF 底 / #4338CA 字 + Sparkles icon）；型別 recommendation（派工候選 #1）/ suggestion（診斷、SOP 草案）/ auto；hover tooltip 顯示推薦理由；**附近永遠有人工覆寫入口**；confidence 有意義才顯示。
- SkillBadge：品牌 + 1–5 星熟練度（★ #F59E0B）+ 認證 ✓（green）；到期指示（30–90 天 amber「即將到期」/ < 30 天 red / 已過期 red + 刪除線）。

### 3.7 DataTable（工單列表 Organism）

工單列表專用 10 欄：☐ 批次選取 40px｜工單號 140px（mono、link）｜客戶 160px（avatar+text）｜鎖具型號 140px｜問題分類 120px（tag）｜狀態 120px（StatusBadge）｜SLA 100px（SLACountdown）｜指派技師 140px（未指派顯示「指派」按鈕）｜建立時間 120px（MM/DD HH:mm）｜操作 80px（⋮ 選單：查看/編輯/指派/取消）。

- Row 高 48px、hover `bg-slate-50`、selected `bg-blue-50`；header sticky、`bg-slate-50` 大寫 12px；數字右對齊。
- **5 態**：Loading（5 行 skeleton）/ Empty（插圖 +「目前沒有工單」+ [建立工單] CTA）/ No Result（「找不到符合條件的工單」+ [清除篩選]）/ Error（「載入失敗」+ [重試]）/ Bulk Selected（頂部浮出「已選 N 項 — [批次指派] [匯出]」）。
- 互動：header 排序 asc→desc→none（`aria-sort`）；13 狀態多選篩選；搜尋 300ms debounce；**篩選條件同步 URL query string**；分頁 10/25/50/100；mobile 轉 WorkOrderCard List；大列表用 `@tanstack/react-virtual` 虛擬化。

### 3.8 KanbanBoard（派工 Organism）

5 欄（欄寬固定 280–320px，水平捲動，欄內垂直捲動 `max-h-[calc(100vh-200px)]`）：

| 欄 | 對應狀態 | Header | Icon |
|---|---|---|---|
| 待指派 | `created` | `border-t-indigo-500` | Inbox |
| 已派工 | `assigned` `accepted` | `border-t-violet-500` | UserCheck |
| 進行中 | `in_progress` `scope_changed` `material_pending` | `border-t-blue-500` | Wrench |
| 已完工 | `completed` `confirmed` | `border-t-emerald-500` | CheckCircle |
| 異常 | `delayed` `rework_required` `disputed` `cancelled` | `border-t-red-500` | AlertTriangle |

拖曳有效轉換表：待指派→已派工（**觸發指派 Dialog**）；已派工→進行中 / 退回待指派；進行中→已完工 / 異常；已完工→進行中（返工）；異常→進行中 / 待指派。無效拖曳回彈 + shake；拖曳啟動 Desktop 按住 150ms / Mobile 長按 300ms。

States：Dragging（`shadow.kanban` + 原位 placeholder）/ Drag Over valid（`bg-blue-50` + 藍線）/ invalid（`bg-red-50` + 🚫）/ **Optimistic Update**（放下即移動半透明，API 失敗回彈 + error toast）/ WebSocket Update（外部變更卡片漸入 + 2s 高亮）/ Empty Column（虛線框「目前無工單」）。鍵盤拖曳替代：`Space` 拾起 → `Arrow` 移動 → `Space` 放下 → `Esc` 取消，並以 aria-live 朗讀。拖曳引擎函式庫選型 [待確認]（行為規格如上為準）。

### 3.9 MapView（Organism）

圖釘：未指派紅 #EF4444 / 已指派紫 #8B5CF6 / 進行中藍 #3B82F6 / 完工綠 #10B981 / 異常橘三角（閃爍）/ **技師** 藍 + 脈動光環（WebSocket 即時位置，平滑移動）。> 50 pin 啟用 clustering（色彩取最嚴重級）；pin 點擊彈 280px popup（迷你 WorkOrderCard + 查看/指派/導航按鈕）；**列表 ↔ 地圖雙向同步**（點列表 → zoom + highlight；點 pin → 列表捲動高亮）；圖例常駐。地圖函式庫選型 [待確認]。

### 3.10 BottomSheet（Tech PWA Organism）

三段式：Collapsed 96px（拉桿 + 摘要「3 筆待處理工單」）→ Half 50vh → Full 90vh（+ `bg-black/20` overlay + focus trap）；拉桿 40×4px `bg-slate-300`；spring 物理動畫（stiffness 300 / damping 30）；safe-area padding；body 內容捲動到頂才觸發 sheet 下滑收合。

### 3.11 Modal / Toast / Tabs / WorkTimeline / 表單類

- **Modal**：尺寸 sm 400 / md 520 / lg 640 / xl 800px；radius.xl；focus trap；mobile 轉 bottom sheet（90vh）。平台場景：派工確認（sm，顯示技師 + AI 推薦理由 + SLA）、取消工單（destructive，必選原因、`preventOverlayClose`）、範圍變更（form md + 費用試算）、SLA 逾時警告（紅標題列）、排程衝突（lg 甘特圖）。
- **Toast**：success 5s / warning 8s / **error 不自動消失 + 重試入口** / info 5s / **dispatch**（Indigo + Truck icon，新工單推播 8s，Tech PWA 可震動）；右上（Admin）/ 頂部居中（PWA）；堆疊最多 3；hover 暫停倒數；`aria-live` polite/assertive。文案要具體（「已成功指派 WO-20260421-001 給王技師」）。
- **Tabs**：underline（工單詳情 5 Tab：基本資訊/服務紀錄/零件/照片/時間軸；技師 Profile）/ pill（Dashboard）/ outlined（設定頁）；tab 對應 URL hash；panel lazy load；2–6 個為宜。
- **WorkTimeline**：垂直時間軸；事件型別 status_change（StatusBadge）/ note / photo（縮圖 → lightbox）/ system / sla_warning；預設最新 10 筆 +「查看更多」；WebSocket 新事件頂部 slide-in + 2s 高亮；相對時間 + tooltip 完整時間。
- **CompletionReportForm**（Tech PWA）：5 區塊——服務檢核清單 / 零件明細（combobox 從目錄帶入單價、即時小計）/ 照片（**至少 3 張**、分類施工前/後/零件）/ 功能測試開關（指紋/密碼/卡片/遠端/自動上鎖 Pass-Fail）/ 電子簽名（最小筆畫偵測）；底部 Summary Bar（總計 + 儲存草稿 + 提交 cta）；**草稿每 30s 自動存 IndexedDB；離線可填寫、上線自動同步**。
- **SignaturePad / PhotoGallery / DeviceStatusPanel / Avatar**：規格重點——簽名 canvas 最少 5 筆觸、輸出 base64、提供清除；照片 3 欄 grid + lightbox + 上傳進度；設備面板電量環形圖（> 50% 綠 / 20–50% 琥珀 / < 20% 紅）+ 連線燈 + 遠端開鎖二次確認、離線 disable；Avatar fallback 圖片→姓名首字→icon、技師必附狀態圓點、stack 超過 5 顯示 +N。

## 4. 命名規範與 Inventory

- Figma：`Category / Component / Variant`（例 `Data Display / StatusBadge / InProgress`）；React：PascalCase；檔案：kebab-case；props：camelCase；**基礎元件放 `components/ui/`（Tailwind v4 + Radix primitives 自建），平台專屬放 `components/smart-lock/`**；設計與工程名稱 1:1 對應。
- Inventory（21 元件）：P0——Button、Input、Select、Card、Modal、Toast、Table、StatusBadge、Avatar、Tabs；P1——SLACountdown、KanbanBoard、MapView、BottomSheet、WorkTimeline、DeviceStatusPanel、CompletionReportForm、AIRecommendationBadge；P2——SignaturePad、PhotoGallery、SkillBadge。全元件 states 覆蓋率 100%（含 loading / error / empty）。

## 5. Token ↔ 工程對接

技術基準（詳見 [./12_SAD.md](./12_SAD.md) 與 [../web/P1/05_architecture_and_design.md](../web/P1/05_architecture_and_design.md) §7）：**Next.js 15（App Router）/ React 19 / TypeScript strict / Tailwind v4 / Radix primitives 自建 `components/ui/` / lucide-react + recharts / @tanstack/react-virtual / 純 React Context（無 redux / zustand / react-query / swr）/ 原生 WebSocket / Playwright E2E**。

| 設計端（Figma）| 工程端 | 同步方式 |
|---|---|---|
| Figma Variables | CSS Custom Properties（`--color-*` 等，globals.css）| Token Studio 匯出 `tokens.json`（W3C Design Token 格式）→ Style Dictionary transform |
| Figma Styles | Tailwind v4 theme（CSS-first `@theme` 引用 CSS 變數）| token pipeline |
| Figma Components | React 元件（`components/ui/` + `components/smart-lock/`）| Code Connect mapping |

同步流程：Figma Variables → tokens.json → Style Dictionary → CSS variables + Tailwind theme + TypeScript 常數（design-tokens.ts）→ Git PR → Review → Merge 生效。dark mode 切換機制（`dark:` variant + CSS 變數）隨 §2.11 dark mode 一併於 🔜 規劃中導入。

## 6. 可及性基線

- WCAG 2.1 AA 對比（§2.2 驗證數據）；CI 以 axe-core 自動檢測。
- Focus ring 一律可見（`shadow.focus-ring`），不被 overflow 裁切。
- 觸控目標 ≥ 44×44px（Tech PWA 硬性）。
- 狀態不單靠顏色：色 + 圖示 + 文字三重指示（StatusBadge / SLACountdown / 技師狀態圓點皆內建）。
- 鍵盤完整可操作：表格排序、Kanban 拖曳（Space/Arrow 替代）、Tabs（Arrow/Home/End）、Modal focus trap。
- `prefers-reduced-motion` 全站尊重（替代方案見 §2.9）。

---

*11_Design_System v1.0 · 2026-07-07 · 上游：smartlock-docs web/P1、technician-platform/P1、ADR-P005*
