# 01_Components — 電子鎖智能客服與派工平台 元件庫規格

> 頁面不是畫出來的，是裝出來的。
> 本文件定義平台三端點（Admin Panel、Technician PWA、LINE Bot）的完整元件庫。

---

## 目錄

1. [元件分級架構](#1-元件分級架構)
2. [元件規格卡模板](#2-元件規格卡模板)
3. [P0 標準元件清單與規格](#3-p0-標準元件清單與規格)
4. [P1 平台專屬元件](#4-p1-平台專屬元件)
5. [P2 元件清單](#5-p2-元件清單)
6. [元件命名規範](#6-元件命名規範)
7. [元件 Inventory 總表](#7-元件-inventory-總表)
8. [Do / Don't 範例](#8-do--dont-範例)

---

## 1. 元件分級架構

採用 Atomic Design 分層，搭配 shadcn/ui 元件基礎擴充平台專屬元件。

```
Atoms（原子）
  最小不可分割的 UI 單位
  基礎：Button, Input, Badge, Avatar, Icon, Tag, Checkbox, Radio, Switch, Divider
  平台：StatusBadge, SLACountdown, AIRecommendationBadge, SkillBadge

Molecules（分子）
  2-3 個 Atom 組合而成的功能單位
  基礎：Search Bar, Form Field, Menu Item, Stat Card
  平台：KPICard, DeviceStatusCard, WorkOrderCard, SignaturePad, PhotoGallery

Organisms（有機體）
  多個 Molecules 組成的完整區塊
  基礎：Navigation Bar, Data Table, Form Section, Card Grid
  平台：KanbanBoard, MapView, BottomSheet, WorkTimeline,
        DeviceStatusPanel, CompletionReportForm

Templates（模板）
  → 歸入 03_Templates
```

---

## 2. 元件規格卡模板

每個元件都必須有一張「規格卡」，格式如下：

```markdown
### [元件名稱] Component Spec

#### Purpose（用途）
一句話說明這個元件「什麼時候用」。

#### Anatomy（結構）
列出元件的所有組成部分。

#### Props（可配置項）
| Prop | Type | Default | Options | 說明 |

#### States（狀態矩陣）
| State | 視覺變化 | 觸發方式 |

#### Interaction（互動規則）
鍵盤、動效、回饋說明。

#### Accessibility
ARIA 角色、標籤、焦點管理。

#### Do / Don't
✅ 正確用法 / ❌ 錯誤用法
```

---

## 3. P0 標準元件清單與規格

### 3.1 Button（按鈕）

#### Purpose（用途）
觸發操作的主要互動元件。平台新增 CTA（琥珀色）變體，用於強調行動呼籲（如「立即派工」「接受工單」）。

#### Anatomy（結構）
- [ ] Root container（`<button>` 或 `<a>`）
- [ ] Leading element（icon，如 `lucide-react` 圖示）
- [ ] Content（label 文字）
- [ ] Trailing element（icon / badge / spinner）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| variant | enum | primary | `primary` / `cta` / `secondary` / `ghost` / `danger` / `link` | 視覺變體 |
| size | enum | md | `sm` / `md` / `lg` | 尺寸 |
| disabled | boolean | false | — | 停用狀態 |
| loading | boolean | false | — | 載入狀態 |
| fullWidth | boolean | false | — | 是否撐滿容器（Tech PWA 常用） |
| leftIcon | ReactNode | — | — | 左側圖示 |
| rightIcon | ReactNode | — | — | 右側圖示 |

**Variant 色彩對應**：

| Variant | 背景色 | 文字色 | Hover 背景 | 用途 |
|---------|--------|--------|-----------|------|
| primary | `#2563EB` (Blue-600) | `#FFFFFF` | `#1D4ED8` (Blue-700) | 主要操作（儲存、送出） |
| cta | `#F59E0B` (Amber-500) | `#FFFFFF` | `#D97706` (Amber-600) | 行動呼籲（派工、接受、開始服務） |
| secondary | `#1E293B` (Slate-800) | `#FFFFFF` | `#0F172A` (Slate-900) | 次要操作（取消、返回） |
| ghost | transparent | `#1E293B` | `#F1F5F9` (Slate-100) | 低優先操作 |
| danger | `#EF4444` (Red-500) | `#FFFFFF` | `#DC2626` (Red-600) | 破壞性操作（刪除、取消工單） |
| link | transparent | `#2563EB` | underline | 連結型按鈕 |

**尺寸規格**：

| Size | 高度 | Padding | Font | 適用場景 |
|------|------|---------|------|---------|
| sm | 32px | `px-3 py-1.5` | 14px / 500 | 表格行內、緊湊列表 |
| md | 36px | `px-4 py-2` | 14px / 500 | 預設、表單按鈕 |
| lg | 44px | `px-5 py-2.5` | 16px / 600 | Tech PWA 主操作（觸控友善） |

- Radius：`radius.md`（6px）
- Min Width：64px
- Loading：Spinner 替換 leading icon，文字保留，disabled interaction

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 基準樣式 | 初始 |
| Hover | 背景加深一階（見上表） | 滑鼠移入 |
| Active/Pressed | 背景再加深 + `scale(0.98)` | 滑鼠按下 |
| Focus | `ring-2 ring-offset-2 ring-blue-500` | Tab 鍵 |
| Disabled | `opacity-50` + `cursor-not-allowed` | `disabled=true` |
| Loading | Spinner 取代 leading icon + `pointer-events-none` | `loading=true` |

#### Interaction（互動規則）
- 鍵盤：`Enter` / `Space` 觸發點擊
- 動效：hover `transition-colors duration-150 ease-in-out`
- 回饋：active 時 `scale(0.98)` transform，150ms
- Tech PWA：lg size 預設，觸控區域至少 44x44px

#### Accessibility
- Role: `button`
- `aria-label`：icon-only 按鈕必須提供
- `aria-disabled`：disabled 時設定
- `aria-busy`：loading 時設定為 `true`
- Focus visible：必須有 focus ring，且不被 overflow hidden 裁切

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 一頁最多一個 Primary CTA + 一個 CTA variant | 同時出現多個 CTA 琥珀色按鈕搶注意力 |
| 按鈕文案用動詞開頭：「派工」「接受工單」「開始服務」 | 模糊文案：「確定」「提交」 |
| Danger 操作用 Danger variant + 確認 Dialog | 用 Primary 或 CTA variant 做刪除 |
| Loading 時 disable + spinner，防止重複提交 | Loading 時什麼都不顯示，用戶連點 |
| Tech PWA 統一使用 lg size | Tech PWA 用 sm size（太小難點） |
| CTA variant 用於需要立即行動的場景 | CTA variant 用於一般瀏覽操作 |

---

### 3.2 Input（輸入框）

#### Purpose（用途）
接收用戶文字輸入的基礎表單元件。平台場景：工單搜尋、客戶資料填寫、報修描述、零件數量輸入。

#### Anatomy（結構）
- [ ] Label（必要，永遠可見）
- [ ] Input Container（包含前綴/後綴）
- [ ] Prefix（icon 或文字，如搜尋圖示、「$」符號）
- [ ] Suffix（icon 或動作，如清除、密碼顯示）
- [ ] Helper Text / Error Message
- [ ] Character Count（可選）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| type | enum | text | `text` / `password` / `email` / `number` / `search` / `tel` / `textarea` | 輸入類型 |
| size | enum | md | `sm` / `md` / `lg` | 尺寸 |
| state | enum | default | `default` / `error` / `disabled` / `readonly` | 狀態 |
| label | string | — | — | 標籤文字 |
| placeholder | string | — | — | 佔位提示 |
| helperText | string | — | — | 輔助說明 |
| errorMessage | string | — | — | 錯誤訊息 |
| required | boolean | false | — | 是否必填 |
| prefix | ReactNode | — | — | 前綴 |
| suffix | ReactNode | — | — | 後綴 |
| maxLength | number | — | — | 最大字數 |

**尺寸規格**：

| Size | 高度 | Padding | 適用場景 |
|------|------|---------|---------|
| sm | 32px | `px-3 py-1.5` | 表格行內篩選 |
| md | 36px | `px-3 py-2` | 預設表單 |
| lg | 44px | `px-4 py-2.5` | Tech PWA（觸控友善） |

- Radius：`radius.md`（6px）
- Border：default `#CBD5E1`（Slate-300）/ focus `#2563EB`（2px）/ error `#EF4444`
- Placeholder 色：`#94A3B8`（Slate-400）

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | `border-slate-300` | 初始 |
| Hover | `border-slate-400` | 滑鼠移入 |
| Focus | `border-blue-600 ring-2 ring-blue-100` | 點擊或 Tab |
| Error | `border-red-500 ring-2 ring-red-100` + 紅色錯誤訊息 | 驗證失敗 |
| Disabled | `bg-slate-50 opacity-50 cursor-not-allowed` | `disabled=true` |
| Readonly | `bg-slate-50` 無邊框互動 | `readonly=true` |

#### Interaction（互動規則）
- 點擊 Label 可聚焦 Input（`htmlFor` 綁定）
- Textarea 支援自動高度調整（`rows` 最小 3）
- Search type：300ms debounce，右側 X 清除
- Number type：支援上下箭頭微調

#### Accessibility
- `<label>` 與 `<input>` 透過 `htmlFor` / `id` 綁定
- `aria-required`：必填時設定
- `aria-invalid`：error 時設定為 `true`
- `aria-describedby`：指向 helper text 或 error message
- Error message 使用 `role="alert"`

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| Label 在上方，永遠可見 | Label 只放在 placeholder 裡 |
| Error 顯示在 Input 下方 + 紅色邊框 | 只用 toast 顯示表單錯誤 |
| 必填欄位用 `*` 標示 | 所有欄位都不標示必填 |
| 報修描述欄位用 textarea + 字數統計 | 用 text input 填寫長描述 |
| 電話欄位設 `type="tel"` 方便手機鍵盤 | 電話用 `type="text"` |

---

### 3.3 Select（選擇器）

#### Purpose（用途）
從預定義選項中選取值。平台場景：選擇品牌/型號、指派技師、選擇工單狀態、篩選鎖具類型。

#### Anatomy（結構）
- [ ] Label
- [ ] Trigger（顯示已選值 + 下拉箭頭）
- [ ] Dropdown Container（shadow + scroll）
- [ ] Option Item（text / icon+text / group header）
- [ ] Search Input（combobox 模式）
- [ ] Selected Indicator（checkmark）
- [ ] Helper Text / Error Message

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| type | enum | single | `single` / `multi` / `combobox` | 選擇模式 |
| size | enum | md | `sm` / `md` / `lg` | 尺寸 |
| options | Option[] | [] | — | 選項資料 |
| value | string / string[] | — | — | 已選值 |
| placeholder | string | 「請選擇」 | — | 佔位提示 |
| searchable | boolean | false | — | 是否可搜尋 |
| grouped | boolean | false | — | 是否分組顯示 |
| disabled | boolean | false | — | 停用 |
| error | boolean | false | — | 錯誤狀態 |
| maxSelections | number | — | — | 多選上限 |

**平台專用選項分組範例**：
```
品牌型號選擇器：
  ── Yale ──
  YDD-424
  YDM-4109
  ── Gateman ──
  GRAB-200
  WF-20
  ── Samsung ──
  SHP-DP609
```

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | `border-slate-300` | 初始 |
| Hover | `border-slate-400` | 滑鼠移入 |
| Focus/Open | `border-blue-600 ring-2 ring-blue-100` + dropdown 展開 | 點擊或 Tab+Enter |
| Error | `border-red-500` | 驗證失敗 |
| Disabled | `opacity-50 cursor-not-allowed` | `disabled=true` |
| Empty | dropdown 顯示「無選項」 | 選項為空 |
| No Result | 「無搜尋結果」（combobox） | 搜尋無匹配 |

- Dropdown：`shadow-lg`、`radius-lg`（8px）、max-height 240px、overflow scroll
- 選項 hover：`bg-slate-100`
- 已選項：右側 checkmark icon（`text-blue-600`）

#### Interaction（互動規則）
- Arrow ↑↓ 導航選項
- Enter 選取、Esc 關閉
- 多選模式：已選項顯示為 Tag，可個別移除
- Combobox：輸入即篩選，300ms debounce

#### Accessibility
- Trigger：`role="combobox"`、`aria-expanded`、`aria-haspopup="listbox"`
- Dropdown：`role="listbox"`
- Option：`role="option"`、`aria-selected`
- 鍵盤完整可操作

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 品牌/型號用分組 Select | 200+ 選項不加搜尋功能 |
| 技師選擇用 combobox（可搜尋名字） | 強迫用戶滾動長列表找技師 |
| 多選顯示已選數量「已選 3 項」 | 多選超過容器寬度不處理 |
| 選項超過 10 個啟用搜尋 | 短列表（3-5 項）也強制搜尋 |

---

### 3.4 Card（卡片）

#### Purpose（用途）
資訊分組容器。平台擴充 4 種專屬變體：KPICard、WorkOrderCard、KanbanCard、DeviceStatusCard。

#### Anatomy（結構）
- [ ] Root container
- [ ] Header（Title + Subtitle + Action）
- [ ] Body（主要內容）
- [ ] Footer（操作按鈕或後設資訊）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| variant | enum | default | `default` / `outlined` / `elevated` / `clickable` / `kpi` / `workorder` / `kanban` / `device` | 變體 |
| padding | enum | md | `sm` (12px) / `md` (16px) / `lg` (24px) | 內距 |
| draggable | boolean | false | — | 是否可拖曳（kanban） |
| selected | boolean | false | — | 是否選中 |
| slaStatus | enum | — | `green` / `amber` / `red` / `black` | SLA 狀態（workorder/kanban） |

**基礎卡片規格**：
- Radius：`radius.lg`（8px）
- Shadow：default `shadow-sm` / hover (clickable) `shadow-md`
- Border：outlined `border-slate-200`

**KPICard 變體**：
```
┌─────────────────────────┐
│ 📊 待指派工單             │  ← 標題 14px Slate-500
│                         │
│ 42                      │  ← 數值 36px/700 Slate-900
│ ▲ 12% vs 上週           │  ← 趨勢 12px Green-600 或 Red-600
└─────────────────────────┘
```
- 數值字體：36px / font-weight 700 / `text-slate-900`
- 趨勢箭頭：上升 `▲ text-green-600`、下降 `▼ text-red-600`、持平 `─ text-slate-400`
- Padding：`p-6`（24px）

**WorkOrderCard 變體**：
```
┌─────────────────────────────────┐
│ WO-2026-0421  ┆ ● 進行中        │  ← 工單號 + StatusBadge
│ 陳先生 - 台北市信義區...         │  ← 客戶 + 地址（truncate）
│ Yale YDD-424 / 指紋辨識異常     │  ← 鎖具品牌型號 + 問題摘要
│ 🕐 剩餘 02:30  │  👤 王技師      │  ← SLACountdown + 技師
│ ▓▓▓▓▓▓▓░░░ SLA 70%            │  ← SLA 進度條
└─────────────────────────────────┘
```
- 左邊框色帶：4px，顏色依 SLA 狀態（green/amber/red/black）
- Padding：`p-4`（16px）

**KanbanCard 變體**：
```
┌─────────────────────────┐
│ WO-2026-0421            │  ← 工單號 14px/600
│ 陳先生                   │  ← 客戶名 14px/400
│ Yale YDD-424            │  ← 鎖具型號 12px Slate-500
│ ● 進行中  🕐 02:30      │  ← StatusBadge + SLA
└─────────────────────────┘
```
- 拖曳中：`shadow-kanban`（`0 8px 24px rgba(0,0,0,0.15)`）+ `scale(1.02)` + `rotate(2deg)`
- 拖曳 placeholder：虛線邊框 `border-2 border-dashed border-slate-300`
- Compact padding：`p-3`（12px）

**DeviceStatusCard 變體**：
```
┌─────────────────────────────────┐
│ 🔒 Yale YDD-424                │  ← 鎖具圖示 + 型號
│ ┌────────┐┌────────┐┌────────┐ │
│ │🔋 87%  ││📶 正常  ││🕐 2分前 ││  ← 電量/連線/最後操作
│ └────────┘└────────┘└────────┘ │
│ [遠端開鎖]  [重設密碼]          │  ← 操作按鈕
└─────────────────────────────────┘
```

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 基準樣式 | 初始 |
| Hover（clickable） | `shadow-md` + `cursor-pointer` | 滑鼠移入 |
| Selected | `ring-2 ring-blue-500` | 點選 |
| Dragging（kanban） | `shadow-kanban` + `scale(1.02)` + `opacity-90` | 拖曳開始 |
| SLA Green | 左邊框 `border-l-green-500` | SLA > 50% |
| SLA Amber | 左邊框 `border-l-amber-500` + 脈動動效 | SLA 20-50% |
| SLA Red | 左邊框 `border-l-red-500` | SLA < 20% |
| SLA Black | 左邊框 `border-l-slate-900` + 閃爍 | SLA 逾時 |

#### Interaction（互動規則）
- Clickable Card：整張可點擊，導向工單詳情
- KanbanCard：`@dnd-kit/core` 拖曳，touch 長按 300ms 啟動
- WorkOrderCard：右鍵 → context menu（查看/編輯/指派/取消）
- DeviceStatusCard：操作按鈕需確認 Dialog（遠端開鎖為高危操作）

#### Accessibility
- Clickable：`role="link"` 或 `<a>` 包裹，`tabindex="0"`
- KanbanCard：`role="listitem"`、`aria-grabbed`、`aria-roledescription="draggable item"`
- SLA 狀態：不僅靠顏色，同時有文字標示
- Screen reader：朗讀工單號 + 狀態 + SLA 剩餘時間

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| KPI 數值用 36px 粗體 + 趨勢箭頭 | KPI 數值跟文字一樣大 |
| WorkOrderCard 左邊框色帶表示 SLA 狀態 | 只用背景色區分 SLA |
| KanbanCard 拖曳時有明顯視覺回饋 | 拖曳時卡片沒有任何變化 |
| DeviceStatusCard 操作按鈕加確認 Dialog | 遠端開鎖一鍵直接執行 |

---

### 3.5 Modal / Dialog（模態框）

#### Purpose（用途）
打斷用戶流程，要求確認或輸入。平台場景：派工確認、取消工單確認、工單範圍變更表單、SLA 逾時警告。

#### Anatomy（結構）
- [ ] Overlay（`bg-black/50`）
- [ ] Container（白底、圓角、陰影）
- [ ] Header（Title + Close X）
- [ ] Body（內容區、可捲動）
- [ ] Footer（Action Buttons）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| variant | enum | default | `default` / `destructive` / `form` / `confirmation` | 變體 |
| size | enum | md | `sm`(400px) / `md`(520px) / `lg`(640px) / `xl`(800px) / `full` | 尺寸 |
| title | string | — | — | 標題 |
| closable | boolean | true | — | 是否可透過 X / Esc / Overlay 關閉 |
| preventOverlayClose | boolean | false | — | 是否禁止 Overlay 點擊關閉 |

**平台專用 Modal 規格**：

| 場景 | Variant | Size | 特殊規則 |
|------|---------|------|---------|
| 派工確認 | confirmation | sm | 顯示技師資訊 + AI 推薦理由 + SLA 倒計時 |
| 取消工單 | destructive | sm | 必須選擇取消原因 + 輸入備註 |
| 工單範圍變更 | form | md | 多欄位表單 + 費用試算 |
| SLA 逾時警告 | default | sm | 紅色標題列 + 逾時時間 + 建議動作 |
| 技師排程衝突 | default | lg | 甘特圖顯示衝突時段 |

- Radius：`radius.xl`（12px）
- 動畫：`scale(0.95) → scale(1)` + `opacity(0→1)`，200ms `ease-out`
- Focus Trap：開啟後 focus 鎖在 Modal 內
- Mobile（< 640px）：轉為 bottom sheet（從底部滑入，高度 90vh）

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Opening | scale + opacity 動畫 | 觸發開啟 |
| Open | 正常顯示 | 動畫完成 |
| Closing | 反向動畫 | 觸發關閉 |
| Submitting | Footer 按鈕 loading | 表單送出中 |

#### Interaction（互動規則）
- 關閉方式：X 按鈕、Esc 鍵、Overlay 點擊（destructive 除外）
- Body 可 scroll，Header/Footer 固定
- destructive variant：確認按鈕用 Danger variant，且 `preventOverlayClose=true`
- 表單 Modal：離開未儲存時提醒

#### Accessibility
- `role="dialog"`、`aria-modal="true"`
- `aria-labelledby` 指向標題
- 開啟時 focus 移至第一個可互動元素
- 關閉時 focus 回到觸發元素
- 內容可用 Tab 導航，不會跳出 Modal

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| Modal 只做一件事 | Modal 裡塞完整的工單編輯 + 子 Modal |
| 破壞性操作（取消工單）要二次確認 + Danger variant | 取消工單一鍵直接執行 |
| Mobile 轉 bottom sheet | Mobile 還用小 Modal |
| 確認按鈕文案要具體：「確定取消工單」 | 只寫「確定」 |
| 派工確認 Modal 顯示 AI 推薦理由 | 只顯示技師名字沒有脈絡 |

---

### 3.6 Toast / Notification（提示通知）

#### Purpose（用途）
非阻斷式操作回饋。平台場景：派工成功、狀態更新、SLA 即將逾時警告、WebSocket 即時推播。

#### Anatomy（結構）
- [ ] Icon（variant 對應圖示）
- [ ] Message（主要文字）
- [ ] Description（可選，補充說明）
- [ ] Action Button（可選，如「撤銷」「查看」）
- [ ] Close Button（X）
- [ ] Progress Bar（自動消失倒數）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| variant | enum | info | `success` / `warning` / `error` / `info` / `dispatch` | 變體 |
| title | string | — | — | 標題 |
| description | string | — | — | 描述 |
| duration | number | 5000 | — | 自動消失毫秒 |
| action | Action | — | — | 操作按鈕 |
| persistent | boolean | false | — | 是否不自動消失 |

**Variant 色彩與圖示**：

| Variant | Icon | 色彩 | Duration | 場景 |
|---------|------|------|----------|------|
| success | `CheckCircle` | `#10B981` Green-500 | 5s | 派工成功、工單完成 |
| warning | `AlertTriangle` | `#F59E0B` Amber-500 | 8s | SLA 即將逾時、排程衝突 |
| error | `XCircle` | `#EF4444` Red-500 | 不自動消失 | 派工失敗、API 錯誤 |
| info | `Info` | `#3B82F6` Blue-500 | 5s | 狀態更新、一般通知 |
| dispatch | `Truck` | `#6366F1` Indigo-500 | 8s | 新工單指派通知（WebSocket） |

- 位置：右上角（Admin Desktop）/ 頂部居中（Tech PWA）
- Width：min 320px / max 420px
- 動畫：slide-in from right（Desktop）/ slide-down（Mobile），300ms
- 堆疊：最多 3 個，新的推舊的向下
- Tech PWA dispatch variant：可帶震動回饋（`navigator.vibrate`）

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Entering | slide-in + fade | 觸發 |
| Visible | 正常顯示 + progress bar 倒數 | 動畫完成 |
| Paused | progress bar 暫停 | hover |
| Exiting | slide-out + fade | duration 到期或手動關閉 |

#### Interaction（互動規則）
- Hover 暫停自動消失計時器
- 可向右 swipe 關閉（Tech PWA）
- Action button 點擊後 toast 消失
- 堆疊超過 3 個時，最舊的被推走

#### Accessibility
- `role="alert"`、`aria-live="polite"`（info/success）、`aria-live="assertive"`（error/warning）
- Close button：`aria-label="關閉通知"`
- 不應該是唯一的錯誤回饋方式（表單錯誤仍需 inline error）

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 派工成功：「已成功指派 WO-2026-0421 給王技師」 | 「操作成功」（太模糊） |
| Error toast 不自動消失 + 提供重試 | Error 5 秒後消失，用戶沒看到 |
| WebSocket 推播新工單用 dispatch variant + 震動 | 新工單通知靜悄悄沒有提示 |
| 帶 Action button：「查看工單」 | 通知沒有後續行動入口 |

---

### 3.7 Table（資料表格）

#### Purpose（用途）
展示結構化資料列表。平台核心場景：工單列表（13 狀態篩選 + SLA 欄 + 批次指派）。

#### Anatomy（結構）
- [ ] Toolbar（Title + Search + Filter + Actions）
- [ ] Header Row（固定 sticky、可排序）
- [ ] Body Rows（hover 高亮、可選取）
- [ ] Cell Types（text / number / StatusBadge / Avatar / Action / SLA）
- [ ] Pagination Bar
- [ ] Bulk Action Bar（選取時浮出）
- [ ] Empty / Loading / Error State

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| variant | enum | default | `default` / `sortable` / `selectable` / `expandable` | 變體 |
| columns | Column[] | — | — | 欄位定義 |
| data | Row[] | — | — | 資料 |
| loading | boolean | false | — | 載入中 |
| pagination | PaginationConfig | — | — | 分頁設定 |
| selectable | boolean | false | — | 是否可選取 |
| onSort | function | — | — | 排序回呼 |
| stickyHeader | boolean | true | — | 表頭固定 |

**工單列表專用欄位**：

| 欄位 | 寬度 | 類型 | 排序 | 說明 |
|------|------|------|------|------|
| ☐ | 40px | checkbox | — | 批次選取 |
| 工單號 | 140px | text link | asc/desc | 點擊導向詳情 |
| 客戶 | 160px | avatar+text | a-z | 客戶名稱 |
| 鎖具型號 | 140px | text | a-z | 品牌+型號 |
| 問題分類 | 120px | tag | — | 安裝/維修/保養 |
| 狀態 | 120px | StatusBadge | — | 13 狀態 |
| SLA | 100px | SLACountdown | — | 倒計時/逾時 |
| 指派技師 | 140px | avatar+text | — | 技師名或「未指派」 |
| 建立時間 | 120px | datetime | asc/desc | 格式 MM/DD HH:mm |
| 操作 | 80px | action buttons | — | ⋮ more menu |

- Header：`bg-slate-50`、`text-slate-600`、`font-weight-600`、`text-xs uppercase`
- Row：高度 48px、hover `bg-slate-50`
- Selected row：`bg-blue-50`
- 數字右對齊、文字左對齊
- Mobile（< 768px）：轉為 WorkOrderCard List

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Loading | 5 行 skeleton rows | `loading=true` |
| Empty | 插圖 +「目前沒有工單」+ [建立工單] CTA | 資料為空 |
| No Result | 「找不到符合條件的工單」+ [清除篩選] | 篩選無結果 |
| Error | 「載入失敗」+ [重試] | API 錯誤 |
| Bulk Selected | 頂部浮出 action bar：「已選 N 項 — [批次指派] [匯出]」 | 勾選 checkbox |

#### Interaction（互動規則）
- 排序：點擊 header 切換 asc → desc → none
- 篩選：狀態 multi-select dropdown（13 狀態可複選）
- 搜尋：toolbar search，300ms debounce
- 選取：Checkbox + Shift 多選
- Row click：導向工單詳情頁
- Row action（⋮）：查看 / 編輯 / 指派 / 取消（Danger）
- 批次指派：選取多筆 → 頂部 action bar → 「批次指派」Dialog
- 分頁：每頁 10/25/50/100，底部分頁器

#### Accessibility
- `<table>` + `<thead>` + `<tbody>` 語義化結構
- 可排序欄：`aria-sort="ascending"` / `"descending"` / `"none"`
- 選取：checkbox 有 `aria-label="選取工單 WO-2026-0421"`
- 分頁：`nav` + `aria-label="分頁"`

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| SLA 欄位用 SLACountdown 元件，不只顯示文字 | SLA 只顯示「2 小時」文字 |
| 狀態欄用 StatusBadge（帶色點 + 文字） | 狀態只用顏色不帶文字 |
| Mobile 轉 WorkOrderCard List | Mobile 還用橫向表格 |
| 批次指派後顯示成功/失敗摘要 | 批次操作無回饋 |
| 篩選條件反映在 URL query string | 篩選後重整頁面遺失條件 |

---

### 3.8 StatusBadge（狀態徽章）— 平台專屬元件

#### Purpose（用途）
以統一的色彩系統顯示工單的 13 種狀態。必須同時包含色點 + 文字標籤，不可僅靠顏色區分。

#### Anatomy（結構）
- [ ] Colored Dot（8px 圓形）
- [ ] Text Label（狀態名稱）
- [ ] Countdown Timer（可選，SLA 倒計時）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| status | enum | — | 13 種工單狀態（見下表） | 工單狀態 |
| size | enum | md | `sm` / `md` | 尺寸 |
| showCountdown | boolean | false | — | 是否顯示 SLA 倒計時 |
| countdown | string | — | — | 倒計時文字（如「02:30」） |

**13 狀態 → 6 色群對應表**：

| 狀態 (status) | 中文標籤 | 色群 | Dot 色 | 背景色 | 文字色 |
|--------------|---------|------|--------|--------|--------|
| `created` | 已建立 | Pending | `#6366F1` Indigo-500 | `#EEF2FF` Indigo-50 | `#4338CA` Indigo-700 |
| `assigned` | 已指派 | Assigned | `#8B5CF6` Violet-500 | `#F5F3FF` Violet-50 | `#6D28D9` Violet-700 |
| `accepted` | 已接受 | Active | `#3B82F6` Blue-500 | `#EFF6FF` Blue-50 | `#1D4ED8` Blue-700 |
| `in_progress` | 進行中 | Active | `#3B82F6` Blue-500 | `#EFF6FF` Blue-50 | `#1D4ED8` Blue-700 |
| `scope_changed` | 範圍變更 | Warning | `#F59E0B` Amber-500 | `#FFFBEB` Amber-50 | `#B45309` Amber-700 |
| `material_pending` | 待料中 | Warning | `#F59E0B` Amber-500 | `#FFFBEB` Amber-50 | `#B45309` Amber-700 |
| `delayed` | 延遲 | Warning | `#F59E0B` Amber-500 | `#FFFBEB` Amber-50 | `#B45309` Amber-700 |
| `completed` | 已完工 | Success | `#10B981` Emerald-500 | `#ECFDF5` Emerald-50 | `#047857` Emerald-700 |
| `confirmed` | 已確認 | Success | `#10B981` Emerald-500 | `#ECFDF5` Emerald-50 | `#047857` Emerald-700 |
| `archived` | 已歸檔 | Success | `#10B981` Emerald-500 | `#ECFDF5` Emerald-50 | `#047857` Emerald-700 |
| `rework_required` | 需返工 | Danger | `#EF4444` Red-500 | `#FEF2F2` Red-50 | `#B91C1C` Red-700 |
| `cancelled` | 已取消 | Danger | `#EF4444` Red-500 | `#FEF2F2` Red-50 | `#B91C1C` Red-700 |
| `disputed` | 爭議中 | Danger | `#EF4444` Red-500 | `#FEF2F2` Red-50 | `#B91C1C` Red-700 |

**尺寸規格**：

| Size | Dot | Font | Padding | 高度 |
|------|-----|------|---------|------|
| sm | 6px | 12px / 500 | `px-2 py-0.5` | 22px |
| md | 8px | 14px / 500 | `px-2.5 py-1` | 28px |

- Radius：`radius-full`（pill shape）
- Dot 與文字間距：`gap-1.5`（6px）
- Countdown 附加：分隔符 `│` + 倒計時文字

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 基準樣式（見上表） | 初始 |
| With Countdown | 右側附加 `│ 02:30` | `showCountdown=true` |
| Overdue | Dot 閃爍動畫 + 文字「逾時」 | SLA 已逾時 |

#### Interaction（互動規則）
- 純展示元件，不可點擊
- 用在：Table cell、Card 內、Detail page header、Kanban card
- Tooltip（hover）：可顯示狀態轉換時間

#### Accessibility
- `role="status"`
- `aria-label`：「工單狀態：進行中」
- 不僅靠顏色區分（dot + 文字 + 背景色三重指示）

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 永遠同時顯示色點 + 文字標籤 | 只用色點不帶文字 |
| 使用規定的 6 色群對應 | 自行新增顏色 |
| 逾時狀態加閃爍動畫強調 | 逾時跟正常狀態看起來一樣 |
| Badge 內文字用中文標籤 | 顯示英文 status code（如 `in_progress`） |

---

### 3.9 Avatar（頭像）

#### Purpose（用途）
顯示用戶（技師、客戶、管理員）身份的視覺代表。

#### Anatomy（結構）
- [ ] Container（圓形）
- [ ] Image / Initial / Fallback Icon
- [ ] Status Indicator（右下角，可選）
- [ ] Badge（右上角，可選，如工單數）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| type | enum | image | `image` / `initial` / `icon` | 顯示類型 |
| size | enum | md | `xs`(24px) / `sm`(32px) / `md`(40px) / `lg`(48px) / `xl`(64px) | 尺寸 |
| src | string | — | — | 圖片 URL |
| name | string | — | — | 用戶姓名（用於 initial） |
| status | enum | — | `online` / `offline` / `busy` / `on-duty` | 狀態指示器 |
| count | number | — | — | 右上角數量徽章 |

**Status 指示器色彩**：

| Status | 色彩 | 說明 |
|--------|------|------|
| online | `#10B981` Green-500 | 上線 |
| offline | `#94A3B8` Slate-400 | 離線 |
| busy | `#EF4444` Red-500 | 忙碌（服務中） |
| on-duty | `#3B82F6` Blue-500 | 值班中 |

- Shape：Circle（`radius-full`）
- Fallback 優先序：圖片 → 姓名首字（背景色由名字 hash 決定）→ User icon
- Avatar Stack：重疊 `-8px`，最多 5 個 + `+N`

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 基準樣式 | 初始 |
| Loading | 灰色 pulse 動畫 | 圖片載入中 |
| Error | Fallback（initial 或 icon） | 圖片載入失敗 |

#### Interaction（互動規則）
- 可包在 Tooltip 中，hover 顯示完整姓名
- 點擊可導向技師 Profile（Admin Panel）
- Avatar Stack hover 展開顯示完整列表

#### Accessibility
- `alt` 屬性：技師/客戶姓名
- Status indicator：`aria-label="狀態：值班中"`
- 不可只依賴 status 色彩

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 技師 Avatar 加 status 指示器 | 看不出技師目前狀態 |
| Fallback 用姓名首字（中文取第一字） | Fallback 全部用同一個灰色 icon |
| Avatar Stack 超過 5 個顯示 +N | 堆疊 20 個擠成一團 |

---

### 3.10 Tabs（分頁）

#### Purpose（用途）
在同一頁面中切換不同內容區塊。平台場景：工單詳情頁（基本資訊/服務紀錄/零件/照片/時間軸）。

#### Anatomy（結構）
- [ ] Tab List（水平排列）
- [ ] Tab Item（icon + text + badge count）
- [ ] Active Indicator（底線或背景）
- [ ] Tab Panel（內容區）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| variant | enum | underline | `underline` / `pill` / `outlined` | 變體 |
| size | enum | md | `sm` / `md` | 尺寸 |
| items | TabItem[] | — | — | 分頁項目 |
| defaultValue | string | — | — | 預設 active tab |
| onChange | function | — | — | 切換回呼 |

**平台專用 Tab 配置**：

| 頁面 | Tabs | Variant |
|------|------|---------|
| 工單詳情 | 基本資訊 / 服務紀錄 / 零件 / 照片 / 時間軸 | underline |
| 技師 Profile | 個人資料 / 技能認證 / 排程 / 績效 | underline |
| Dashboard | 總覽 / 即時地圖 / 異常工單 | pill |
| 設定頁 | 一般 / 通知 / 整合 / 團隊 | outlined |

- Indicator 動畫：underline `width + translateX` 滑動，200ms ease
- Tab Badge：未讀數或項目數，`bg-red-500 text-white` 圓形
- Overflow：超過容器寬度時顯示左右箭頭 scroll
- 鍵盤：Arrow ← → 切換、Home/End 跳首尾

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | `text-slate-600` | 初始 |
| Hover | `text-slate-900` | 滑鼠移入 |
| Active | `text-blue-600` + indicator | 點擊 |
| Disabled | `text-slate-300 cursor-not-allowed` | `disabled=true` |
| With Badge | 右上角紅色 badge | 有未讀/數量 |

#### Interaction（互動規則）
- URL 同步：每個 tab 對應 URL hash（`#info`、`#timeline`）
- Tab Panel 載入：lazy load（切換到才載入）
- Mobile：可水平 scroll 或轉為 Select dropdown

#### Accessibility
- `role="tablist"` + `role="tab"` + `role="tabpanel"`
- `aria-selected`：active tab
- `aria-controls`：tab 指向 panel
- `tabindex`：active tab = 0，其餘 = -1

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| Tab 數量 2-6 個 | 超過 8 個 tab 擠在一起 |
| 工單詳情用 underline tab | 混用不同 variant |
| 每個 tab 對應 URL hash | Tab 切換不更新 URL（使用者無法分享特定 tab） |
| Badge 數量有意義（未讀、異常數） | 每個 tab 都加 badge |

---

## 4. P1 平台專屬元件

### 4.1 SLACountdown（SLA 倒計時）

#### Purpose（用途）
即時顯示工單 SLA 剩餘或逾時時間，以交通燈色彩系統傳達緊迫程度。

#### Anatomy（結構）
- [ ] Container（圓角 pill）
- [ ] Clock Icon（`lucide-react/Clock`）
- [ ] Time Text（「剩餘 HH:mm」或「逾時 HH:mm」）
- [ ] Pulse Border（amber/red 狀態時）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| deadline | Date | — | — | SLA 截止時間 |
| totalDuration | number | — | — | SLA 總時長（分鐘） |
| size | enum | md | `sm` / `md` / `lg` | 尺寸 |
| showIcon | boolean | true | — | 是否顯示時鐘圖示 |
| onExpire | function | — | — | 逾時回呼 |

**交通燈色彩規格**：

| 級別 | 條件 | 背景色 | 文字色 | 邊框 | 動效 |
|------|------|--------|--------|------|------|
| Green | > 50% 剩餘 | `#ECFDF5` Emerald-50 | `#047857` Emerald-700 | `border-emerald-200` | 無 |
| Amber | 20-50% 剩餘 | `#FFFBEB` Amber-50 | `#B45309` Amber-700 | `border-amber-400` | 邊框脈動 2s infinite |
| Red | < 20% 剩餘 | `#FEF2F2` Red-50 | `#B91C1C` Red-700 | `border-red-500` solid | pulse 動畫 1.5s |
| Black | 已逾時 | `#1E293B` Slate-800 | `#FFFFFF` | `border-slate-900` | 閃爍 1s infinite |

**文字格式**：
- 未逾時：「剩餘 02:30」
- 已逾時：「逾時 00:45」
- 即將逾時（< 5 min）：「剩餘 04:59」 每秒更新

**尺寸規格**：

| Size | 高度 | Font | Icon Size | 用途 |
|------|------|------|-----------|------|
| sm | 22px | 12px | 12px | Table cell |
| md | 28px | 14px | 14px | Card 內 |
| lg | 36px | 16px | 18px | Detail page header |

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Green | 綠色底 + 靜態 | > 50% 剩餘 |
| Amber | 琥珀底 + 邊框脈動 | 20-50% 剩餘 |
| Red | 紅色底 + pulse | < 20% 剩餘 |
| Black/Overdue | 深底白字 + 閃爍 | 已逾時 |
| Paused | 灰色底 + 暫停圖示 | 工單暫停（如待料中） |

#### Interaction（互動規則）
- 純展示元件，不可點擊（但可包在 Tooltip 中顯示詳細時間）
- 每秒更新（使用 `requestAnimationFrame` 或 interval）
- 級別轉換時有 transition 動畫（色彩漸變 300ms）
- 逾時瞬間觸發 `onExpire` callback + 震動（Tech PWA）

#### Accessibility
- `role="timer"`、`aria-live="polite"`
- `aria-label`：「服務等級協議倒計時：剩餘 2 小時 30 分」
- 色彩 + 圖示 + 文字三重指示

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 同時顯示色彩 + 文字 + 圖示 | 只用色彩不顯示時間 |
| 逾時狀態用深底白字 + 閃爍 | 逾時跟紅色狀態看起來一樣 |
| < 5 分鐘時每秒更新 | 全部 1 分鐘才更新一次 |
| 待料中等暫停狀態顯示 Paused | 暫停時還在倒數 |

---

### 4.2 KanbanBoard（看板）

#### Purpose（用途）
Admin Panel 的核心派工介面。5 欄看板，技師可拖曳工單卡片在狀態間移動。

#### Anatomy（結構）
- [ ] Board Container（水平 scroll wrapper）
- [ ] Column（5 欄，固定寬度 280px）
- [ ] Column Header（狀態名稱 + 數量 Badge + 摺疊按鈕）
- [ ] Card List（垂直排列，可 scroll）
- [ ] KanbanCard（拖曳單位）
- [ ] Drop Indicator（拖曳放置指示）
- [ ] Empty Column State

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| columns | Column[] | — | 見下表 | 欄位定義 |
| workOrders | WorkOrder[] | — | — | 工單資料 |
| onMove | function | — | — | 拖曳完成回呼 |
| onCardClick | function | — | — | 卡片點擊回呼 |
| realtime | boolean | true | — | 是否啟用 WebSocket 即時更新 |

**5 欄定義**：

| 欄位 | 對應狀態 | Header 色彩 | Icon |
|------|---------|-------------|------|
| 待指派 | `created` | `border-t-indigo-500` | `Inbox` |
| 已派工 | `assigned`, `accepted` | `border-t-violet-500` | `UserCheck` |
| 進行中 | `in_progress`, `scope_changed`, `material_pending` | `border-t-blue-500` | `Wrench` |
| 已完工 | `completed`, `confirmed` | `border-t-emerald-500` | `CheckCircle` |
| 異常 | `delayed`, `rework_required`, `disputed`, `cancelled` | `border-t-red-500` | `AlertTriangle` |

**拖曳規則（有效狀態轉換）**：

| 從 | 可拖至 | 說明 |
|----|-------|------|
| 待指派 | 已派工 | 指派技師（觸發指派 Dialog） |
| 已派工 | 進行中 | 技師開始服務 |
| 已派工 | 待指派 | 退回未指派 |
| 進行中 | 已完工 | 完成服務 |
| 進行中 | 異常 | 發生異常 |
| 已完工 | 進行中 | 需返工 |
| 異常 | 進行中 | 異常解除 |
| 異常 | 待指派 | 重新指派 |

- 無效拖曳：卡片回彈原位 + shake 動畫
- Column 寬度：280px（固定）
- Column max height：`calc(100vh - 200px)`，內部 scroll
- Card 間距：`gap-2`（8px）
- Column 間距：`gap-4`（16px）
- Board overflow：水平 scroll

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 5 欄正常排列 | 初始 |
| Dragging | 拖曳卡片 `shadow-kanban` + 原位 placeholder | 拖曳開始 |
| Drag Over (valid) | 目標欄 `bg-blue-50` + drop indicator 藍線 | 拖曳經過有效欄位 |
| Drag Over (invalid) | 目標欄 `bg-red-50` + 🚫 cursor | 拖曳經過無效欄位 |
| Optimistic Update | 卡片立即移動 + 半透明 | 放下後、API 回應前 |
| Rollback | 卡片動畫回彈原位 + error toast | API 失敗 |
| WebSocket Update | 卡片漸入新位置 + highlight 2s | 外部更新 |
| Empty Column | 「目前無工單」虛線框 | 欄位無卡片 |

#### Interaction（互動規則）
- 拖曳引擎：`@dnd-kit/core` + `@dnd-kit/sortable`
- 拖曳啟動：Desktop 滑鼠按住 150ms / Mobile 長按 300ms
- Optimistic UI：放下後卡片立即移至新欄，API 成功 → 確認，API 失敗 → 回彈 + toast
- WebSocket：其他用戶變更 → 卡片動態移動 + 2s 高亮
- 欄位 Header 點擊數量 Badge → 展開/摺疊欄位
- 卡片點擊 → 工單詳情 side panel

#### Accessibility
- Board：`role="region"`、`aria-label="派工看板"`
- Column：`role="list"`、`aria-label="待指派工單"`
- Card：`role="listitem"`、`aria-roledescription="可拖曳工單卡片"`
- 鍵盤拖曳：`Space` 拾起 → `Arrow` 移動 → `Space` 放下 → `Esc` 取消
- 拖曳狀態朗讀：「正在移動工單 WO-2026-0421，目前位於待指派欄」

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| Optimistic UI + rollback on failure | 等 API 回來才更新 UI（慢） |
| 無效拖曳有 shake + cursor 回饋 | 無效拖曳靜悄悄 |
| WebSocket 外部更新有 highlight 動畫 | 卡片突然跳位沒有提示 |
| 拖曳到「已派工」觸發指派 Dialog | 拖曳直接指派不經確認 |
| Mobile 長按 300ms 啟動拖曳 | Mobile 不支援拖曳 |

---

### 4.3 MapView（地圖檢視）

#### Purpose（用途）
Google Maps 包裝元件，在地圖上顯示工單位置與技師位置，支援即時追蹤。

#### Anatomy（結構）
- [ ] Map Container（`@vis.gl/react-google-maps`）
- [ ] Pin Markers（不同類型圖釘）
- [ ] Cluster Markers（聚合標記）
- [ ] Popup Card（圖釘點擊彈出）
- [ ] Legend（圖例）
- [ ] Map Controls（zoom / fullscreen / layer toggle）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| workOrders | WorkOrder[] | [] | — | 工單資料（含 lat/lng） |
| technicians | Technician[] | [] | — | 技師資料（含即時位置） |
| center | LatLng | — | — | 初始中心點 |
| zoom | number | 12 | 8-18 | 初始縮放 |
| showLegend | boolean | true | — | 是否顯示圖例 |
| showClusters | boolean | true | — | 是否聚合標記 |
| onPinClick | function | — | — | 圖釘點擊回呼 |
| selectedId | string | — | — | 高亮選中的圖釘 |

**圖釘類型規格**：

| Type | 色彩 | Icon | 動效 | 說明 |
|------|------|------|------|------|
| Unassigned WO | `#EF4444` Red-500 | 🔴 圓形 pin | 靜態 | 未指派工單 |
| Assigned WO | `#8B5CF6` Violet-500 | 紫色 pin | 靜態 | 已指派工單 |
| In Progress WO | `#3B82F6` Blue-500 | 藍色 pin | 靜態 | 進行中工單 |
| Technician | `#3B82F6` Blue-600 | 人形 icon | 脈動光環（2s infinite） | 技師即時位置 |
| Completed WO | `#10B981` Green-500 | 綠色 pin | 靜態 | 已完工 |
| Exception WO | `#F59E0B` Amber-500 | 橘色三角 | 閃爍 | 異常工單 |

- Cluster：圓形，顯示數量，色彩取最嚴重等級
- Popup Card：點擊圖釘彈出迷你 WorkOrderCard 或 Technician Card
- Popup 寬度：280px，`shadow-lg`、`radius-lg`

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 所有 pin 正常顯示 | 初始 |
| Pin Hover | pin 放大 1.2x | 滑鼠移入 |
| Pin Selected | pin 放大 1.3x + 光環 + popup 開啟 | 點擊 |
| Popup Open | 迷你 card 彈出 | pin 點擊 |
| Synced Highlight | pin 放大 + bounce 動畫 | 列表項目點擊 |
| Loading | skeleton overlay | 資料載入中 |
| Tech Moving | 技師 pin 平滑移動 | WebSocket 位置更新 |

#### Interaction（互動規則）
- Pin click → 彈出 popup card
- Popup card → Action buttons（查看詳情/指派/導航）
- 列表 ↔ 地圖 雙向同步：
  - 點擊列表項 → 地圖 zoom to pin + highlight
  - 點擊 pin → 列表 scroll to item + highlight
- Cluster click → zoom in 展開
- 技師 pin：WebSocket 即時更新位置，平滑動畫移動
- 地圖邊界變更 → 重新載入可視範圍內的資料

#### Accessibility
- Map：`role="application"`、`aria-label="工單與技師位置地圖"`
- Pins：作為 button，`aria-label="未指派工單 WO-2026-0421，台北市信義區"`
- Popup：`role="dialog"`
- Legend：`role="list"` with status descriptions

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 超過 50 個 pin 啟用 clustering | 地圖上 200 個 pin 重疊 |
| 技師 pin 有脈動動畫區分 | 技師跟工單用一樣的 pin |
| Popup 有直接操作按鈕（指派/導航） | Popup 只顯示資訊沒有 action |
| 地圖 + 列表雙向同步 | 地圖與列表獨立運作 |
| 圖例常駐顯示 | 沒有圖例，用戶猜色彩含義 |

---

### 4.4 BottomSheet（底部面板）— Tech PWA 專用

#### Purpose（用途）
Technician PWA 的主要資訊展示容器，從底部滑出，三段式高度。

#### Anatomy（結構）
- [ ] Pull Indicator（頂部拉桿，40px × 4px 圓角灰條）
- [ ] Header（Title + Close/Action）
- [ ] Body（可 scroll 內容區）
- [ ] Safe Area Padding（底部，避免手機底部手勢區）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| state | enum | collapsed | `collapsed` / `half` / `full` | 展開狀態 |
| collapsedHeight | number | 96 | — | 收合高度 (px) |
| halfHeight | string | "50%" | — | 半展開高度 |
| fullHeight | string | "90%" | — | 全展開高度 |
| title | string | — | — | 標題 |
| showPullIndicator | boolean | true | — | 是否顯示拉桿 |
| onStateChange | function | — | — | 狀態變更回呼 |
| dismissible | boolean | true | — | 是否可關閉 |

**三段式規格**：

| State | 高度 | 顯示內容 | 手勢 |
|-------|------|---------|------|
| Collapsed | 96px | Pull indicator + 標題摘要（如「3 筆待處理工單」） | 上滑展開至 half |
| Half | 50vh | 列表或摘要內容 | 上滑至 full / 下滑至 collapsed |
| Full | 90vh | 完整內容 + 可 scroll | 下滑至 half |

- Pull Indicator：居中，40px × 4px，`bg-slate-300`、`radius-full`
- 動畫：spring physics（`stiffness: 300, damping: 30`）
- 背景 overlay：full state 時 `bg-black/20`
- Safe area：`padding-bottom: env(safe-area-inset-bottom)`
- 圓角：top-left + top-right `radius-xl`（12px）

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Collapsed | 只露出 96px | 初始 / 下滑 |
| Half | 50vh | 上滑至閾值 / 程式設定 |
| Full | 90vh + overlay | 繼續上滑 / 程式設定 |
| Dragging | 跟隨手指位置 | touch move |
| Snapping | 彈簧動畫至最近 snap point | touch end |

#### Interaction（互動規則）
- 手勢：touch 上滑/下滑，速度超過閾值 snap 至下/上一段
- Pull indicator 區域：touch target 至少 44px 高
- Body 內部 scroll：body 內容到頂時，繼續下滑 → 觸發 sheet 收合
- 防止背景 scroll：full state 時背景 `overflow: hidden`
- 關閉：下滑超過 collapsed → dismiss（如果 `dismissible=true`）

#### Accessibility
- `role="dialog"`（half/full 時）
- `aria-label`：面板標題
- 拉桿：`role="slider"`、`aria-label="拖曳展開面板"`
- Focus trap：full state 時啟用

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| Collapsed 顯示摘要（如工單數量） | Collapsed 只有空白拉桿 |
| Spring 彈簧動畫，自然物理感 | 線性動畫（不自然） |
| 尊重 safe-area-inset-bottom | 內容被手機底部手勢遮擋 |
| Body scroll 到頂才觸發 sheet 下滑 | 任何下滑都收合 sheet（很惱人） |

---

### 4.5 WorkTimeline（工單時間軸）

#### Purpose（用途）
垂直時間軸顯示工單歷史紀錄，包含所有狀態變更、操作、備註。

#### Anatomy（結構）
- [ ] Timeline Container（垂直線）
- [ ] Timeline Node（每個事件節點）
  - [ ] Timestamp（左側或上方）
  - [ ] Status Dot（色彩對應狀態語意色）
  - [ ] Actor Avatar（操作人頭像）
  - [ ] Content Card
    - [ ] StatusBadge（狀態變更時）
    - [ ] Description（事件描述）
    - [ ] Metadata（附加資訊）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| events | TimelineEvent[] | [] | — | 事件列表 |
| variant | enum | default | `default` / `compact` | 變體 |
| showAvatar | boolean | true | — | 是否顯示操作人頭像 |
| maxItems | number | — | — | 最大顯示數（可展開更多） |

**TimelineEvent 結構**：

| 欄位 | Type | 說明 |
|------|------|------|
| id | string | 事件 ID |
| timestamp | Date | 時間戳 |
| type | enum | `status_change` / `note` / `photo` / `system` / `sla_warning` |
| actor | Actor | 操作人（name + avatar + role） |
| status | string | 狀態值（status_change 時） |
| description | string | 事件描述 |
| metadata | object | 附加資訊（如零件清單、照片 URL） |

**節點色彩對應**：

| Event Type | Dot 色彩 | Icon |
|------------|---------|------|
| status_change | 對應狀態色群 | StatusBadge |
| note | `#94A3B8` Slate-400 | `MessageSquare` |
| photo | `#6366F1` Indigo-500 | `Camera` |
| system | `#64748B` Slate-500 | `Settings` |
| sla_warning | `#F59E0B` Amber-500 | `AlertTriangle` |

- 時間軸線：`border-l-2 border-slate-200`
- Node 間距：`space-6`（24px）
- Timestamp 格式：「今天 14:30」「昨天 09:15」「2026/04/19 16:42」
- Compact variant：隱藏 avatar，縮小間距

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 顯示最近 N 筆 | 初始 |
| Expanded | 顯示全部 | 點擊「查看更多」 |
| Loading | Skeleton nodes | 載入中 |
| Empty | 「尚無紀錄」 | 無事件 |
| New Event | 頂部新事件 slide-in + highlight 2s | WebSocket 即時推播 |

#### Interaction（互動規則）
- 預設顯示最新 10 筆，底部「查看更多」展開
- 新事件（WebSocket）：頂部 slide-in + 2s highlight
- 照片類型事件：thumbnail 可點擊展開 lightbox
- 備註事件：可回覆

#### Accessibility
- `role="list"`、每個 node `role="listitem"`
- Timestamp：`<time>` 元素 with `datetime` 屬性
- 色彩 + icon + 文字三重指示

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 用相對時間（「2 小時前」） + 完整時間（tooltip） | 只顯示完整時間戳（不直覺） |
| 新事件有 slide-in 動畫 | 新事件突然出現沒有提示 |
| 狀態變更節點使用 StatusBadge | 只用文字描述狀態變更 |
| SLA 警告在時間軸上可見 | SLA 警告只出現在 toast |

---

### 4.6 DeviceStatusPanel（設備狀態面板）

#### Purpose（用途）
顯示特定電子鎖的詳細狀態，包含設備圖片、三項指標、操作按鈕。用於工單詳情頁和設備管理頁。

#### Anatomy（結構）
- [ ] Device Image / Icon（鎖具型號圖片或通用 lock icon）
- [ ] Model Label（品牌 + 型號）
- [ ] Metric Cards（3 張，水平排列）
  - [ ] Battery Ring Chart（電量環形圖）
  - [ ] Connectivity Status Light（連線狀態燈）
  - [ ] Last Operation Timestamp（最後操作時間）
- [ ] Action Buttons（遠端開鎖、重設密碼等）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| device | DeviceInfo | — | — | 設備資訊 |
| battery | number | — | 0-100 | 電量百分比 |
| connectivity | enum | — | `online` / `offline` / `weak` | 連線狀態 |
| lastOperation | Date | — | — | 最後操作時間 |
| actions | Action[] | — | — | 可用操作 |
| onAction | function | — | — | 操作回呼 |

**電量環形圖規格**：

| 電量 | 色彩 | 說明 |
|------|------|------|
| > 50% | `#10B981` Green | 正常 |
| 20-50% | `#F59E0B` Amber | 偏低 |
| < 20% | `#EF4444` Red | 低電量警告 |
| Unknown | `#94A3B8` Slate | 無資料 |

- Ring chart：SVG 圓環，stroke-width 8px，背景 `stroke-slate-100`
- 中心顯示百分比數值

**連線狀態燈規格**：

| Status | 色彩 | 動效 | 文字 |
|--------|------|------|------|
| online | `#10B981` Green | 靜態 | 正常連線 |
| weak | `#F59E0B` Amber | 慢速脈動 | 訊號微弱 |
| offline | `#EF4444` Red | 靜態 | 離線 |

**操作按鈕**：

| Action | Variant | 需確認 | 說明 |
|--------|---------|--------|------|
| 遠端開鎖 | cta | 是（高危 Dialog） | 遠端觸發開鎖 |
| 重設密碼 | secondary | 是 | 重設鎖具使用者密碼 |
| 診斷測試 | ghost | 否 | 觸發遠端診斷 |
| 查看日誌 | link | 否 | 導向設備日誌頁 |

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 正常顯示 3 指標 + 操作 | 初始 |
| Loading | Skeleton 佔位 | 資料載入中 |
| Offline | connectivity 離線 + 操作按鈕 disabled | 設備離線 |
| Action Pending | 按鈕 loading spinner | 等待設備回應 |
| Action Success | 綠色 flash + success toast | 操作成功 |
| Action Failed | 按鈕恢復 + error toast | 操作失敗 |
| No Data | 「無法取得設備資訊」+ retry | API 失敗 |

#### Interaction（互動規則）
- 電量、連線狀態：WebSocket 即時更新
- 遠端開鎖：需二次確認 Dialog（含原因選擇）
- 設備離線時：操作按鈕 disabled + tooltip 說明
- 操作結果等待：最多 30 秒 timeout

#### Accessibility
- Battery ring：`role="img"`、`aria-label="電量 87%"`
- Connectivity：`aria-label="連線狀態：正常"`
- 操作按鈕：明確 `aria-label`

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 設備離線時 disable 操作按鈕 + 說明原因 | 離線時還能點操作按鈕（導致錯誤） |
| 遠端開鎖需二次確認 + 原因選擇 | 遠端開鎖一鍵直接執行 |
| 電量低於 20% 用紅色 + 警告 | 低電量跟正常電量看起來一樣 |
| 最後操作用相對時間（「5 分鐘前」） | 只顯示完整時間戳 |

---

### 4.7 CompletionReportForm（完工報告表單）

#### Purpose（用途）
Tech PWA 完工回報的多區塊表單，涵蓋檢核清單、零件紀錄、照片、功能測試、電子簽名。

#### Anatomy（結構）
- [ ] Form Header（工單號 + 客戶資訊 + 進度指示器）
- [ ] Section 1: Service Checklist（核取方塊清單）
- [ ] Section 2: Parts Used（零件明細，可新增/移除列）
- [ ] Section 3: Photo Gallery（拍照 + 上傳）
- [ ] Section 4: Functional Tests（開關切換）
- [ ] Section 5: Signature Canvas（電子簽名）
- [ ] Summary Bar（費用總計 + 提交按鈕）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| workOrderId | string | — | — | 工單 ID |
| checklist | ChecklistItem[] | — | — | 檢核項目 |
| partsCatalog | Part[] | — | — | 零件目錄 |
| requiredPhotos | number | 3 | — | 最少照片數 |
| functionalTests | Test[] | — | — | 功能測試項目 |
| onSubmit | function | — | — | 提交回呼 |
| onSaveDraft | function | — | — | 儲存草稿回呼 |

**Section 規格**：

**1. Service Checklist**：
```
┌─────────────────────────────────┐
│ 服務檢核清單                      │
├─────────────────────────────────┤
│ ☑ 確認鎖具型號與報修相符          │
│ ☑ 拆卸舊零件                     │
│ ☐ 安裝新零件                     │
│ ☐ 功能測試通過                   │
│ ☐ 現場環境清潔                   │
│ ☐ 客戶確認滿意                   │
└─────────────────────────────────┘
```

**2. Parts Used（動態列表）**：
```
┌────────────┬──────┬────────┬─────┐
│ 零件名稱    │ 數量 │ 單價   │     │
├────────────┼──────┼────────┼─────┤
│ [Select ▼] │ [1]  │ $1,200 │ [🗑] │
│ [Select ▼] │ [2]  │ $  350 │ [🗑] │
├────────────┴──────┴────────┴─────┤
│ [+ 新增零件]          小計: $1,900 │
└──────────────────────────────────┘
```
- 零件選擇：combobox（可搜尋零件目錄）
- 數量：number input，min 1
- 單價：readonly（從目錄帶入）
- 小計：即時計算

**3. Photo Gallery**：
- Grid 排列（3 欄）
- 至少 3 張照片才可提交
- 拍照按鈕（呼叫 camera API）+ 上傳按鈕
- 每張照片可標註分類（施工前/施工後/零件）

**4. Functional Tests（開關列表）**：
```
┌─────────────────────────────────┐
│ 功能測試                         │
├─────────────────────────────────┤
│ 指紋辨識    [Pass ● ─── ○ Fail] │
│ 密碼開鎖    [Pass ● ─── ○ Fail] │
│ 卡片感應    [Pass ● ─── ○ Fail] │
│ 遠端開鎖    [Pass ● ─── ○ Fail] │
│ 自動上鎖    [Pass ● ─── ○ Fail] │
└─────────────────────────────────┘
```

**5. Signature Canvas**：
- 白底畫布，touch 繪製
- 「清除」按鈕重新簽名
- 最小筆畫偵測（避免空白提交）

**Summary Bar（固定底部）**：
```
┌──────────────────────────────────┐
│ 總計: $1,900  │  [儲存草稿] [提交報告] │
└──────────────────────────────────┘
```
- 提交按鈕：所有必填完成才啟用（CTA variant）
- 草稿自動儲存至 IndexedDB

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 各 section 可填寫 | 初始 |
| Partial | 已填 section 有綠色 checkmark | 部分填寫 |
| Draft Saved | 底部短暫提示「草稿已儲存」 | 自動/手動儲存 |
| Validation Error | 未完成 section 紅色標示 | 點擊提交 |
| Submitting | 提交按鈕 loading + 全表單 disabled | 送出中 |
| Success | 成功頁面 + 工單狀態更新 | 送出成功 |
| Offline | 「離線模式」banner + 存入 sync queue | 無網路 |

#### Interaction（互動規則）
- 各 Section 獨立驗證
- 草稿每 30 秒自動儲存至 IndexedDB
- 離線時可完整填寫，上線後自動同步
- 照片拍攝：使用 `navigator.mediaDevices.getUserMedia`
- 簽名板：Canvas API，touch events
- 提交前顯示摘要確認 Dialog

#### Accessibility
- 每個 section 有 `<fieldset>` + `<legend>`
- Checkbox / Switch 有 `aria-label`
- 照片 gallery：每張照片 `alt` 描述
- 簽名板：`aria-label="客戶簽名區"`

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 自動儲存草稿至 IndexedDB | 離開頁面遺失所有填寫 |
| 照片最少 3 張才能提交 | 不拍照也能提交完工 |
| 零件選擇從目錄帶入單價 | 讓技師手動輸入價格（容易錯） |
| 簽名有最小筆畫偵測 | 空白簽名也能提交 |
| 離線可填寫 + 上線自動 sync | 無網路完全無法操作 |

---

### 4.8 AIRecommendationBadge（AI 推薦徽章）

#### Purpose（用途）
標示 AI 推薦的項目（如最佳派工候選人、診斷建議、SOP 草案），提供推薦理由的 tooltip。

#### Anatomy（結構）
- [ ] Badge Container（Indigo pill）
- [ ] AI Icon（sparkle / brain icon）
- [ ] "AI" Text Label
- [ ] Tooltip（hover 顯示推薦理由）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| type | enum | recommendation | `recommendation` / `suggestion` / `auto` | 類型 |
| reason | string | — | — | 推薦理由（Tooltip 顯示） |
| confidence | number | — | 0-100 | 信心度（可選顯示） |
| size | enum | sm | `sm` / `md` | 尺寸 |

**類型規格**：

| Type | 文字 | 場景 |
|------|------|------|
| recommendation | 「AI 推薦」 | 派工候選人 #1 |
| suggestion | 「AI 建議」 | 診斷建議、SOP 草案 |
| auto | 「AI 自動」 | 自動指派結果 |

- 色彩：`#6366F1` Indigo-500 背景 `#EEF2FF` Indigo-50、文字 `#4338CA` Indigo-700
- Radius：`radius-full`（pill）
- Icon：`Sparkles`（lucide-react）
- Tooltip：白底、`shadow-lg`、max-width 280px、顯示推薦理由段落

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | Indigo pill + AI text | 初始 |
| Hover | Tooltip 浮出 + badge 微亮 | 滑鼠移入 |
| With Confidence | 附加百分比「AI 推薦 95%」 | `confidence` 有值 |

#### Interaction（互動規則）
- Hover / Focus → Tooltip 顯示推薦理由
- Tooltip 內容可包含多行文字
- 點擊 badge 不觸發任何動作（純展示）
- 永遠伴隨「人工覆寫」選項（badge 附近有 override button）

#### Accessibility
- `role="img"`、`aria-label="AI 推薦：{reason}"`
- Tooltip：`role="tooltip"`

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| Tooltip 解釋推薦理由 | 只標「AI 推薦」不解釋為什麼 |
| 附近永遠有「人工覆寫」選項 | AI 推薦不可覆寫 |
| 使用統一的 Indigo 色系 | 用其他顏色混淆語意 |
| confidence 有意義時才顯示 | 永遠顯示 confidence（低信心度反而降低信任） |

---

## 5. P2 元件清單

### 5.1 SignaturePad（電子簽名板）

#### Purpose（用途）
Tech PWA 完工報告中的客戶電子簽名元件，使用 Canvas 觸控繪製。

#### Anatomy（結構）
- [ ] Canvas Container（白底、border）
- [ ] Placeholder Text（「請在此簽名」灰色提示）
- [ ] Clear Button（右上角）
- [ ] Stroke Preview（即時筆觸）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| width | number | 100% | — | 寬度 |
| height | number | 200 | — | 高度 (px) |
| strokeColor | string | #1E293B | — | 筆觸色彩 |
| strokeWidth | number | 2.5 | — | 筆觸粗細 |
| onSign | function | — | — | 簽名完成回呼（base64） |
| minStrokes | number | 5 | — | 最少筆觸數 |

- Border：`border-2 border-slate-200`、focus `border-blue-500`
- Radius：`radius-lg`（8px）
- Placeholder：居中灰色文字，簽名開始後消失
- Clear button：ghost variant，右上角

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Empty | Placeholder 顯示 | 初始 |
| Drawing | 即時筆觸 + placeholder 消失 | touch/mouse 開始 |
| Signed | 簽名內容 + clear 按鈕 | 筆觸 >= minStrokes |
| Invalid | 紅色邊框 + 「簽名筆畫不足」 | 驗證失敗 |

#### Interaction（互動規則）
- Touch events：`touchstart` / `touchmove` / `touchend`
- Mouse fallback：`mousedown` / `mousemove` / `mouseup`
- 清除按鈕：確認 Dialog 後清空
- 輸出：`toDataURL('image/png')` base64

#### Accessibility
- `role="img"`（簽名完成後）
- `aria-label="客戶簽名區"`
- 鍵盤替代：提供「上傳簽名圖片」選項

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 最少筆畫偵測（防空白提交） | 隨便一點就算簽名完成 |
| 提供清除重簽功能 | 簽錯不能重來 |
| 白底 + 深色筆觸（高對比） | 淺色筆觸看不清楚 |

---

### 5.2 PhotoGallery（照片圖庫）

#### Purpose（用途）
工單相關照片的 grid 展示 + lightbox 放大 + 拍照/上傳功能。

#### Anatomy（結構）
- [ ] Grid Container（3 欄 responsive grid）
- [ ] Photo Thumbnail（正方形、圓角）
- [ ] Category Tag（施工前/施工後/零件）
- [ ] Add Button（拍照 + 上傳）
- [ ] Lightbox Overlay（放大檢視）
- [ ] Count Indicator（「3/5 張」）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| photos | Photo[] | [] | — | 照片列表 |
| minCount | number | 3 | — | 最少照片數 |
| maxCount | number | 10 | — | 最多照片數 |
| categories | string[] | — | — | 分類選項 |
| editable | boolean | true | — | 是否可新增/刪除 |
| onAdd | function | — | — | 新增回呼 |
| onRemove | function | — | — | 刪除回呼 |

- Thumbnail：正方形 `aspect-square`、`radius-md`（6px）、`object-cover`
- Grid：`grid-cols-3 gap-2`
- Category Tag：左下角小 Tag
- Add button：虛線邊框 + `+` icon + 相機 icon
- Lightbox：全螢幕黑底、左右滑動切換、pinch zoom

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Empty | Add button + 「至少拍 {minCount} 張照片」 | 無照片 |
| Partial | Grid + 「還需 {remaining} 張」 | 未達 minCount |
| Complete | Grid + 綠色 checkmark | >= minCount |
| Uploading | Thumbnail overlay + progress | 照片上傳中 |
| Lightbox | 全螢幕放大 | 點擊照片 |

#### Interaction（互動規則）
- 點擊 Add → ActionSheet（拍照 / 從相簿選取）
- 點擊 thumbnail → lightbox 放大
- 長按 thumbnail → 刪除確認
- Lightbox：左右 swipe 切換、pinch zoom、X 關閉

#### Accessibility
- 每張照片 `alt` 描述（分類 + 序號）
- Lightbox：`role="dialog"`、`aria-label="照片放大檢視"`
- Add button：`aria-label="新增照片"`

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 顯示剩餘需要張數 | 不提示就不能提交 |
| 上傳中顯示 progress | 按了拍照沒有任何回饋 |
| 照片分類標籤（施工前/後） | 所有照片混在一起 |

---

### 5.3 SkillBadge（技能徽章）

#### Purpose（用途）
顯示技師的品牌認證和技能等級，包含熟練度星級和到期指示。

#### Anatomy（結構）
- [ ] Brand Logo / Icon
- [ ] Brand Name
- [ ] Proficiency Stars（1-5 星）
- [ ] Expiry Indicator（可選）

#### Props（可配置項）

| Prop | Type | Default | Options | 說明 |
|------|------|---------|---------|------|
| brand | string | — | — | 品牌名稱 |
| proficiency | number | — | 1-5 | 熟練度星級 |
| certified | boolean | false | — | 是否認證 |
| expiryDate | Date | — | — | 認證到期日 |
| size | enum | md | `sm` / `md` | 尺寸 |

**熟練度顯示**：
- 1-5 顆星：`★` 填充 `#F59E0B` Amber / `☆` 空心 `#CBD5E1` Slate-300
- Certified：badge 左上角 ✓ 徽章（`#10B981` Green）

**到期指示**：

| 狀態 | 色彩 | 文字 |
|------|------|------|
| > 90 天 | 無指示 | — |
| 30-90 天 | `#F59E0B` Amber | 「即將到期」 |
| < 30 天 | `#EF4444` Red | 「即將過期」 |
| 已過期 | `#EF4444` Red + 刪除線 | 「已過期」 |

#### States（狀態矩陣）

| State | 視覺變化 | 觸發方式 |
|-------|---------|---------|
| Default | 品牌 + 星級 | 初始 |
| Certified | 左上角綠色 ✓ | `certified=true` |
| Expiring | Amber 到期標示 | 30-90 天 |
| Expired | Red 過期 + 刪除線 | 已過期 |

#### Interaction（互動規則）
- 純展示元件
- Hover tooltip：顯示認證日期、到期日、認證機構

#### Accessibility
- `aria-label`：「Yale 品牌認證，熟練度 4 星（滿分 5 星），認證有效至 2026/12/31」

#### Do / Don't

| ✅ Do | ❌ Don't |
|-------|---------|
| 過期認證用紅色 + 刪除線 | 過期認證不做任何標示 |
| 星級 + 文字描述 | 只用星級不說明含義 |
| 派工時優先顯示相關品牌認證 | 列出所有認證（多而無用） |

---

## 6. 元件命名規範

### 6.1 Figma 命名

```
格式：[Category] / [Component Name] / [Variant]

範例：
  Actions / Button / Primary
  Actions / Button / CTA
  Actions / Button / Danger
  Inputs / TextField / Default
  Inputs / Select / Multi
  Data Display / StatusBadge / InProgress
  Data Display / SLACountdown / Green
  Data Display / KPICard / Default
  Data Display / WorkOrderCard / Default
  Data Display / DeviceStatusCard / Default
  Feedback / Toast / Dispatch
  Navigation / KanbanBoard / Default
  Navigation / BottomSheet / Collapsed
  Organisms / MapView / Default
  Organisms / WorkTimeline / Default
  Organisms / CompletionReportForm / Default
  Organisms / DeviceStatusPanel / Default
  Atoms / AIRecommendationBadge / Default
  Atoms / SkillBadge / Certified
```

### 6.2 工程命名

| Figma 名稱 | React 元件名 | 檔案路徑 |
|------------|-------------|----------|
| Actions / Button | `<Button>` | `components/ui/button.tsx` |
| Inputs / TextField | `<TextField>` | `components/ui/text-field.tsx` |
| Inputs / Select | `<Select>` | `components/ui/select.tsx` |
| Data Display / StatusBadge | `<StatusBadge>` | `components/smart-lock/status-badge.tsx` |
| Data Display / SLACountdown | `<SLACountdown>` | `components/smart-lock/sla-countdown.tsx` |
| Data Display / KPICard | `<KPICard>` | `components/smart-lock/kpi-card.tsx` |
| Data Display / WorkOrderCard | `<WorkOrderCard>` | `components/smart-lock/work-order-card.tsx` |
| Data Display / DeviceStatusCard | `<DeviceStatusCard>` | `components/smart-lock/device-status-card.tsx` |
| Feedback / Toast | `<Toast>` | `components/ui/toast.tsx` |
| Navigation / KanbanBoard | `<KanbanBoard>` | `components/smart-lock/kanban-board.tsx` |
| Navigation / BottomSheet | `<BottomSheet>` | `components/smart-lock/bottom-sheet.tsx` |
| Organisms / MapView | `<MapView>` | `components/smart-lock/map-view.tsx` |
| Organisms / WorkTimeline | `<WorkTimeline>` | `components/smart-lock/work-timeline.tsx` |
| Organisms / DeviceStatusPanel | `<DeviceStatusPanel>` | `components/smart-lock/device-status-panel.tsx` |
| Organisms / CompletionReportForm | `<CompletionReportForm>` | `components/smart-lock/completion-report-form.tsx` |
| Atoms / AIRecommendationBadge | `<AIRecommendationBadge>` | `components/smart-lock/ai-recommendation-badge.tsx` |
| Atoms / SignaturePad | `<SignaturePad>` | `components/smart-lock/signature-pad.tsx` |
| Atoms / PhotoGallery | `<PhotoGallery>` | `components/smart-lock/photo-gallery.tsx` |
| Atoms / SkillBadge | `<SkillBadge>` | `components/smart-lock/skill-badge.tsx` |

### 6.3 命名規則

```
規則 1：Figma 用 / 分層（Category / Name / Variant）
規則 2：React 用 PascalCase（Button、StatusBadge、KanbanBoard）
規則 3：檔案用 kebab-case（status-badge.tsx、kanban-board.tsx）
規則 4：Props 用 camelCase（variant、slaStatus、onStateChange）
規則 5：shadcn/ui 基礎元件放 components/ui/，平台專屬放 components/smart-lock/
規則 6：設計與工程名稱必須 1:1 對應（建立 Code Connect mapping）
```

---

## 7. 元件 Inventory 總表

| # | 元件 | 分層 | 優先級 | 端點 | Variants 數 | States 覆蓋 | 版本 |
|---|------|------|--------|------|------------|------------|------|
| 1 | Button | Atom | P0 | All | 6 | 6/6 | v1.0 |
| 2 | Input / TextField | Atom | P0 | All | 7 | 6/6 | v1.0 |
| 3 | Select | Atom | P0 | All | 3 | 7/7 | v1.0 |
| 4 | Card | Molecule | P0 | All | 8 | 8/8 | v1.0 |
| 5 | Modal / Dialog | Organism | P0 | Admin+PWA | 4 | 4/4 | v1.0 |
| 6 | Toast | Atom | P0 | All | 5 | 4/4 | v1.0 |
| 7 | Table | Organism | P0 | Admin | 4 | 5/5 | v1.0 |
| 8 | StatusBadge | Atom | P0 | All | 13 | 3/3 | v1.0 |
| 9 | Avatar | Atom | P0 | All | 3 | 3/3 | v1.0 |
| 10 | Tabs | Molecule | P0 | Admin+PWA | 3 | 5/5 | v1.0 |
| 11 | SLACountdown | Atom | P1 | All | 1 | 5/5 | v1.0 |
| 12 | KanbanBoard | Organism | P1 | Admin | 1 | 8/8 | v1.0 |
| 13 | MapView | Organism | P1 | Admin | 1 | 7/7 | v1.0 |
| 14 | BottomSheet | Organism | P1 | PWA | 1 | 5/5 | v1.0 |
| 15 | WorkTimeline | Organism | P1 | Admin+PWA | 2 | 5/5 | v1.0 |
| 16 | DeviceStatusPanel | Organism | P1 | Admin | 1 | 7/7 | v1.0 |
| 17 | CompletionReportForm | Organism | P1 | PWA | 1 | 7/7 | v1.0 |
| 18 | AIRecommendationBadge | Atom | P1 | Admin | 3 | 3/3 | v1.0 |
| 19 | SignaturePad | Molecule | P2 | PWA | 1 | 4/4 | v1.0 |
| 20 | PhotoGallery | Molecule | P2 | PWA | 1 | 5/5 | v1.0 |
| 21 | SkillBadge | Atom | P2 | Admin | 1 | 4/4 | v1.0 |

---

## 8. Do / Don't 範例

### 全局規則

| ✅ Do | ❌ Don't |
|-------|---------|
| 所有狀態都用色彩 + 文字 + 圖示三重指示 | 只靠顏色區分狀態 |
| Tech PWA 按鈕/觸控區域至少 44x44px | 按鈕太小手指點不到 |
| 平台專屬元件放 `components/smart-lock/` | 跟 shadcn/ui 基礎元件混在一起 |
| 所有互動元件都有 loading + error 狀態 | 只做 happy path |
| SLA 倒計時統一使用 SLACountdown 元件 | 各處自行實作倒計時（不一致） |
| AI 推薦統一使用 Indigo 色系 | AI 推薦用不同顏色 |
| CTA（琥珀色）只用於需要立即行動的場景 | CTA variant 濫用到一般操作 |

### StatusBadge

| ✅ Do | ❌ Don't |
|-------|---------|
| 永遠顯示色點 + 中文標籤 | 只顯示英文狀態碼 |
| 使用規定的 6 色群 | 13 個狀態用 13 種顏色 |
| 逾時狀態加動畫 | 逾時跟正常一樣靜態 |

### KanbanBoard

| ✅ Do | ❌ Don't |
|-------|---------|
| 有效拖曳顯示藍色指示區 | 不區分有效/無效拖曳目標 |
| 拖曳到「已派工」觸發指派 Dialog | 拖曳直接指派不經確認 |
| Optimistic UI + 失敗回彈 | 等 API 回來才移動卡片 |
| WebSocket 外部更新有動畫 | 突然跳位 |

---

## Figma 結構建議

```
📁 01_Components（Figma Page）
├── 📄 Overview（元件總覽 + Inventory 表）
├── 📄 Actions
│   ├── Button（6 variants × 6 states × 3 sizes）
│   └── Icon Button
├── 📄 Inputs
│   ├── TextField（含 search / textarea）
│   ├── Select（single / multi / combobox）
│   ├── Checkbox / Radio / Switch
│   └── SignaturePad
├── 📄 Data Display
│   ├── Table（工單列表專用 + 通用）
│   ├── StatusBadge（13 狀態 × 2 sizes）
│   ├── SLACountdown（4 級別 × 3 sizes）
│   ├── Avatar（含 status indicators）
│   ├── Card（4 基礎 + 4 平台專屬 variants）
│   ├── KPICard
│   ├── WorkOrderCard
│   ├── DeviceStatusCard
│   ├── AIRecommendationBadge
│   └── SkillBadge
├── 📄 Feedback
│   ├── Toast（5 variants 含 dispatch）
│   ├── Modal / Dialog（4 平台場景）
│   └── BottomSheet（3 states）
├── 📄 Navigation
│   ├── Tabs（3 variants + platform configs）
│   └── KanbanBoard（5 columns + all drag states）
├── 📄 Organisms
│   ├── MapView（pin types + popup）
│   ├── WorkTimeline（event types）
│   ├── DeviceStatusPanel（metrics + actions）
│   ├── CompletionReportForm（5 sections）
│   └── PhotoGallery
└── 📄 Do & Don't（全局 + 各元件錯用案例）
```

---

**版本**：v1.0
**最後更新**：2026-04-21
**技術棧**：Next.js 14 + shadcn/ui + Tailwind CSS + TanStack Query + @dnd-kit/core + @vis.gl/react-google-maps
**相關文件**：`00_foundations_spec.md`（基礎規格）、`02_patterns_spec.md`（互動模式）、`03_templates_spec.md`（頁面模板）
