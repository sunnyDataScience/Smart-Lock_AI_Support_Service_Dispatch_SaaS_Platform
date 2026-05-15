---
id: DS-0001
title: "Design Foundations"
tier: 2-contracts
status: active
owner: HYBRID
last-reviewed: 2026-05-15
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
---

# 00_Foundations — 電子鎖智能客服與派工平台 基礎系統規格

> 全站的物理定律。Admin Panel、Technician PWA、LINE Bot 三端共享同一套設計語言。
> 本文件為 Single Source of Truth，所有 UI 開發均以此為準。

---

## 目錄

1. [Grid & Layout System](#1-grid--layout-system)
2. [Color System](#2-color-system)
3. [Typography System](#3-typography-system)
4. [Spacing System](#4-spacing-system)
5. [Border & Radius System](#5-border--radius-system)
6. [Elevation & Shadow System](#6-elevation--shadow-system)
7. [Z-Index System](#7-z-index-system)
8. [Iconography](#8-iconography)
9. [Motion & Animation](#9-motion--animation)
10. [Design Tokens 命名規範](#10-design-tokens-命名規範)
11. [Token Mode 管理](#11-token-mode-管理)

---

## 1. Grid & Layout System

本平台有兩套獨立的 Grid System，分別服務 Admin Panel（Desktop-first）與 Technician PWA（Mobile-first）。

### 1.1 Admin Panel Grid

#### 1.1.1 Container

| 屬性 | 值 | 說明 |
|------|-----|------|
| `layout.admin.container.max-width` | 1440px | 主內容區最大寬度 |
| `layout.admin.container.padding` | 24px | 容器左右內距（固定） |
| `layout.admin.container.center` | `margin: 0 auto` | 居中策略 |

#### 1.1.2 Grid

| 斷點 | 欄數 | Gutter | Margin | Container | Sidebar |
|------|------|--------|--------|-----------|---------|
| Mobile (< 768px) | 4 | 16px | 16px | 100% | 隱藏（hamburger） |
| Tablet (768px–1023px) | 8 | 20px | 20px | 100% | 收合 64px |
| Desktop (1024px–1439px) | 12 | 24px | 24px | 100% | 展開 240px |
| Wide (>= 1440px) | 12 | 24px | 24px | 1440px max | 展開 240px |

#### 1.1.3 Breakpoints

| Token | 值 | 說明 |
|-------|-----|------|
| `breakpoint.admin.md` | 768px | Mobile → Tablet（Sidebar 收合） |
| `breakpoint.admin.lg` | 1024px | Tablet → Desktop（Sidebar 展開） |
| `breakpoint.admin.xl` | 1440px | Desktop → Wide（Container 鎖寬） |

#### 1.1.4 Sidebar Layout

| 屬性 | 展開 | 收合 |
|------|------|------|
| Token | `space.sidebar` | `space.sidebar.collapsed` |
| 寬度 | 240px | 64px |
| 行為 | 顯示 icon + 文字標籤 | 僅顯示 icon，hover 展開 tooltip |
| 過渡動效 | `motion.duration.slow` (300ms) + `motion.ease.default` | 同左 |
| 內容區計算 | `calc(100vw - 240px)` 或 `max-width: 1200px` | `calc(100vw - 64px)` 或 `max-width: 1376px` |

#### 1.1.5 Layout Primitives（Admin）

| 名稱 | 規則 | 用途 |
|------|------|------|
| Admin Shell | `grid grid-cols-[240px_1fr]` (desktop) / `grid grid-cols-[64px_1fr]` (tablet) | Sidebar + Main |
| Page Header | `h-16 (64px)` + `sticky top-0` + `z-sticky` | 頁面頂部導航列 |
| Content Area | `max-w-[1200px]` + `mx-auto` + `px-6` | 主內容區（扣除 Sidebar 後） |
| Dashboard Grid | `grid grid-cols-4 gap-6` (desktop) → `grid-cols-2` (tablet) → `grid-cols-1` (mobile) | KPI 卡片排列 |
| Kanban Board | `flex overflow-x-auto gap-4` + 每欄 `w-[320px] flex-shrink-0` | 工單看板排列 |
| Split Detail | `grid grid-cols-[1fr_400px]` (desktop) → `stack` (mobile) | 列表 + 詳情面板 |

### 1.2 Technician PWA Grid

#### 1.2.1 Container

| 屬性 | 值 | 說明 |
|------|-----|------|
| `layout.tech.container.max-width` | 480px | 主內容區最大寬度 |
| `layout.tech.container.padding` | 16px | 容器左右內距（固定） |
| `layout.tech.container.center` | `margin: 0 auto` | 居中策略 |

#### 1.2.2 Grid

| 斷點 | 欄數 | Gutter | Margin | Container |
|------|------|--------|--------|-----------|
| All (< 480px) | 1 | — | 16px | 100% |
| Wide phone (>= 480px) | 1 | — | 16px | 480px max |

#### 1.2.3 Breakpoints

| Token | 值 | 說明 |
|-------|-----|------|
| `breakpoint.tech.sm` | 480px | Container 鎖寬（唯一斷點） |

#### 1.2.4 Bottom Navigation

| 屬性 | 值 | 說明 |
|------|-----|------|
| Token | `space.bottomnav` | 底部導航高度 |
| 高度 | 56px | 固定高度 |
| Safe Area | `+ env(safe-area-inset-bottom)` | iOS 瀏海機底部安全區 |
| Token（含安全區） | `space.safe-area` | `env(safe-area-inset-bottom)` |
| 總高度計算 | `calc(56px + env(safe-area-inset-bottom))` | 實際佔用高度 |
| 內容底部 padding | `pb-[calc(56px+env(safe-area-inset-bottom)+16px)]` | 確保內容不被遮蓋 |

#### 1.2.5 Layout Primitives（Tech PWA）

| 名稱 | 規則 | 用途 |
|------|------|------|
| PWA Shell | `min-h-screen` + `flex flex-col` + `pb-bottomnav-safe` | 頁面外殼 |
| Top Bar | `h-14 (56px)` + `sticky top-0` + `z-sticky` | 頂部導航（返回 + 標題） |
| Bottom Nav | `fixed bottom-0` + `h-14` + `pb-safe` + `z-bottomnav` | 底部 Tab 導航 |
| Card Stack | `flex flex-col gap-3 px-4` | 工單卡片堆疊 |
| Map Full | `h-[calc(100vh-56px-56px-env(safe-area-inset-bottom))]` | 全螢幕地圖（扣頂部與底部） |
| Bottom Sheet | `fixed bottom-0 inset-x-0` + `rounded-t-2xl` + `z-bottomsheet` | 地圖上的詳情面板 |

### 1.3 共通 RWD 行為規則

```
規則 1：平台分離
  - Admin Panel：Desktop-first，media query 用 max-width 向下覆蓋
  - Tech PWA：Mobile-first，極少 RWD（單一欄位）
  - 兩套 codebase 獨立，不共用 layout

規則 2：Admin 斷點行為
  - Sidebar：desktop 展開 240px，tablet 收合 64px，mobile 隱藏改 hamburger
  - Table：desktop 橫向表格，tablet 隱藏次要欄位，mobile 轉為 card list
  - Form：desktop 雙欄（label 左 / input 右），mobile 單欄堆疊
  - Modal：desktop 居中彈窗（max-w-lg），mobile 全螢幕 bottom sheet
  - Kanban：desktop 水平捲動看板，tablet 2 欄，mobile 改為 list view

規則 3：Tech PWA 行為
  - 永遠單欄，無斷點變化
  - 地圖全螢幕 + 底部 Sheet 呈現工單詳情
  - 所有可點擊元素最小 44×44px touch target
  - 手勢：下拉重新整理、左右滑動切換工單狀態

規則 4：圖片策略
  - Admin 圖片：使用 next/image 的 srcset + sizes
  - Tech PWA：圖片壓縮優先（離線快取考量）
  - 工單照片：max 1920px，縮圖 200px
```

---

## 2. Color System

### 2.1 Brand Colors

| Token | Light 色值 | 用途 | WCAG 對比（vs #FFFFFF） |
|-------|-----------|------|----------------------|
| `color.brand.primary` | #2563EB | Trust Blue — 主要品牌色、Primary CTA、Active 狀態、Focus ring | 4.6:1 AA |
| `color.brand.primary.hover` | #1D4ED8 | Primary hover（加深一階） | 5.9:1 AA |
| `color.brand.primary.active` | #1E40AF | Primary active/pressed（加深兩階） | 7.1:1 AAA |
| `color.brand.primary.light` | #DBEAFE | Primary 淺色底（tag bg、selected row bg） | N/A（用作背景） |
| `color.brand.accent` | #F59E0B | Amber CTA — 強調色、緊急操作、派工按鈕 | 2.1:1（需搭配深色文字） |
| `color.brand.accent.hover` | #D97706 | Accent hover | 3.3:1 |
| `color.brand.accent.active` | #B45309 | Accent active | 4.5:1 AA |
| `color.brand.accent.light` | #FEF3C7 | Accent 淺色底 | N/A（用作背景） |
| `color.brand.secondary` | #1E293B | Slate — Sidebar 背景、深色區域 | 14.5:1 AAA |
| `color.brand.secondary.hover` | #334155 | Secondary hover | 11.1:1 AAA |
| `color.brand.secondary.active` | #475569 | Secondary active | 7.5:1 AAA |

### 2.2 Work Order Status Colors（工單狀態語意色）

本平台有 6 大工單狀態色系，每個狀態包含 `main`（圖示/標籤色）、`bg`（Badge 背景/行高亮）、`text`（淺色背景上的文字色）。

| 狀態 | Token | main | bg | text | 用途 |
|------|-------|------|-----|------|------|
| Pending（待處理） | `color.status.pending` | #6366F1 | #EEF2FF | #3730A3 | 新建工單、待指派 |
| Assigned（已指派） | `color.status.assigned` | #8B5CF6 | #F5F3FF | #5B21B6 | 已分派技師、待出發 |
| Active（進行中） | `color.status.active` | #3B82F6 | #EFF6FF | #1E40AF | 技師已到場、施工中 |
| Warning（警告/逾時） | `color.status.warning` | #F59E0B | #FEF3C7 | #92400E | SLA 即將到期、需注意 |
| Success（完成） | `color.status.success` | #10B981 | #ECFDF5 | #065F46 | 工單完成、驗收通過 |
| Danger（異常/取消） | `color.status.danger` | #EF4444 | #FEF2F2 | #991B1B | 工單取消、施工異常、SLA 超時 |

#### 2.2.1 完整 13 態工單狀態 → 色系對應

| 工單狀態 | 中文 | 使用色系 |
|----------|------|---------|
| `new` | 新建 | `status.pending` |
| `pending_assignment` | 待指派 | `status.pending` |
| `assigned` | 已指派 | `status.assigned` |
| `accepted` | 技師已接受 | `status.assigned` |
| `en_route` | 前往中 | `status.active` |
| `arrived` | 已到場 | `status.active` |
| `in_progress` | 施工中 | `status.active` |
| `pending_review` | 待審核 | `status.warning` |
| `completed` | 完成 | `status.success` |
| `closed` | 結案 | `status.success` |
| `cancelled` | 已取消 | `status.danger` |
| `on_hold` | 暫停 | `status.warning` |
| `escalated` | 已升級 | `status.danger` |

### 2.3 通用語意色

| Token | Light 色值 | Dark 色值（V2.0） | 用途 |
|-------|-----------|-------------------|------|
| `color.success` | #10B981 | #34D399 | 成功、通過、正面操作 |
| `color.success.bg` | #ECFDF5 | #064E3B | 成功狀態背景 |
| `color.success.text` | #065F46 | #A7F3D0 | 成功文字（淺底上） |
| `color.warning` | #F59E0B | #FBBF24 | 警告、SLA 預警 |
| `color.warning.bg` | #FEF3C7 | #78350F | 警告狀態背景 |
| `color.warning.text` | #92400E | #FDE68A | 警告文字（淺底上） |
| `color.error` | #EF4444 | #F87171 | 錯誤、危險、負面 |
| `color.error.bg` | #FEF2F2 | #450A0A | 錯誤狀態背景 |
| `color.error.text` | #991B1B | #FECACA | 錯誤文字（淺底上） |
| `color.info` | #3B82F6 | #60A5FA | 資訊、提示 |
| `color.info.bg` | #EFF6FF | #172554 | 資訊狀態背景 |
| `color.info.text` | #1E40AF | #BFDBFE | 資訊文字（淺底上） |

### 2.4 Surface Colors

| Token | Light | Dark（V2.0） | 用途 |
|-------|-------|-------------|------|
| `color.bg.page` | #F8FAFC | #0F172A | 頁面底色 |
| `color.bg.surface` | #FFFFFF | #1E293B | 卡片/容器底色 |
| `color.bg.elevated` | #FFFFFF | #334155 | 浮層/Modal/Dropdown 底色 |
| `color.bg.muted` | #F1F5F9 | #1E293B | 低調背景（disabled 區、striped row） |
| `color.bg.sidebar` | #1E293B | #0F172A | Sidebar 專用背景 |
| `color.bg.overlay` | rgba(15,23,42,0.6) | rgba(0,0,0,0.7) | 遮罩層（Modal backdrop） |
| `color.bg.selected` | #DBEAFE | #1E3A5F | 選中行/選中項目 |
| `color.bg.hover` | #F1F5F9 | #334155 | 列表項 hover 背景 |

### 2.5 Text Colors

| Token | Light | Dark（V2.0） | 用途 |
|-------|-------|-------------|------|
| `color.text.primary` | #0F172A | #F1F5F9 | 主要文字（標題、內文） |
| `color.text.secondary` | #64748B | #94A3B8 | 次要文字（說明、label） |
| `color.text.disabled` | #94A3B8 | #475569 | 停用狀態文字 |
| `color.text.inverse` | #FFFFFF | #0F172A | 反轉文字（深色底上的白字） |
| `color.text.link` | #2563EB | #60A5FA | 連結文字 |
| `color.text.link.hover` | #1D4ED8 | #93C5FD | 連結 hover |
| `color.text.on-primary` | #FFFFFF | #FFFFFF | Primary 按鈕上的文字 |
| `color.text.on-accent` | #0F172A | #0F172A | Accent 按鈕上的文字（Amber 底需深色字） |
| `color.text.sidebar` | #CBD5E1 | #94A3B8 | Sidebar 內文字 |
| `color.text.sidebar.active` | #FFFFFF | #F1F5F9 | Sidebar 選中項文字 |

### 2.6 Border Colors

| Token | Light | Dark（V2.0） | 用途 |
|-------|-------|-------------|------|
| `color.border.default` | #E2E8F0 | #334155 | 預設邊框（Card、Divider） |
| `color.border.hover` | #CBD5E1 | #475569 | hover 邊框 |
| `color.border.focus` | #2563EB | #60A5FA | Focus ring 色（= brand.primary） |
| `color.border.error` | #EF4444 | #F87171 | 錯誤邊框 |
| `color.border.success` | #10B981 | #34D399 | 成功邊框 |
| `color.border.sla.green` | #10B981 | #34D399 | SLA 剩餘 > 50% |
| `color.border.sla.amber` | #F59E0B | #FBBF24 | SLA 剩餘 20%–50% |
| `color.border.sla.red` | #EF4444 | #F87171 | SLA 剩餘 < 20% |

### 2.7 對比度規則

```
必須遵守 WCAG 2.1 AA 標準：

一般文字（< 18px）：對比度 >= 4.5:1
  - color.text.primary (#0F172A) vs color.bg.surface (#FFFFFF) = 15.4:1 ✅
  - color.text.secondary (#64748B) vs color.bg.surface (#FFFFFF) = 5.0:1 ✅
  - color.text.disabled (#94A3B8) vs color.bg.surface (#FFFFFF) = 2.9:1 （僅用於 disabled，豁免）

大文字（>= 18px bold 或 >= 24px）：對比度 >= 3:1
  - color.brand.primary (#2563EB) vs #FFFFFF = 4.6:1 ✅
  - color.brand.accent (#F59E0B) vs #FFFFFF = 2.1:1 ❌ → Accent 按鈕文字必須用深色 #0F172A

UI 元件（按鈕邊框、輸入框邊框）：對比度 >= 3:1
  - color.border.default (#E2E8F0) vs #FFFFFF = 1.5:1 ⚠️ → 搭配 shadow 補強視覺區分

Status Badge 文字對比：
  - status.pending.text (#3730A3) vs status.pending.bg (#EEF2FF) = 8.2:1 ✅
  - status.assigned.text (#5B21B6) vs status.assigned.bg (#F5F3FF) = 7.6:1 ✅
  - status.active.text (#1E40AF) vs status.active.bg (#EFF6FF) = 8.9:1 ✅
  - status.warning.text (#92400E) vs status.warning.bg (#FEF3C7) = 6.3:1 ✅
  - status.success.text (#065F46) vs status.success.bg (#ECFDF5) = 7.1:1 ✅
  - status.danger.text (#991B1B) vs status.danger.bg (#FEF2F2) = 7.8:1 ✅

工具：
  - Figma 插件：Contrast Checker
  - 線上：webaim.org/resources/contrastchecker
  - CI：axe-core 自動檢測
```

---

## 3. Typography System

### 3.1 字體堆疊

| 用途 | 字體 | Fallback | 載入策略 |
|------|------|----------|---------|
| 英文 | `Inter` | `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` | Google Fonts variable, `font-display: swap` |
| 中文 | `Noto Sans TC` | `'PingFang TC', 'Microsoft JhengHei', sans-serif` | Google Fonts weights: 400, 600, 700 |
| 程式碼 | `JetBrains Mono` | `'Fira Code', 'SF Mono', Consolas, monospace` | Google Fonts, 用於序號/代碼/JSON |

```css
/* Tailwind config font-family */
fontFamily: {
  sans: ['Inter', 'Noto Sans TC', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
  mono: ['JetBrains Mono', 'Fira Code', 'SF Mono', 'Consolas', 'monospace'],
}
```

### 3.2 字級階梯

| Token | 字級 | 行高 | 字重 | Letter Spacing | 用途 |
|-------|------|------|------|---------------|------|
| `text.display` | 32px / 2rem | 1.2 | 700 | -0.02em | Dashboard 大標題、Hero |
| `text.heading.h1` | 28px / 1.75rem | 1.25 | 700 | -0.01em | 頁面主標題（工單管理、技師列表） |
| `text.heading.h2` | 24px / 1.5rem | 1.3 | 600 | -0.01em | 區塊標題（篩選區、統計區） |
| `text.heading.h3` | 20px / 1.25rem | 1.4 | 600 | 0 | 卡片標題、Modal 標題 |
| `text.heading.h4` | 16px / 1rem | 1.5 | 600 | 0.01em | 小節標題、表格欄位標題 |
| `text.body.lg` | 16px / 1rem | 1.6 | 400 | 0 | 大段落文字、工單描述 |
| `text.body.md` | 14px / 0.875rem | 1.5 | 400 | 0 | 標準內文、表格資料 |
| `text.body.sm` | 12px / 0.75rem | 1.5 | 400 | 0 | 小字說明、輔助資訊 |
| `text.caption` | 11px / 0.6875rem | 1.4 | 400 | 0.02em | 時間戳、標註、Badge 內文字 |
| `text.overline` | 12px / 0.75rem | 1.4 | 600 | 0.05em | 上標分類標籤（大寫英文） |
| `text.kpi` | 36px / 2.25rem | 1.1 | 700 | -0.02em | Dashboard KPI 數字（`font-variant-numeric: tabular-nums`） |

### 3.3 中英混排規則

```
規則 1：字體順序
  - font-family: 'Inter', 'Noto Sans TC', sans-serif
  - 英文字體在前，中文字體在後（瀏覽器自動 fallback）

規則 2：行高
  - 純英文段落：line-height 1.5
  - 中文或中英混排：line-height 1.6–1.8（中文字高較大）
  - 本平台大部分為中英混排，預設 1.5–1.6

規則 3：標點符號
  - 使用全形中文標點（，。；：「」）
  - 數字和英文之間加半形空格（例：共 3 個工單、使用 Yale 電子鎖）
  - 工單編號使用 monospace（例：WO-20260421-001）

規則 4：數字
  - KPI 數字：tabular-nums（等寬數字）+ JetBrains Mono
  - 表格數字：tabular-nums（等寬數字，欄位對齊）
  - 內文數字：proportional-nums（自然寬度）
  - 金額格式：千分位逗號（例：$12,500）
  - 電話格式：0912-345-678

規則 5：工單編號
  - 使用 JetBrains Mono，確保辨識度
  - 格式：WO-YYYYMMDD-NNN
```

### 3.4 RWD 字級調整（僅 Admin Panel）

| Token | Desktop (>= 1024px) | Tablet (768px–1023px) | Mobile (< 768px) |
|-------|---------------------|----------------------|-------------------|
| `text.display` | 32px | 28px | 24px |
| `text.heading.h1` | 28px | 24px | 22px |
| `text.heading.h2` | 24px | 22px | 20px |
| `text.heading.h3` | 20px | 18px | 18px |
| `text.kpi` | 36px | 32px | 28px |
| 其餘 | 不變 | 不變 | 不變 |

> Tech PWA 不做 RWD 字級調整——已為 mobile 尺寸最佳化，無需再縮。

---

## 4. Spacing System

### 4.1 Spacing Scale（4px 基數）

| Token | 值 | 用途範例 |
|-------|-----|---------|
| `space.0.5` | 2px | 微調（icon 與 badge 數字間距） |
| `space.1` | 4px | icon 與文字間距、元素內微間距 |
| `space.1.5` | 6px | 緊湊元件內距（Badge padding） |
| `space.2` | 8px | 元素內標準間距、相關元素間距 |
| `space.3` | 12px | 標籤與文字、列表項間距、表格 cell padding |
| `space.4` | 16px | 元件間距、Card padding (Tech PWA)、Container padding (Tech) |
| `space.5` | 20px | Card padding (Admin)、元件群組間距 |
| `space.6` | 24px | 區塊間距、Admin Container padding、Gutter |
| `space.8` | 32px | 大區塊間距、Section 間距 |
| `space.10` | 40px | Section 間距（mobile） |
| `space.12` | 48px | Section 間距（desktop） |
| `space.16` | 64px | 頁面級間距、Page Header 高度 |
| `space.20` | 80px | 大間距（Dashboard 頂部留白） |
| `space.24` | 96px | 超大間距 |

### 4.2 平台專用 Spacing Tokens

| Token | 值 | 平台 | 用途 |
|-------|-----|------|------|
| `space.sidebar` | 240px | Admin | Sidebar 展開寬度 |
| `space.sidebar.collapsed` | 64px | Admin | Sidebar 收合寬度 |
| `space.page-header` | 64px | Admin | 頂部導航列高度 |
| `space.bottomnav` | 56px | Tech PWA | 底部導航列高度 |
| `space.safe-area` | `env(safe-area-inset-bottom)` | Tech PWA | iOS 底部安全區 |
| `space.bottomnav.total` | `calc(56px + env(safe-area-inset-bottom))` | Tech PWA | 底部導航含安全區總高 |
| `space.topbar` | 56px | Tech PWA | 頂部標題列高度 |
| `space.touch-target` | 44px | Tech PWA | 最小觸控目標（WCAG 2.5.5） |
| `space.kanban.column` | 320px | Admin | Kanban 單欄寬度 |
| `space.kanban.gap` | 16px | Admin | Kanban 欄間距 |

### 4.3 使用規則

```
規則 1：鄰近原則
  - 相關元素間距 < 不相關元素間距
  - 例：工單標題與描述之間 space.2 (8px)，工單卡片之間 space.3 (12px)

規則 2：一致性原則
  - 同層級元素使用相同間距
  - Kanban 看板中每欄間距一致 (space.4 = 16px)
  - Dashboard KPI 卡片間距一致 (space.6 = 24px)

規則 3：層級對應
  - 元素內部 → space.1–3 (4–12px)
  - 元件間 → space.4–6 (16–24px)
  - Section 間 → space.8–12 (32–48px)
  - Page 間 → space.16–24 (64–96px)

規則 4：Padding vs Margin
  - Padding：用在容器內部（Card padding、Button padding）
  - Margin：用在容器外部（元件間距、Section 間距）
  - 永遠用 token，不寫 magic number

規則 5：Tech PWA 最小 touch target
  - 所有可點擊元素 >= 44×44px
  - 若視覺尺寸小於 44px，用 padding 補足觸控區域
```

---

## 5. Border & Radius System

### 5.1 Border

| Token | 值 | 用途 |
|-------|-----|------|
| `border.width.default` | 1px | 標準邊框（Card、Input、Divider） |
| `border.width.thick` | 2px | 強調邊框（Focus ring、Active Tab、SLA indicator） |
| `border.width.status` | 3px | 狀態指示（Kanban 卡片左側 status stripe） |
| `border.style` | solid | 統一使用 solid |

### 5.2 Border Radius

| Token | 值 | 用途 |
|-------|-----|------|
| `radius.none` | 0px | 無圓角 |
| `radius.sm` | 4px | 小元素（Tag, Badge, Tooltip, 表格 cell） |
| `radius.md` | 6px | 按鈕、輸入框、Select |
| `radius.lg` | 8px | 卡片、容器、工單卡片 |
| `radius.xl` | 12px | Modal、Dialog、大容器 |
| `radius.2xl` | 16px | Bottom Sheet 頂部圓角、大圓角卡片 |
| `radius.full` | 9999px | 圓形（Avatar, Pill Badge, 圓形按鈕） |

### 5.3 Radius 使用規則

```
規則 1：外層圓角 > 內層圓角
  - Card radius.lg (8px) 內的 Button radius.md (6px)
  - Modal radius.xl (12px) 內的 Card radius.lg (8px)
  - 內層 radius ≈ 外層 radius - padding

規則 2：平台差異
  - Admin Panel：radius.lg (8px) 為主要卡片圓角
  - Tech PWA：radius.xl (12px) 為主要卡片圓角（較大更易觸控）
  - Bottom Sheet：radius.2xl (16px) 頂部圓角

規則 3：Kanban 卡片
  - 卡片本體：radius.lg (8px)
  - 左側 status stripe：僅左側圓角 radius.lg (8px)
  - 拖曳中：radius 不變，靠 shadow 表示浮起
```

---

## 6. Elevation & Shadow System

| Token | 值 | 用途 |
|-------|-----|------|
| `shadow.none` | none | 平面元素 |
| `shadow.xs` | `0 1px 2px rgba(0,0,0,0.05)` | 輕微浮起（Input default） |
| `shadow.sm` | `0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)` | 卡片預設、工單卡片 |
| `shadow.md` | `0 4px 6px rgba(0,0,0,0.1), 0 2px 4px rgba(0,0,0,0.06)` | 懸浮卡片、卡片 hover |
| `shadow.lg` | `0 10px 15px rgba(0,0,0,0.1), 0 4px 6px rgba(0,0,0,0.05)` | Dropdown、Popover、Select menu |
| `shadow.xl` | `0 20px 25px rgba(0,0,0,0.1), 0 10px 10px rgba(0,0,0,0.04)` | Modal、Dialog |
| `shadow.2xl` | `0 25px 50px rgba(0,0,0,0.25)` | Toast、最高層 |
| `shadow.kanban` | `0 8px 16px rgba(37,99,235,0.15)` | Kanban 卡片拖曳狀態（帶品牌色暈染） |
| `shadow.bottomsheet` | `0 -4px 16px rgba(0,0,0,0.12)` | Bottom Sheet 頂部陰影（向上投影） |
| `shadow.sidebar` | `4px 0 8px rgba(0,0,0,0.08)` | Sidebar 右側陰影（僅 tablet 收合態 hover 展開時） |
| `shadow.map-control` | `0 2px 6px rgba(0,0,0,0.2)` | 地圖上的浮動控制按鈕 |
| `shadow.focus-ring` | `0 0 0 3px rgba(37,99,235,0.3)` | Focus ring 外發光（搭配 border.focus） |

---

## 7. Z-Index System

| Layer | Z-Index | 元素 |
|-------|---------|------|
| Base | 0 | 頁面內容、卡片 |
| Elevated | 5 | Hover 浮起的卡片 |
| Sticky | 10 | Sticky header、Sticky table header、Sidebar |
| Kanban Drag | 15 | Kanban 拖曳中的卡片 |
| Dropdown | 20 | Select dropdown、Popover、DatePicker |
| Bottom Sheet | 25 | Tech PWA 的 Bottom Sheet |
| Overlay | 30 | Modal backdrop、遮罩層 |
| Map Controls | 35 | 地圖上的浮動控制（縮放、定位按鈕） |
| Modal | 40 | Modal、Dialog、Drawer |
| Toast | 50 | Toast 通知、Snackbar |
| Tooltip | 60 | Tooltip |
| Command | 70 | Command Palette（如有） |

```
規則：
  - 同層元素靠 DOM 順序決定堆疊
  - 不要在上述定義之外自創 z-index
  - 新增層級需經 Design System Lead 審核
  - Tech PWA 的 Bottom Sheet 在 Map Controls 之下，避免遮擋地圖操作
```

---

## 8. Iconography

### 8.1 Icon 規格

| 屬性 | 值 |
|------|-----|
| 圖標庫 | Lucide Icons（shadcn/ui 內建） |
| 風格 | Outline（線條風格），一致線寬 1.5px |
| 尺寸 | 16px / 20px / 24px / 32px |
| 顏色 | 繼承 `currentColor` |
| 圓角 | 與系統圓角一致 |

### 8.2 Icon 尺寸對應

| 尺寸 | 用途 | 範例 |
|------|------|------|
| 16px | 行內 icon（Badge 內、表格操作、inline hint） | 排序箭頭、Info tooltip |
| 20px | 按鈕內 icon、導航項、表單 prefix/suffix | 搜尋、篩選、通知鈴 |
| 24px | 獨立 icon（空狀態配圖、Feature icon、Sidebar nav） | Sidebar 選項圖示 |
| 32px | 大型展示用（Dashboard 卡片 icon、空狀態主圖） | 儀表板工單數圖示 |

### 8.3 自定義 Icon 規格（Lucide 不足時）

以下為本平台特有的 icon，需自行設計或使用組合：

| Icon 名稱 | 描述 | 建議來源 | 尺寸 |
|-----------|------|---------|------|
| `icon.lock.locked` | 電子鎖上鎖狀態 | Lucide `Lock` | 20/24px |
| `icon.lock.unlocked` | 電子鎖解鎖狀態 | Lucide `LockOpen` | 20/24px |
| `icon.lock.error` | 電子鎖異常 | Lucide `Lock` + 紅色圓點 overlay | 20/24px |
| `icon.lock.offline` | 電子鎖離線 | Lucide `Lock` + 斜線 overlay | 20/24px |
| `icon.battery.full` | 電池滿電 (>75%) | Lucide `BatteryFull` | 16/20px |
| `icon.battery.medium` | 電池中等 (25%–75%) | Lucide `BatteryMedium` | 16/20px |
| `icon.battery.low` | 電池低電 (<25%) | Lucide `BatteryLow` + 紅色 | 16/20px |
| `icon.battery.charging` | 充電中 | Lucide `BatteryCharging` | 16/20px |
| `icon.connectivity.wifi` | WiFi 連線 | Lucide `Wifi` | 16/20px |
| `icon.connectivity.bluetooth` | 藍牙連線 | Lucide `Bluetooth` | 16/20px |
| `icon.connectivity.offline` | 離線狀態 | Lucide `WifiOff` | 16/20px |
| `icon.connectivity.z-wave` | Z-Wave 連線 | 自定義（Z 字波紋） | 16/20px |
| `icon.technician.available` | 技師可派工 | Lucide `UserCheck` + 綠色圓點 | 24px |
| `icon.technician.busy` | 技師忙碌中 | Lucide `User` + 橙色圓點 | 24px |
| `icon.technician.offline` | 技師離線 | Lucide `UserX` + 灰色圓點 | 24px |
| `icon.technician.en-route` | 技師移動中 | Lucide `UserCog` + 藍色圓點 | 24px |

### 8.4 Icon 使用規則

```
規則 1：間距
  - Icon + Text：space.1 (4px) 到 space.2 (8px)
  - Icon button padding：space.2 (8px)
  - Tech PWA icon button：最小 44×44px touch target

規則 2：可及性
  - 純 icon 按鈕必須有 aria-label（例：aria-label="篩選工單"）
  - 裝飾性 icon 使用 aria-hidden="true"
  - 狀態指示 icon 必須搭配文字標籤（不依賴顏色/形狀單獨傳達）

規則 3：技師狀態圓點
  - 圓點尺寸：8px 圓形
  - 位置：icon 右下角，偏移 -2px
  - 顏色：available=#10B981, busy=#F59E0B, offline=#94A3B8, en-route=#3B82F6
  - 圓點需有 2px 白色描邊（避免與 icon 融合）

規則 4：電池等級色彩
  - > 75%：color.success (#10B981)
  - 25%–75%：color.text.primary (繼承)
  - < 25%：color.error (#EF4444)
  - 充電中：color.brand.primary (#2563EB)
```

---

## 9. Motion & Animation

### 9.1 Duration

| Token | 值 | 用途 |
|-------|-----|------|
| `motion.duration.instant` | 100ms | Hover 狀態變化、Toggle |
| `motion.duration.fast` | 150ms | Checkbox、Radio、小型互動 |
| `motion.duration.normal` | 200ms | Button press、Fade in/out、Tab 切換 |
| `motion.duration.slow` | 300ms | Modal 開合、Drawer 滑入、Sidebar 展開/收合、Bottom Sheet |
| `motion.duration.slower` | 500ms | Page transition、大型內容切換 |
| `motion.duration.pulse` | 2000ms | SLA 脈搏動畫週期 |

### 9.2 Easing

| Token | 值 | 用途 |
|-------|-----|------|
| `motion.ease.default` | `cubic-bezier(0.4, 0, 0.2, 1)` | 通用過渡 |
| `motion.ease.in` | `cubic-bezier(0.4, 0, 1, 1)` | 元素離開畫面 |
| `motion.ease.out` | `cubic-bezier(0, 0, 0.2, 1)` | 元素進入畫面 |
| `motion.ease.in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | 元素位移（Sidebar、Bottom Sheet） |
| `motion.ease.spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | 彈跳效果（Kanban 卡片放下、通知 badge 出現） |

### 9.3 平台專用動效

#### 9.3.1 SLA Pulse Animation（SLA 脈搏動畫）

```css
/* 用途：工單卡片 SLA 逾期時，卡片邊框脈動提醒 */
@keyframes sla-pulse {
  0%, 100% {
    border-color: var(--color-border-sla-red);       /* #EF4444 */
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  50% {
    border-color: var(--color-border-sla-red);
    box-shadow: 0 0 0 4px rgba(239, 68, 68, 0);
  }
}

.sla-overdue {
  animation: sla-pulse 2s ease-in-out infinite;
  border-width: 2px;
}

/* SLA 三階段視覺 */
.sla-green  { border-left: 3px solid var(--color-border-sla-green);  }  /* > 50% */
.sla-amber  { border-left: 3px solid var(--color-border-sla-amber);  }  /* 20%–50% */
.sla-red    { border-left: 3px solid var(--color-border-sla-red);    }  /* < 20% */
.sla-red.overdue { animation: sla-pulse 2s ease-in-out infinite; }       /* 已超時 */
```

#### 9.3.2 Kanban Drag Animation

```css
/* 用途：Kanban 看板拖曳卡片時的浮起效果 */
.kanban-card-dragging {
  transform: rotate(2deg) scale(1.02);
  box-shadow: var(--shadow-kanban);   /* 0 8px 16px rgba(37,99,235,0.15) */
  opacity: 0.95;
  transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 200ms ease-out;
  z-index: var(--z-kanban-drag);      /* 15 */
}

/* 拖曳結束放下 */
.kanban-card-dropped {
  transform: rotate(0deg) scale(1);
  box-shadow: var(--shadow-sm);
  transition: transform 300ms cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 300ms ease-out;
}

/* 放置區高亮 */
.kanban-column-drop-target {
  background: var(--color-brand-primary-light);  /* #DBEAFE */
  border: 2px dashed var(--color-brand-primary); /* #2563EB */
  transition: background 150ms ease-out, border 150ms ease-out;
}
```

#### 9.3.3 Bottom Sheet Slide（Tech PWA）

```css
/* 用途：Tech PWA 地圖頁的 Bottom Sheet 滑入 */
@keyframes bottomsheet-slide-up {
  from {
    transform: translateY(100%);
  }
  to {
    transform: translateY(0);
  }
}

.bottomsheet-enter {
  animation: bottomsheet-slide-up 300ms cubic-bezier(0, 0, 0.2, 1) forwards;
}

.bottomsheet-exit {
  animation: bottomsheet-slide-up 200ms cubic-bezier(0.4, 0, 1, 1) reverse forwards;
}

/* 三段式 snap point */
.bottomsheet-peek    { transform: translateY(calc(100% - 120px)); }  /* 僅露出摘要 */
.bottomsheet-half    { transform: translateY(50%); }                  /* 半螢幕 */
.bottomsheet-full    { transform: translateY(0); }                    /* 全螢幕 */
```

#### 9.3.4 Map Pin Pulse（地圖圖釘脈動）

```css
/* 用途：地圖上的工單圖釘，表示進行中的工單 */
@keyframes map-pin-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.3);
    opacity: 0;
  }
}

.map-pin-active::after {
  content: '';
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-status-active);  /* #3B82F6 */
  animation: map-pin-pulse 2s ease-in-out infinite;
  z-index: -1;
}
```

#### 9.3.5 Sidebar Toggle（Admin）

```css
/* 用途：Admin Sidebar 展開/收合 */
.sidebar-expanded {
  width: var(--space-sidebar);              /* 240px */
  transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-collapsed {
  width: var(--space-sidebar-collapsed);    /* 64px */
  transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Sidebar 文字標籤 fade */
.sidebar-label {
  transition: opacity 150ms ease-out;
}
.sidebar-collapsed .sidebar-label {
  opacity: 0;
  pointer-events: none;
}
```

### 9.4 動效規則

```
規則 1：目的性
  - 動效必須有功能目的（引導注意力、回饋操作、表示狀態變化）
  - SLA pulse = 吸引注意力到逾期工單
  - Kanban drag = 表示元素正在被操作
  - 不做純裝飾性動畫

規則 2：可中斷
  - 使用者操作可以中斷任何動畫
  - Bottom Sheet 拖曳中可隨時改變方向
  - Sidebar 展開中點擊可立即收合

規則 3：減少動態偏好
  - 遵守 prefers-reduced-motion
  - 替代方案：SLA pulse → 改用靜態紅色邊框
  - 替代方案：Map pin pulse → 改用靜態圖釘
  - 替代方案：Slide → 改用 opacity fade

規則 4：效能
  - 只 animate transform 和 opacity（GPU 加速）
  - 避免 animate layout properties（width, height, top, left）
  - Sidebar 寬度動畫是例外，用 will-change: width 提示瀏覽器
  - Tech PWA 特別注意：60fps 是底線

規則 5：WebSocket 狀態同步動效
  - 工單狀態變更時：卡片邊框顏色變化 200ms ease
  - 新工單進入：slide-down + fade-in 300ms
  - 工單被其他人拖走：fade-out 200ms + placeholder 顯示
```

---

## 10. Design Tokens 命名規範

### 10.1 命名結構

```
{category}.{property}.{variant}.{state}

範例：
  color.bg.surface               ← 類別.屬性.變體
  color.text.primary             ← 類別.屬性.變體
  color.status.pending           ← 類別.屬性.變體（工單狀態）
  color.status.pending.bg        ← 類別.屬性.變體.子變體
  color.border.sla.red           ← 類別.屬性.子類.變體
  text.heading.h1                ← 類別.屬性.尺寸
  text.kpi                       ← 類別.特殊用途
  space.sidebar                  ← 類別.特殊用途
  space.sidebar.collapsed        ← 類別.特殊用途.狀態
  space.bottomnav                ← 類別.特殊用途
  shadow.kanban                  ← 類別.特殊用途
  z.kanban-drag                  ← 類別.層級名
  motion.duration.pulse          ← 類別.屬性.值
  layout.admin.container.max-width ← 類別.平台.屬性.子屬性
  layout.tech.container.padding  ← 類別.平台.屬性.子屬性
  breakpoint.admin.lg            ← 類別.平台.尺寸
  breakpoint.tech.sm             ← 類別.平台.尺寸
```

### 10.2 命名規則

```
規則 1：小寫 + 點分隔
  ✅ color.bg.surface
  ❌ Color.Bg.Surface
  ❌ color-bg-surface

規則 2：語意化而非描述值
  ✅ color.status.pending（語意：待處理狀態色）
  ❌ color.indigo.500（描述：靛藍色 500）

規則 3：平台前綴（佈局類 token）
  ✅ layout.admin.container.max-width
  ✅ layout.tech.container.padding
  ✅ breakpoint.admin.lg
  ❌ layout.container.max-width（歧義：哪個平台？）

規則 4：可預測性
  - 同類 token 遵循相同結構
  - 新增 token 時使用者能「猜到」名字
  - 狀態色一定有 main / bg / text 三件套

規則 5：避免縮寫（除非公認）
  ✅ color.bg（公認縮寫）
  ✅ space.bottomnav（底部導航）
  ❌ color.brd → 應寫 color.border
  ❌ space.sb → 應寫 space.sidebar
```

### 10.3 Token 類別總表

| 類別 | Prefix | 範例 |
|------|--------|------|
| 顏色 | `color.*` | `color.brand.primary`, `color.status.pending`, `color.text.secondary` |
| 間距 | `space.*` | `space.4`, `space.sidebar`, `space.bottomnav` |
| 字型 | `text.*` | `text.body.md`, `text.heading.h1`, `text.kpi` |
| 圓角 | `radius.*` | `radius.md`, `radius.lg` |
| 陰影 | `shadow.*` | `shadow.sm`, `shadow.kanban`, `shadow.bottomsheet` |
| 邊框 | `border.*` | `border.width.default`, `border.width.status` |
| 動效 | `motion.*` | `motion.duration.fast`, `motion.ease.spring` |
| 佈局 | `layout.*` | `layout.admin.container.max-width`, `layout.tech.container.padding` |
| 斷點 | `breakpoint.*` | `breakpoint.admin.lg`, `breakpoint.tech.sm` |
| Z 軸 | `z.*` | `z.modal`, `z.kanban-drag`, `z.bottomsheet` |
| 圖標 | `icon.*` | `icon.lock.locked`, `icon.technician.available` |

---

## 11. Token Mode 管理

### 11.1 Mode 定義

| Mode 名稱 | 說明 | 切換方式 | 時程 |
|-----------|------|---------|------|
| `light` | 淺色模式（預設） | 系統預設 | V1.0 |
| `dark` | 深色模式（技師夜間作業） | `prefers-color-scheme` / 手動 toggle | V2.0 規劃 |
| `brand-yale` | Yale 品牌色皮膚 | 設定檔 / 租戶設定 | 白標未來規劃 |
| `brand-gateman` | Gateman 品牌色皮膚 | 設定檔 / 租戶設定 | 白標未來規劃 |
| `brand-samsung` | Samsung 品牌色皮膚 | 設定檔 / 租戶設定 | 白標未來規劃 |
| `high-contrast` | 高對比模式 | `prefers-contrast` | V2.0 規劃 |

### 11.2 Light / Dark Token 對照

```json
{
  "color.bg.page": {
    "light": "#F8FAFC",
    "dark": "#0F172A"
  },
  "color.bg.surface": {
    "light": "#FFFFFF",
    "dark": "#1E293B"
  },
  "color.bg.elevated": {
    "light": "#FFFFFF",
    "dark": "#334155"
  },
  "color.bg.sidebar": {
    "light": "#1E293B",
    "dark": "#0F172A"
  },
  "color.text.primary": {
    "light": "#0F172A",
    "dark": "#F1F5F9"
  },
  "color.text.secondary": {
    "light": "#64748B",
    "dark": "#94A3B8"
  },
  "color.text.disabled": {
    "light": "#94A3B8",
    "dark": "#475569"
  },
  "color.text.inverse": {
    "light": "#FFFFFF",
    "dark": "#0F172A"
  },
  "color.border.default": {
    "light": "#E2E8F0",
    "dark": "#334155"
  },
  "color.border.focus": {
    "light": "#2563EB",
    "dark": "#60A5FA"
  },
  "color.brand.primary": {
    "light": "#2563EB",
    "dark": "#3B82F6"
  },
  "color.brand.accent": {
    "light": "#F59E0B",
    "dark": "#FBBF24"
  },
  "color.status.pending": {
    "light": "#6366F1",
    "dark": "#818CF8"
  },
  "color.status.assigned": {
    "light": "#8B5CF6",
    "dark": "#A78BFA"
  },
  "color.status.active": {
    "light": "#3B82F6",
    "dark": "#60A5FA"
  },
  "color.status.warning": {
    "light": "#F59E0B",
    "dark": "#FBBF24"
  },
  "color.status.success": {
    "light": "#10B981",
    "dark": "#34D399"
  },
  "color.status.danger": {
    "light": "#EF4444",
    "dark": "#F87171"
  }
}
```

### 11.3 白標品牌覆蓋範圍

白標模式僅覆蓋以下 token，其餘繼承 light/dark mode：

```json
{
  "brand-yale": {
    "color.brand.primary": "#003DA5",
    "color.brand.primary.hover": "#002D7A",
    "color.brand.primary.active": "#001F54",
    "color.brand.primary.light": "#E6EDF7",
    "color.brand.accent": "#FFD700"
  },
  "brand-gateman": {
    "color.brand.primary": "#E31937",
    "color.brand.primary.hover": "#C21530",
    "color.brand.primary.active": "#A11128",
    "color.brand.primary.light": "#FDECEF",
    "color.brand.accent": "#1A1A1A"
  },
  "brand-samsung": {
    "color.brand.primary": "#1428A0",
    "color.brand.primary.hover": "#0F1F7A",
    "color.brand.primary.active": "#0B1654",
    "color.brand.primary.light": "#E8EAF6",
    "color.brand.accent": "#FF6F00"
  }
}
```

### 11.4 Figma 對應

```
Figma Variables → Collections:
  ├── Primitives（原始值：slate-50, slate-100, blue-500, indigo-500...）
  ├── Semantic-Light（語意對應：bg.page = slate-50, status.pending = indigo-500）
  ├── Semantic-Dark（語意對應：bg.page = slate-900, status.pending = indigo-400）
  ├── Brand-Yale（覆蓋 brand.primary = yale-blue）
  ├── Brand-Gateman（覆蓋 brand.primary = gateman-red）
  └── Component-Specific（元件專用：kanban.card.bg = bg.surface）

Figma Modes:
  - 每個 Variable Collection 可設定 Mode
  - Frame 上切換 Mode = 全部子元素自動切換
  - V1.0 僅需維護 Light mode
```

### 11.5 與工程的對應

| 設計端（Figma） | 工程端（CSS/Tailwind） | 同步方式 |
|----------------|----------------------|---------|
| Figma Variables | CSS Custom Properties (`--color-*`) | Token Studio / Style Dictionary |
| Figma Styles | `tailwind.config.ts` theme extend | 手動或 token pipeline |
| Figma Components | shadcn/ui React Components | Figma MCP / Code Connect |

```
同步流程：
  Figma Variables
    ↓ Token Studio plugin export
  tokens.json (W3C Design Token 格式)
    ↓ Style Dictionary transform
  ├── CSS variables (globals.css)
  ├── Tailwind config (tailwind.config.ts)
  └── TypeScript constants (design-tokens.ts)
    ↓ Git PR → Code Review → Merge
  工程端自動生效

技術堆疊映射：
  - Next.js 14 + React 19：CSR/SSR 均使用 CSS Variables
  - shadcn/ui：已內建 Tailwind + CSS Variables 整合
  - Tailwind 3.4：theme.extend 引用 CSS Variables
  - Dark Mode：Tailwind `dark:` prefix + CSS Variables 切換
```

---

## Figma 結構建議

```
📁 00_Foundations（Figma Page）
├── 📄 Grid & Layout
│   ├── Admin Grid 展示（Desktop / Tablet / Mobile）
│   ├── Admin Sidebar 展開/收合
│   ├── Tech PWA Grid 展示
│   ├── Tech PWA Bottom Nav + Safe Area
│   └── Layout Primitives 範例（Admin + Tech）
├── 📄 Colors
│   ├── Brand Colors（Primary Blue / Accent Amber / Secondary Slate）
│   ├── Work Order Status Colors（6 色系 × main/bg/text）
│   ├── 13 態工單狀態 → 色系對應表
│   ├── Semantic Colors（Success/Warning/Error/Info）
│   ├── Surface Colors
│   ├── Text Colors
│   ├── Border & SLA Colors
│   └── Dark Mode 對照（V2.0 preview）
├── 📄 Typography
│   ├── 字級階梯展示（含 KPI 數字）
│   ├── 中英混排範例（工單描述、技師資料）
│   ├── 工單編號 monospace 展示
│   └── RWD 字級對照（Admin only）
├── 📄 Spacing
│   ├── Spacing Scale 視覺化
│   ├── 平台專用 spacing（Sidebar / BottomNav / touch target）
│   └── 使用規則圖示
├── 📄 Borders & Radius
│   ├── 圓角階梯
│   └── Kanban 卡片 status stripe 範例
├── 📄 Shadows & Elevation
│   ├── Shadow 階梯
│   ├── Kanban drag shadow
│   ├── Bottom Sheet shadow
│   └── Z-Index 層級圖
├── 📄 Icons
│   ├── Lucide 常用 icon 展示
│   ├── 自定義 icon（Lock status / Battery / Connectivity / Technician status）
│   └── 使用規則
└── 📄 Motion
    ├── Duration & Easing 表
    ├── SLA Pulse 動畫（GIF）
    ├── Kanban Drag 動畫（GIF）
    ├── Bottom Sheet Slide 動畫（GIF）
    ├── Map Pin Pulse 動畫（GIF）
    └── Sidebar Toggle 動畫（GIF）
```

---

## 交付產出清單

| 文件 | 格式 | 給誰 | 說明 |
|------|------|------|------|
| Foundation Spec | Markdown（本文件） | 設計 + 工程 | 規格全文（Single Source of Truth） |
| Design Token Sheet | JSON (`tokens.json`) | 工程 | W3C Design Token 格式，可被 Style Dictionary 消費 |
| Figma Variables | Figma Library | 設計 | 可直接在設計檔中使用 |
| Tailwind Config | TypeScript (`tailwind.config.ts`) | 工程 | 對應 token 的 Tailwind 設定 |
| CSS Variables | CSS (`globals.css`) | 工程 | 全域 CSS Custom Properties |
| Token Change Log | Markdown | 全團隊 | token 變更紀錄 |

---

**版本**：v1.0
**最後更新**：2026-04-21
**平台**：Admin Panel (Next.js 14) / Technician PWA / LINE Bot
**技術堆疊**：Next.js 14 + React 19 + shadcn/ui + Tailwind 3.4 + TanStack Query + Zustand + Recharts + @vis.gl/react-google-maps + @dnd-kit/core
**相關文件**：`SYSTEM_DOCUMENT_SPEC.md` → B1 Design Tokens、`BASE_DESIGN_SYSTEM.md` → Visual Design System Layer
