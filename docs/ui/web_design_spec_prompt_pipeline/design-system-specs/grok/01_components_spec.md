# 01_Components — xAI Grok 風格 元件規格

> 元件層（Atoms / Molecules）。每個元件遵循 `00_foundations_spec.md` 的 token 系統。
> 預設皆 **Dark first**，Light mode 為對偶映射。

---

## 目錄

1. [Button](#1-button)
2. [Input / Textarea](#2-input--textarea)
3. [Select / Combobox](#3-select--combobox)
4. [Checkbox / Radio / Switch](#4-checkbox--radio--switch)
5. [Tag / Badge / Chip](#5-tag--badge--chip)
6. [Avatar](#6-avatar)
7. [Card](#7-card)
8. [Tooltip](#8-tooltip)
9. [Popover](#9-popover)
10. [Modal / Dialog](#10-modal--dialog)
11. [Toast / Snackbar](#11-toast--snackbar)
12. [Tabs](#12-tabs)
13. [Breadcrumb](#13-breadcrumb)
14. [Pagination](#14-pagination)
15. [Progress / Skeleton / Spinner](#15-progress--skeleton--spinner)
16. [Code Block / Inline Code](#16-code-block--inline-code)
17. [Kbd / Shortcut](#17-kbd--shortcut)
18. [Divider](#18-divider)
19. [Eyebrow](#19-eyebrow)
20. [Marquee](#20-marquee)

---

## 1. Button

Grok 按鈕：銳利、低 radius、無陰影、無發光、hover 純粹切換 surface 顏色。

### 1.1 Variants

| Variant | 用途 | bg | text | border | hover bg |
|---------|------|-----|------|--------|----------|
| `primary` | 主要 CTA | `text.primary` (#FAFAFA) | `text.inverse` (#0A0A0A) | none | `#E5E5E5` |
| `secondary` | 次要動作 | `surface.default` | `text.primary` | `border.default` (1px) | `surface.hover` |
| `ghost` | 純文字 / icon | transparent | `text.primary` | none | `surface.hover` |
| `outline` | 邊框型 | transparent | `text.primary` | `border.default` (1px) | `surface.hover` |
| `danger` | 危險動作 | transparent | `status.danger` (icon 色) | `border.default` (1px) | `surface.hover` |
| `link` | 內聯連結式 | none | `text.primary` | none（hover 加底線） | none |

### 1.2 Sizes

| Size | height | padding-x | font | icon | radius |
|------|--------|-----------|------|------|--------|
| `xs` | 24px | 8px | `type.label.sm` | 12px | `radius.sm` |
| `sm` | 32px | 12px | `type.label.md` | 14px | `radius.sm` |
| `md`（預設） | 40px | 16px | `type.label.md` | 16px | `radius.sm` |
| `lg` | 48px | 24px | `type.body.md` (medium) | 18px | `radius.sm` |
| `xl` | 56px | 32px | `type.body.lg` (medium) | 20px | `radius.sm` |

### 1.3 States

| State | 視覺處理 |
|-------|---------|
| Default | 按 §1.1 定義 |
| Hover | 切換 hover bg，**不做 translate / scale** |
| Active | bg 加深一階（用 active token） |
| Focus | `outline: 2px solid text.primary` + `outline-offset: 2px`（純白 ring，無發光） |
| Disabled | `opacity: 0.4` + `cursor: not-allowed` + 移除 hover |
| Loading | 文字保留但 `opacity: 0`，覆蓋 16px spinner（§15.3） |

### 1.4 Icon Button

| Size | 容器 | Icon | radius |
|------|------|------|--------|
| `sm` | 32×32 | 16px | `radius.sm` |
| `md` | 40×40 | 18px | `radius.sm` |
| `lg` | 48×48 | 20px | `radius.sm` |

> 圓形版：radius 改 `radius.full`，僅用於 Avatar Button（搭配大頭照）。

### 1.5 Button Group

```
 - segmented：水平排列、共用邊框、第一個 round-l-sm、最後 round-r-sm，中間 0
 - split-button：主按鈕 + 右側 chevron 觸發 dropdown，中間以 1px hairline 分隔
 - 上限：3 個按鈕，超過改用 dropdown
```

### 1.6 Anti-pattern

```
✗ 漸層底色按鈕
✗ 圓角 > 8px（除 IconButton 圓形版）
✗ 多色陰影
✗ hover 時整個按鈕放大
✗ 按鈕內超過 3 個 icon / 元素
```

---

## 2. Input / Textarea

### 2.1 Anatomy

```
[ Label ]
[ Hint? ]
┌──────────────────────────────────────┐
│ [icon?] Placeholder / Value          │ ← input field
└──────────────────────────────────────┘
[ Error / Helper text? ]
```

### 2.2 Sizes

| Size | height | padding | font |
|------|--------|---------|------|
| `sm` | 32px | 8px / 12px | `type.body.sm` |
| `md`（預設） | 40px | 10px / 14px | `type.body.md` |
| `lg` | 48px | 12px / 16px | `type.body.md` |

### 2.3 States

| State | bg | border | text |
|-------|-----|--------|------|
| Default | `canvas.sunken` | `border.default` | `text.primary` |
| Hover | `canvas.sunken` | `border.strong` | `text.primary` |
| Focus | `canvas.sunken` | `text.primary` 2px（純線條，無發光） | `text.primary` |
| Filled | 同 default | 同 default | `text.primary` |
| Error | `canvas.sunken` | `status.danger` | `text.primary` |
| Disabled | `surface.disabled` | `border.subtle` | `text.disabled` |
| ReadOnly | `surface.default` | `border.subtle` | `text.secondary` |

### 2.4 Label & Helper Text

| 元素 | typography | color | margin |
|------|-----------|-------|--------|
| Label | `type.label.md` | `text.primary` | margin-bottom 8px |
| Optional 標記 | `type.label.sm` + 小寫 | `text.tertiary` | inline 後綴 |
| Hint | `type.body.sm` | `text.tertiary` | margin-bottom 8px |
| Error | `type.body.sm` | `status.danger` | margin-top 6px，搭配 ⚠ icon |
| Success | `type.body.sm` | `status.success` | margin-top 6px |

### 2.5 Textarea

```
 - 預設 min-height: 96px
 - resize: vertical only
 - max-height: 240px（超過內部捲動）
 - 字數計數：右下角 type.body.xs + text.tertiary
```

### 2.6 Input Addon

```
 [Prefix] [Input] [Suffix]
 ┌────┬───────────────┬────┐
 │ $  │ 1,200.00      │USD │
 └────┴───────────────┴────┘
 - Prefix/Suffix bg = surface.default
 - 中間 input bg = canvas.sunken
 - 分隔線 = border.subtle 1px
```

---

## 3. Select / Combobox

### 3.1 Trigger

外觀同 §2 Input，右側追加 chevron icon（16px，`text.tertiary`）。

### 3.2 Dropdown Menu

| 屬性 | 值 |
|------|-----|
| bg | `canvas.overlay` |
| border | `border.hairline` 1px |
| radius | `radius.lg` (8px) |
| max-height | 320px（內部捲動） |
| padding | 4px |
| min-width | trigger 寬度 |
| z-index | `z.dropdown` |

### 3.3 Option Item

| 屬性 | 值 |
|------|-----|
| height | 36px |
| padding | 0 12px |
| font | `type.body.md` |
| radius | `radius.xs` |
| hover bg | `surface.hover` |
| selected bg | `surface.active` |
| selected text | `text.primary` |
| selected indicator | 左側 2px `text.primary` 邊條 |
| icon（左） | 16px，可選 |
| check（右） | 16px，僅 selected 顯示 |

### 3.4 Combobox 搜尋

```
 - 頂部固定 input（type.body.sm，無邊框，bg = transparent）
 - 下方 1px hairline 分隔
 - 無結果：顯示 "No results found"，type.body.sm + text.tertiary，置中
```

---

## 4. Checkbox / Radio / Switch

### 4.1 Checkbox

| State | Box bg | Box border | Check icon |
|-------|--------|------------|-----------|
| Unchecked | transparent | `border.default` 1.5px | 隱藏 |
| Hover | `surface.hover` | `border.strong` 1.5px | 隱藏 |
| Checked | `text.primary` | `text.primary` | `text.inverse`（黑色 ✓） |
| Indeterminate | `text.primary` | `text.primary` | `text.inverse` 短橫 |
| Disabled | transparent | `border.subtle` | 灰色 |

| Size | box | radius |
|------|-----|--------|
| `sm` | 14×14 | `radius.xs` |
| `md`（預設） | 16×16 | `radius.xs` |
| `lg` | 20×20 | `radius.xs` |

### 4.2 Radio

| State | Outer | Inner dot |
|-------|-------|-----------|
| Unchecked | 1.5px `border.default` 圓圈 | 隱藏 |
| Hover | 1.5px `border.strong` | 隱藏 |
| Checked | 1.5px `text.primary` | 8px 實心圓 `text.primary` |
| Disabled | 1.5px `border.subtle` | 隱藏 |

> 圓形元件，`radius.full`。

### 4.3 Switch

```
 ┌───────────┐    ┌───────────┐
 │○          │    │          ●│
 └───────────┘    └───────────┘
   off              on
```

| Size | Track | Thumb |
|------|-------|-------|
| `sm` | 28×16 | 12×12 |
| `md`（預設） | 36×20 | 16×16 |
| `lg` | 44×24 | 20×20 |

| State | Track bg | Thumb bg |
|-------|----------|----------|
| Off | `surface.elevated` | `text.secondary` |
| On | `text.primary` | `text.inverse` |
| Disabled | `surface.disabled` | `text.disabled` |

> Track radius `radius.full`，Thumb radius `radius.full`。動畫 `motion.duration.fast` + `motion.ease.snappy`。

---

## 5. Tag / Badge / Chip

### 5.1 Tag（內容分類）

| Size | height | padding-x | font | radius |
|------|--------|-----------|------|--------|
| `sm` | 20px | 6px | `type.body.xs` | `radius.xs` |
| `md` | 24px | 8px | `type.body.xs` | `radius.xs` |

| Variant | bg | text | border |
|---------|-----|------|--------|
| `neutral` | `surface.elevated` | `text.secondary` | none |
| `accent` | `surface.elevated` | `text.primary` | `border.default` 1px |
| `success` | `status.success.bg` (#0F2A1B) | `status.success.text` (#BBF7D0) | none |
| `warning` | `status.warning.bg` (#2A1F0A) | `status.warning.text` (#FDE68A) | none |
| `danger` | `status.danger.bg` (#2A0F0F) | `status.danger.text` (#FECACA) | none |
| `outline` | transparent | `text.primary` | `border.default` 1px |

### 5.2 Badge（小數字 / 通知點）

| Type | 樣式 |
|------|------|
| Dot | 6×6 圓點，`radius.full`，`text.primary`（純白） |
| Numeric | min-w 16，h 16，padding 0 4，`type.body.xs`，`radius.full`，`status.danger` bg + 白字 |
| Cap (`99+`) | 同 numeric，文字 `99+` |

### 5.3 Chip（可關閉）

```
 ┌─────────────────┐
 │ Label        ✕ │
 └─────────────────┘
 - 同 tag.md，右側 12px ✕ icon button
 - hover ✕ → text.primary，bg surface.hover
```

---

## 6. Avatar

| Size | 值 | Font (initials) |
|------|-----|----------------|
| `xs` | 20px | 10px / 600 |
| `sm` | 24px | 11px / 600 |
| `md`（預設） | 32px | 13px / 600 |
| `lg` | 40px | 15px / 600 |
| `xl` | 56px | 20px / 600 |
| `2xl` | 80px | 28px / 600 |

| 屬性 | 值 |
|------|-----|
| radius | `radius.full` |
| 預設 bg | `surface.elevated` |
| 預設 text | `text.primary` |
| border（多人重疊時） | 2px `canvas.base`（製造分離感） |

### 6.1 Avatar Group

```
 ◯ ◯ ◯ ◯ +5
 - 重疊 -8px（md size）
 - 顯示前 4 個，第 5 個改為 "+N" chip（同 size，bg surface.elevated，font 11px）
 - 各 avatar 加 2px canvas.base 邊框分隔
```

### 6.2 Avatar with Status Dot

```
 ┌─────┐
 │ AB  ●  ← 6px 狀態點，右下角
 └─────┘
 - online: status.success
 - busy: status.danger
 - away: status.warning
 - offline: text.disabled
 - 外圍 2px canvas.base 邊框
```

---

## 7. Card

Grok 卡片：低調、銳利、無陰影、靠 surface + hairline 切分。

### 7.1 Variants

| Variant | bg | border | radius |
|---------|-----|--------|--------|
| `default` | `surface.default` | `border.hairline` 1px | `radius.md` |
| `flat` | transparent | `border.hairline` 1px | `radius.md` |
| `elevated` | `surface.default` | `border.default` 1px（hover 切到 `border.strong`，無發光） | `radius.md` |
| `interactive` | `surface.default` | `border.hairline` 1px | `radius.md` |

### 7.2 Anatomy

```
┌────────────────────────────────────┐
│ [Eyebrow?]                         │  ← 12px label，optional
│                                    │
│ Heading                            │  ← type.heading.lg
│ Description                        │  ← type.body.md / text.secondary
│                                    │
│ [Body content]                     │
│                                    │
│ ─── (border.subtle hairline)  ──── │  ← optional footer divider
│ Footer / Action                    │  ← type.body.sm
└────────────────────────────────────┘
```

### 7.3 Padding

| Size | padding |
|------|---------|
| `sm` | 16px |
| `md`（預設） | 24px |
| `lg` | 32px |
| `xl` | 48px |

### 7.4 Interactive Card

```
 - cursor: pointer
 - transition: background 180ms, border 180ms
 - hover: bg → surface.hover, border → border.default
 - focus: outline 2px text.primary + offset 2px（純線條，無發光）
 - active: bg → surface.active
 - 不做 translate / scale
```

### 7.5 Bento Grid Card

Grok 風格常用「Bento」格狀展示（仿 Apple WWDC、X premium）：
- 不規則尺寸（1×1、2×1、2×2 cells）
- 每格邊框 1px `border.hairline`
- 內部允許大字 + icon + 視覺元素混搭
- 跨格時 gap 16px

---

## 8. Tooltip

| 屬性 | 值 |
|------|-----|
| bg | `text.primary` (#FAFAFA) |
| text | `text.inverse` (#0A0A0A) |
| font | `type.body.xs` |
| padding | 6px 10px |
| radius | `radius.xs` |
| max-width | 280px |
| arrow | 6px 三角，同 bg |
| delay open | 400ms |
| delay close | 100ms |
| z-index | `z.popover` |

> 動畫：fade + 4px slide（依方向），`motion.duration.fast`。

---

## 9. Popover

| 屬性 | 值 |
|------|-----|
| bg | `canvas.overlay` |
| border | `border.hairline` 1px |
| radius | `radius.lg` (8px) |
| padding | 16px |
| min-width | 240px |
| max-width | 400px |
| z-index | `z.popover` |
| arrow | 可選，8px 三角，bg + border 雙層繪製 |

```
 結構：
 [Title]            ← type.heading.sm
 [Description]      ← type.body.sm + text.secondary
 [Content]
 [Footer actions]   ← 右對齊 button group
```

---

## 10. Modal / Dialog

### 10.1 Backdrop

```
 - bg: rgba(0, 0, 0, 0.7)
 - backdrop-filter: blur(8px) saturate(0.6)
 - z-index: z.overlay
 - 動畫：fade in 180ms
```

### 10.2 Modal Container

| Size | max-width |
|------|-----------|
| `sm` | 420px |
| `md`（預設） | 560px |
| `lg` | 720px |
| `xl` | 960px |
| `full` | calc(100vw - 64px) |

| 屬性 | 值 |
|------|-----|
| bg | `canvas.overlay` |
| border | `border.hairline` 1px |
| radius | `radius.lg` (8px) |
| padding | 0（內部用 sub-section 自行處理） |
| max-height | calc(100vh - 80px) |
| z-index | `z.modal` |

### 10.3 Anatomy

```
┌────────────────────────────────────┐
│ [Eyebrow?]                       ✕ │  ← 24px padding，header 高 64px
│ Title                              │  ← type.heading.lg
├────────────────────────────────────┤  ← border.hairline
│                                    │
│ [Body]                             │  ← padding 24px，可捲動
│                                    │
├────────────────────────────────────┤  ← border.hairline
│              [Cancel] [Confirm]    │  ← footer 高 72px，padding 24px
└────────────────────────────────────┘
```

### 10.4 Mobile（< 640px）

- 改為 `Bottom Sheet`：`fixed bottom-0`，`rounded-t-lg`，從底部上滑進場
- 全寬，max-height 90vh
- 頂部 4×40 拖曳指示條（`border.strong` bg）

### 10.5 動畫

| Phase | Backdrop | Modal |
|-------|----------|-------|
| Enter | fade 0→1 (180ms) | scale 0.96→1 + fade (280ms ease.out) |
| Exit | fade 1→0 (120ms) | scale 1→0.98 + fade (120ms ease.in) |

---

## 11. Toast / Snackbar

```
 ┌──────────────────────────────────────┐
 │ [icon] Title                       ✕ │
 │        Description                   │
 │        [Action?]                     │
 └──────────────────────────────────────┘
```

| 屬性 | 值 |
|------|-----|
| width | 360px |
| min-height | 48px |
| bg | `canvas.overlay` |
| border | `border.hairline` 1px |
| border-left | 3px（依 variant：accent / status） |
| radius | `radius.md` |
| padding | 12px 16px |
| z-index | `z.toast` |
| 顯示位置 | bottom-right，距邊 24px |
| 堆疊間距 | 12px |
| 自動消失 | 5s（success / info），8s（warning），不自動消失（danger） |

### 11.1 Variants

| Variant | left border | icon |
|---------|-------------|------|
| `info` | `text.primary` | ℹ |
| `success` | `status.success` | ✓ |
| `warning` | `status.warning` | ⚠ |
| `danger` | `status.danger` | ✕ |
| `loading` | `text.primary` | spinner |

---

## 12. Tabs

### 12.1 Underline（預設）

```
  Tab 1     Tab 2     Tab 3
 ─────                       ← 2px underline，text.primary（active）
 ───────────────────────────  ← 1px hairline，border.hairline（base line）
```

| 屬性 | 值 |
|------|-----|
| Tab height | 40px |
| Tab padding-x | 16px |
| 字 | `type.label.md` |
| Default text | `text.secondary` |
| Hover text | `text.primary` |
| Active text | `text.primary` |
| Active underline | 2px `text.primary`（純白） |
| Underline animate | `transform`，`motion.duration.fast` |

### 12.2 Pill

```
 ┌────┐ ┌────┐ ┌────┐
 │Tab1│ │Tab2│ │Tab3│
 └────┘ └────┘ └────┘
 - 同 button.ghost，active 為 surface.elevated bg
 - 容器 bg: surface.default, padding 4px, radius.sm
```

### 12.3 Vertical Tabs

```
 │ Tab 1     │
 │ Tab 2  ←  │  active 左側 2px text.primary
 │ Tab 3     │
 - 用於 Settings、文件側邊導航
```

---

## 13. Breadcrumb

```
 Home  /  Section  /  Sub  /  Current
```

| 元素 | 樣式 |
|------|------|
| 連結 | `type.body.sm` + `text.secondary`，hover → `text.primary` |
| 目前頁 | `type.body.sm` + `text.primary` |
| 分隔符 | `/`，`text.tertiary`，左右 8px |
| 高度 | 24px |

---

## 14. Pagination

```
 [<]  1  2  [3]  4  5  ...  20  [>]
```

| 元素 | 大小 | 字 | 預設 | Active |
|------|------|----|------|--------|
| 數字按鈕 | 32×32 | `type.body.sm` | `text.secondary`，hover surface.hover | bg `text.primary`, text `text.inverse` |
| Prev / Next | 32×32 | icon 16px | 同上 | — |
| 省略號 | 32×32 | `…` | `text.tertiary` | — |

> Disabled prev/next：`opacity: 0.4` + `cursor: not-allowed`。

---

## 15. Progress / Skeleton / Spinner

### 15.1 Linear Progress

```
 ━━━━━━━━━━━━━━━━━━━━  ← track：surface.elevated，2px height
 ━━━━━━━━━━            ← bar：text.primary（純白）
```

| 屬性 | 值 |
|------|-----|
| height | 2px（細）/ 4px（預設） |
| radius | `radius.full` |
| 不確定模式 | infinite linear，bar 從左滑到右循環，`motion.duration.crawl × 4` |

### 15.2 Skeleton

```
 - bg: surface.default（純色，無漸層）
 - 動畫：opacity 0.4 ↔ 1.0 交替，1.4s ease.standard infinite
 - radius: 同被替代元素（text → 4px，avatar → full，card → md）
 - 高度：依文字行高（16/20/24px 三種預設）
 - 規則：禁止 shimmer 漸層動畫，改為純粹 opacity 呼吸
```

### 15.3 Spinner

```
 - 圓形 SVG，stroke 1.5px
 - 旋轉 360°，1s linear infinite
 - 預設色：currentColor（繼承文字色）
 - 尺寸：12 / 16 / 20 / 24 / 32
```

> Loading 按鈕：spinner 16px + 文字隱藏（覆蓋層）。

---

## 16. Code Block / Inline Code

### 16.1 Inline Code

| 屬性 | 值 |
|------|-----|
| font | `font.mono` + `type.mono.sm` |
| bg | `surface.elevated` |
| color | `text.primary` |
| padding | 1px 6px |
| radius | `radius.xs` |
| 邊框 | none |

### 16.2 Block Code

```
┌──────────────────────────────────────────┐
│ [Tab: filename.ts]                  [📋] │  ← 可選 header
├──────────────────────────────────────────┤
│ 1   import { foo } from 'bar';          │
│ 2   const x = 1;                         │
│ 3   ...                                  │
└──────────────────────────────────────────┘
```

| 屬性 | 值 |
|------|-----|
| bg | `canvas.sunken` |
| border | `border.hairline` 1px |
| radius | `radius.md`（無 header）/ 上下分明（有 header） |
| padding | 16px 20px |
| font | `type.mono.md` |
| line-number | `text.tertiary`，select 時不選取（`user-select: none`） |
| 主題 | 同 X / Vercel 風暗色（建議：Vesper / Tokyo Night Storm） |

### 16.3 Toolbar

```
 - 右上角：Copy 按鈕（icon-only ghost button），點擊後 200ms 顯示「Copied」chip
 - 多檔分頁：Tab 風格切換，每個 tab 為 filename
 - 行號：選擇性顯示
```

---

## 17. Kbd / Shortcut

```
 Press  ⌘ K  to open
```

| 屬性 | 值 |
|------|-----|
| bg | `surface.elevated` |
| border | `border.hairline` 1px (top + left highlight) |
| radius | `radius.xs` |
| padding | 1px 6px |
| min-width | 20px |
| height | 20px |
| font | `font.mono` 11px / 500 |
| color | `text.secondary` |

> 多鍵組合：`⌘` `+` `K` 三個 kbd，間距 4px，無 + 號。

---

## 18. Divider

| 類型 | 樣式 |
|------|------|
| 水平實線 | 1px `border.hairline`，全寬 |
| 水平虛線 | 1px dashed `border.subtle` |
| 垂直 | 1px `border.hairline`，高度由父容器決定 |
| 帶文字 | `─── OR ───`，文字 `type.body.xs` + `text.tertiary`，左右各 16px |
| 雙線（Hero 區用） | 兩條 1px hairline，間距 4px |

---

## 19. Eyebrow

Grok 標誌性元素。

```
 01 / FOUNDATIONS / COLOR
 ───────────────────────
 (heading content here)
```

| 屬性 | 值 |
|------|-----|
| font | `font.mono` + `type.label.sm` |
| color | `text.tertiary` |
| transform | `uppercase` |
| letter-spacing | 0.08em |
| margin-bottom | 12px |
| 分隔符 | ` / `（前後各 1 空格） |

### 19.1 Variants

| Variant | 樣式 |
|---------|------|
| `plain` | 純文字 |
| `numbered` | 起頭 `01` 數字編號 |
| `dotted` | 起頭加 `●` 6px 圓點，`text.primary`（純白） |
| `with-line` | 後方延伸 `border.hairline` 至父容器寬度 |

---

## 20. Marquee

跑馬燈，常用於 Logo wall 或文字流動。

```
 [Logo1]  [Logo2]  [Logo3]  [Logo4]  [Logo5]  →
```

| 屬性 | 值 |
|------|-----|
| 速度 | 30s / 一輪 |
| 動畫 | `transform: translateX(0 → -50%)` linear infinite |
| Hover | 暫停（`animation-play-state: paused`） |
| Mask | 左右兩端 24px solid `canvas.base` 同色蓋片（**禁止 linear-gradient fade**） |
| 容器 | overflow hidden，子元素 `flex shrink-0` |

---

## 元件實作優先序

1. Button、Input、Card、Tag — 構成 80% 介面
2. Modal、Dropdown、Tooltip、Toast — 互動骨幹
3. Tabs、Pagination、Breadcrumb — 導航類
4. Code Block、Kbd、Eyebrow — Grok 風格標誌元件
5. Skeleton、Spinner、Progress — 狀態指示
6. Marquee、Bento Card — Hero / 行銷頁專用

---

**版本**：v1.0
**最後更新**：2026-05-02
