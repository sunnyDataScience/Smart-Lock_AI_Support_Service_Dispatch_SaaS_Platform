# 02_Patterns — xAI Grok 風格 模式規格

> 模式層（Molecules / Organisms）。把 `01_components_spec.md` 的元件組合成可重用區塊。
> 模式不綁定特定頁面，但有明確的使用情境與互動規則。

---

## 模式分類（v1.1 校準）

依 x.ai 實況分為兩類：

| 類別 | 模式 | 使用情境 |
|------|------|---------|
| **🎯 Core**（x.ai 主站常用） | Top Nav / Hero / Stats Strip / Feature Triplet / Logo Wall / FAQ / CTA Block / Footer (minimal) | x.ai/、x.ai/api、x.ai/company、x.ai/news/* |
| **🧩 Extension**（子產品 / 子站使用） | Sidebar Nav / Bento Grid / Pricing Table / Data Table / Empty State / Form Section / Chat Conversation / Command Palette / Notification Center / Compare Slider / Code Demo Panel / Marquee Banner | console.x.ai、docs.x.ai、grok.com、Settings |

**規則**：
- 主行銷站 (x.ai/*) 嚴格使用 Core 模式維持品牌極簡
- 子產品 / Console / Docs 可組合 Extension 模式增加功能性
- 在同一頁面中混用兩類時，視覺上應有明確區隔（容器、padding 或 hairline）

---

## 目錄

1. [Top Navigation Bar](#1-top-navigation-bar)
2. [Hero Section](#2-hero-section)
3. [Bento Grid Showcase](#3-bento-grid-showcase)
4. [Feature Triplet](#4-feature-triplet)
5. [Logo Wall](#5-logo-wall)
6. [Pricing Table](#6-pricing-table)
7. [FAQ Accordion](#7-faq-accordion)
8. [CTA Block](#8-cta-block)
9. [Footer](#9-footer)
10. [Sidebar Navigation](#10-sidebar-navigation)
11. [Data Table](#11-data-table)
12. [Empty State](#12-empty-state)
13. [Form Section](#13-form-section)
14. [Stats Strip](#14-stats-strip)
15. [Chat Conversation](#15-chat-conversation)
16. [Command Palette](#16-command-palette)
17. [Notification Center](#17-notification-center)
18. [Compare Slider](#18-compare-slider)
19. [Code Demo Panel](#19-code-demo-panel)
20. [Marquee Banner](#20-marquee-banner)

---

## 1. Top Navigation Bar

x.ai 實際導航：高 64–80px、純黑底、左 logo 中 nav（少量 5–6 項）右 1 個 CTA。**無 backdrop blur、無透明、無多 CTA**。

### 1.1 結構（x.ai 實況版）

```
┌──────────────────────────────────────────────────────────────────┐
│ [✕logo]    Grok  API  Company  Colossus  Careers  News  [Try Grok ↗]│
└──────────────────────────────────────────────────────────────────┘
                                                            ↑
                                       無 border、純黑（#000）滿底
```

### 1.2 規格

| 屬性 | 值 |
|------|-----|
| height | 64px (mobile) / 72px (tablet) / 80px (desktop) |
| bg | `canvas.base` (純 #000，**不透明**) |
| border-bottom | 無（x.ai 不用分隔線，靠 padding 區隔） |
| padding | 0 24px (mobile) / 0 32px (tablet) / 0 48px (desktop) |
| position | `sticky top-0` |
| z-index | `z.sticky` |
| Logo | 高 20px（mobile）/ 24px（desktop），**單一 ✕ 字符或黑洞圓**，純白 |
| Nav 對齊 | logo 左對齊；nav 中央偏左群組；CTA 右對齊 |
| Nav link | `type.label.md`，`text.primary`（**白色，非 secondary**），hover `text.secondary`，間距 24px (tablet) / 32px (desktop) |
| Active link | 無下方 underline（x.ai 實況），改 `text.tertiary` 標示 |
| Right CTA | 單一 `Button.primary`（白底黑字 pill） + 後綴 `↗`，文字 `Try Grok` |
| 「+ Sign in」 | 移除（x.ai 主站無 Sign in 按鈕，登入入口在 grok.com / console.x.ai） |

### 1.3 真實 Nav 項目（依 x.ai/ 實況）

| 連結文字 | URL | 用途 |
|---------|-----|------|
| `Grok` | grok.com | 消費端產品（外連） |
| `API` | x.ai/api | API 平台 |
| `Company` | x.ai/company | 公司 |
| `Colossus` | x.ai/colossus | 訓練叢集 |
| `Careers` | x.ai/careers | 招募 |
| `News` | x.ai/news | 新聞 |

### 1.4 Mobile 行為

- 中央 nav 隱藏，改右側 hamburger（IconButton.ghost，24px Menu icon）
- 點擊展開全螢幕 overlay（bg `canvas.base`，列表 `type.heading.lg`）
- Overlay 進場：fade + translateY(-8px) → 0，280ms ease.out

### 1.5 Variants

| Variant | 差異 |
|---------|------|
| `default`（x.ai 主站） | 純黑、無分隔線、單 CTA（如上述） |
| `console` | 切換到 console.x.ai 變體：左 logo + breadcrumb，右 user avatar；強調色仍為白色（不啟用霓虹） |
| `docs` | 切換到 docs.x.ai 變體：加 search input（中央，width 320px），右 GitHub icon |
| `with-banner` | 上方加一條 32px News banner（最新公告，§20，僅在重大發佈時啟用） |

---

## 2. Hero Section

x.ai 風 Hero：**單句宣言式巨大標題、無 eyebrow、無副標（或極短一行）、單一純文字 CTA、純黑無漸層**。

### 2.1 結構（x.ai 實況版）

```
 (上方留白 space.section.2xl = 192px)



           Understand the universe.



           Try Grok ↗



 (下方留白 space.section.xl = 160px)

 (純黑背景，無 spotlight、無星空、無 dot grid)
```

> 注意：x.ai/ 主頁 Hero 只有一行宣言句 + 一個 CTA，**沒有副標、沒有 eyebrow、沒有特效背景**。極端 minimalism。

### 2.2 規格

| 區塊 | 屬性 | 值 |
|------|------|-----|
| Container | min-height | 90vh（desktop）/ 80vh（mobile） |
| Container | padding-y | `space.section.2xl` (192px) ≥ 1440px / `space.section.xl` (160px) desktop / `space.24` (96px) mobile |
| Container | text-align | left（x.ai 偏好左對齊，**非置中**） |
| Container | max-width | none（標題吃滿 container） |
| Eyebrow | **不使用**（x.ai 實況） | — |
| 主標題 | `type.display.4xl` (160px) ≥ 1440px / `type.display.3xl` (120px) desktop / `type.display.2xl` (96px) tablet / `type.display.xl` (72px) mobile | `text.primary` |
| 主標題 | font-weight | 600（不到 700，避免過重） |
| 主標題 | letter-spacing | -0.05em（更緊縮） |
| 主標題 | max-width | 16em（允許換行 1–2 行） |
| 主標題 | margin-bottom | 48px（直接接 CTA，不放副標） |
| 副標題 | **可選**，極短，僅 1 行 | `type.body.lg` + `text.secondary`，max-width 28em |
| CTA | 單一按鈕：`Button.primary`（白底黑字 pill）+ 後綴 `↗`，size `lg` 或 `xl` | — |
| CTA group | 不使用雙 CTA（x.ai 實況） | — |
| 背景 | 純 `canvas.base` (#000)，**不加任何特效** | — |
| 旁邊視覺 | 可選右側放抽象幾何圖（黑洞、線條、3D 物件），但主頁不用 | — |

### 2.3 動畫進場

```
 序列入場（極簡，總時長 800ms）：
 1. 主標題：fade + translateY(12px) → 0，0ms 觸發，480ms ease.out
 2. CTA：同上，280ms 觸發，280ms

 不做：眉題動畫、背景光暈動畫、視差
 reduced motion 時：直接顯示，跳過動畫
```

### 2.4 Variants

| Variant | 用途 |
|---------|------|
| `manifesto`（**x.ai 預設**） | 單句巨大標題 + 單 CTA，純黑底，無副標 |
| `with-subtitle` | 加一行短副標於標題下方（Company / About 頁） |
| `with-cta-pair` | 雙 CTA：主白底黑字 + 次純文字 + ↗（API / 產品介紹頁） |
| `with-visual` | 右側放抽象幾何圖、黑洞、3D 渲染（產品介紹頁） |
| `with-image` | 右側放裝置截圖或抽象視覺，使用 grid 1fr/1fr |
| `with-terminal` | 右側放 Code Demo Panel（§19，API/Docs 頁專用） |
| `centered`（**節制使用**） | 文字置中 + 弱光暈，僅用於品牌時刻或 404 |

---

## 3. Bento Grid Showcase

仿 Apple WWDC / X premium 的 Bento 格狀展示。

### 3.1 結構

```
┌──────────────┬─────────┬─────────┐
│              │         │         │
│   2×2        │  1×1    │  1×1    │
│              │         │         │
│              ├─────────┴─────────┤
│              │                   │
├──────────────┤      2×1          │
│              │                   │
│   1×1        ├──────┬───────────┤
│              │      │           │
│              │ 1×1  │   1×2     │
└──────────────┴──────┴───────────┘
```

### 3.2 規格

| 屬性 | 值 |
|------|-----|
| 容器 | `grid grid-cols-12 gap-4 lg:gap-6` |
| 每個 Card | `border.hairline` 1px，`radius.md`，`canvas.raised` bg |
| 標準尺寸 | 1×1 = `col-span-3 row-span-1`（共 4 列）|
| 大尺寸 | 2×1 = `col-span-6`，2×2 = `col-span-6 row-span-2` |
| 高 | `min-h-[240px]` 基礎，2×2 = `min-h-[496px]` |
| Padding | 24–32px |

### 3.3 內容類型

| 類型 | 內容 |
|------|------|
| Headline Card | 大字標題（`type.display.sm`）+ 副標 + 視覺元素 |
| Stat Card | 數字（`type.display.md` mono）+ 標籤 + sparkline |
| Visual Card | 全幅插圖 / 動畫，最少文字 |
| Code Card | 內嵌 mini code block + 結果展示 |
| Quote Card | 大型引號 + 引言 + 作者 |
| Comparison Card | 左右對比（before/after） |

### 3.4 Hover 行為

```
 - bg: surface.default → surface.hover
 - border: border.hairline → border.default
 - 內部視覺元素：可加細微 transform（建議 scale 1.0 → 1.02，僅限 visual 元素本身，卡片本體不動）
 - 不做 elevation 改變（保持平面感）
```

### 3.5 Mobile 行為

- 退化為單欄 stack
- 每張卡 min-height 200px，固定間距 16px

---

## 4. Feature Triplet

3 個並列功能介紹卡，極常用於 Landing 中段。

### 4.1 結構

```
┌─────────────┬─────────────┬─────────────┐
│ [icon]      │ [icon]      │ [icon]      │
│             │             │             │
│ Feature 1   │ Feature 2   │ Feature 3   │
│ Description │ Description │ Description │
│             │             │             │
│ Learn more →│ Learn more →│ Learn more →│
└─────────────┴─────────────┴─────────────┘
```

### 4.2 規格

| 屬性 | 值 |
|------|-----|
| 容器 | `grid grid-cols-1 md:grid-cols-3 gap-px bg-border-hairline` |
| Card bg | `canvas.base`（讓 gap-px 形成分隔線效果）|
| Card padding | 32px |
| Icon | 24px stroke 1.5，`text.primary` |
| Icon margin-bottom | 24px |
| 標題 | `type.heading.xl` |
| 標題 margin-bottom | 12px |
| 描述 | `type.body.md` + `text.secondary` |
| 描述 margin-bottom | 24px |
| 連結 | `Button.link` + 後綴 `→` icon |

### 4.3 Variant：4 / 6 個

- 4 個：`md:grid-cols-2 lg:grid-cols-4`
- 6 個：`md:grid-cols-2 lg:grid-cols-3`，分兩 row

### 4.4 Variant：with-divider-only

無背景色，僅以 `border.hairline` 縱向分隔線分隔三欄（適合純文字段落）。

---

## 5. Logo Wall

客戶 / 合作夥伴 logo 牆。Grok 風格採取靜止排列或 marquee 流動。

### 5.1 Static Grid

```
┌────────┬────────┬────────┬────────┬────────┐
│ Logo 1 │ Logo 2 │ Logo 3 │ Logo 4 │ Logo 5 │
├────────┼────────┼────────┼────────┼────────┤
│ Logo 6 │ Logo 7 │ Logo 8 │ Logo 9 │ Logo10 │
└────────┴────────┴────────┴────────┴────────┘
```

| 屬性 | 值 |
|------|-----|
| 容器 | `grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-px bg-border-hairline` |
| 單格 | aspect-ratio 3/2，`canvas.base`，flex center |
| Logo | 高 24–32px，monochrome，`opacity: 0.6`，hover `opacity: 1` |
| 顏色 | 全部反白為 `text.secondary`，hover → `text.primary` |

### 5.2 Marquee 變體

採用 §20 Marquee Banner，logo 連續橫向流動，速度 40s / 一輪。

### 5.3 上方標題

```
 [eyebrow.with-line] TRUSTED BY ─────
 type.heading.lg "Powering teams at"
```

---

## 6. Pricing Table

### 6.1 結構

```
┌────────────┬────────────┬────────────┐
│            │ [POPULAR]  │            │
│ Free       │ Pro        │ Enterprise │
│            │            │            │
│ $0         │ $20/mo     │ Custom     │
│ /forever   │ per user   │            │
│            │            │            │
│ ✓ Feat 1   │ ✓ Feat 1   │ ✓ Feat 1   │
│ ✓ Feat 2   │ ✓ Feat 2   │ ✓ Feat 2   │
│            │ ✓ Feat 3   │ ✓ Feat 3   │
│            │            │ ✓ Feat 4   │
│            │            │            │
│ [Sign up]  │ [Get Pro]  │ [Contact]  │
└────────────┴────────────┴────────────┘
```

### 6.2 規格

| 屬性 | 值 |
|------|-----|
| 容器 | `grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-6` |
| Card | Card.default，padding 32px |
| 推薦版 Card | border 由 hairline 改為 `text.primary` 1.5px（**無發光**） |
| Plan 名稱 | `type.heading.xl` |
| Price | `type.display.lg` font-mono，tabular-nums |
| Price 後綴 | `type.body.sm` + `text.tertiary`（`/mo`、`per user`）|
| Feature list | `type.body.md`，icon 16px Check `text.primary`（不用綠色），間距 12px |
| Disabled feature | icon 改 `–`，文字 `text.disabled`，加刪除線 |
| CTA | 全寬 button.lg，間距距離卡頂 32px |
| Popular Badge | 卡頂中央，Tag.accent，文字 `MOST POPULAR` uppercase |

### 6.3 Toggle（月 / 年）

```
 [Monthly] [Annual (-20%)]
 - Switch 風格，水平排列
 - Annual 後綴折扣 chip：surface.elevated bg + text.primary text
 - 切換時數字 fade 替換，180ms
```

### 6.4 Compare Table（多功能對比）

```
 ┌─────────┬──────┬─────┬──────┐
 │ Feature │ Free │ Pro │ Ent. │
 ├─────────┼──────┼─────┼──────┤
 │ ...     │  ✓   │  ✓  │  ✓   │
 │ ...     │  –   │  ✓  │  ✓   │
 └─────────┴──────┴─────┴──────┘
 - 表格樣式同 §11 Data Table
 - Group rows 用 type.label.sm 分組標題（uppercase mono）
```

---

## 7. FAQ Accordion

### 7.1 結構

```
 Q: How does Grok work?                       [+]
 ─────────────────────────────────────────────────
 Q: What model is it based on?                [+]
 ─────────────────────────────────────────────────
 Q: Is my data private?                       [-]
 ─────────────────────────────────────────────────
   Answer paragraph here. Multiple lines if needed.

 ─────────────────────────────────────────────────
```

### 7.2 規格

| 屬性 | 值 |
|------|-----|
| Item border-bottom | 1px `border.hairline` |
| Question 高 | 80px（min-height） |
| Question padding | 24px 0 |
| Question typography | `type.heading.md` |
| Question hover bg | none（保持極簡） |
| Question hover text | `text.primary`（預設 secondary） |
| Toggle icon | 16px Plus → Minus，旋轉 45°（cross 風）|
| Answer padding | 0 0 24px 0 |
| Answer typography | `type.body.md` + `text.secondary` |
| Answer max-width | 64ch |
| 動畫 | grid-template-rows 0fr → 1fr，280ms ease.standard |

### 7.3 Variant：bordered

```
 - 每 item 為獨立 Card.flat，間距 8px
 - 用於 Pricing 頁的 FAQ 區段
```

---

## 8. CTA Block

頁尾或區段尾的轉換區塊。

### 8.1 Centered（最常用）

```
                  [eyebrow.dotted GET STARTED]

           Ready to ship faster?

           Join thousands of teams using Grok
           to build at the speed of thought.

                  [Try Grok free]  [Talk to sales]


             ──── (純黑底，無背景特效) ────
```

| 屬性 | 值 |
|------|-----|
| 容器 | `space.section.xl` padding-y |
| 背景 | `canvas.base` 純黑（**禁止 spotlight 與漸層**） |
| 標題 | `type.display.lg` |
| 副標 | `type.body.lg` + `text.secondary`，max-width 32em |
| CTA | flex gap 12px，wrap，置中 |

### 8.2 Banner

```
┌──────────────────────────────────────────────────────────┐
│  Ready to ship faster?                  [Try free]   →  │
│  Join thousands building with Grok.                      │
└──────────────────────────────────────────────────────────┘
```

| 屬性 | 值 |
|------|-----|
| Card.flat，padding 48px |
| border 1px `border.hairline` |
| 左：標題 + 副標 |
| 右：CTA 按鈕 |
| 背景：`bg.dot.dim` |

---

## 9. Footer

> **v1.1 校準**：x.ai 主站使用**極簡一行式 Footer**（單列 logo + nav links + copyright），不使用多欄 link wall。多欄 wall 改為「Variant: rich」備用。

### 9.1 預設結構（x.ai 實況版 / 極簡）

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│ [✕]   Grok  API  Company  Colossus  Careers  News  Privacy ·  │
│                                                                   │
│              Terms   © 2026 xAI Corp.            [X]  [GitHub]   │
└──────────────────────────────────────────────────────────────────┘
```

### 9.2 規格（預設 / minimal）

| 屬性 | 值 |
|------|-----|
| bg | `canvas.base` (#000，與頁面同色) |
| border-top | **無**（x.ai 不用，靠 padding 區隔） |
| padding-y | 64px (mobile) / 96px (desktop) |
| padding-x | 同 nav |
| Logo | 高 20px，左對齊 |
| Layout | flex / 中段是 nav links inline，右側 social icons |
| Nav link | `type.body.sm` + `text.secondary`，hover `text.primary`，間距 24px |
| Copyright | `type.body.sm` + `text.tertiary`，可放在最後 |
| Social icons | 16px `text.secondary`，hover `text.primary`，間距 16px |
| Mobile | 全部換行為 stack，每行 1–2 個 link，置中對齊 |

### 9.3 Variant：rich（多欄連結 wall — 用於 Docs / API / Careers 頁）

```
┌──────────────────────────────────────────────────────────────────┐
│ [✕logo]                                                           │
│                                                                   │
│ Products      Company       Resources     Legal                  │
│ Grok          About         Docs          Privacy                │
│ API           Careers       News          Terms                  │
│ Colossus      Press         Status        Cookies                │
│                                                                   │
│ ───────────────────────────────────────────────────────────────  │
│ © 2026 xAI Corp.                          [X] [GitHub] [YouTube]│
└──────────────────────────────────────────────────────────────────┘
```

| 屬性 | 值 |
|------|-----|
| bg | `canvas.base` 或 `canvas.sunken` |
| padding-y | `space.section.lg` (128px) |
| Logo 區 margin-bottom | 64px |
| Link grid | `grid grid-cols-2 md:grid-cols-4 gap-8 lg:gap-12` |
| Group title | `type.label.sm` uppercase + `text.tertiary`，margin-bottom 16px |
| Link | `type.body.sm` + `text.secondary`，hover `text.primary`，行高 32px |
| Bottom row | margin-top 64px，flex justify-between，border-top `border.hairline` padding-top 32px |

---

## 10. Sidebar Navigation

### 10.1 結構（Console / Docs）

```
┌──────────────┐
│ [logo]       │
├──────────────┤
│ ⌕ Search     │   ← Cmd+K trigger
├──────────────┤
│ ─ Section 1  │   ← group label, type.label.sm uppercase
│  ◉ Item 1    │   ← active item
│  ○ Item 2    │
│  ○ Item 3    │
├──────────────┤
│ ─ Section 2  │
│  ○ Item 4    │
│  ○ Item 5    │
├──────────────┤
│ [Avatar] Me  │   ← bottom user menu
└──────────────┘
```

### 10.2 規格

| 屬性 | 值 |
|------|-----|
| 寬 | 240px（展開）/ 56px（收合） |
| bg | `canvas.raised` |
| border-right | 1px `border.hairline` |
| padding | 0 |
| Logo 區 | h 64px，padding 0 24px，border-bottom hairline |
| Search | h 36px，margin 12px 16px，bg `canvas.sunken`，radius `radius.sm`，icon + placeholder |
| Group label | `type.label.sm` uppercase + `text.tertiary`，padding 12px 24px 8px |
| Item | h 36px，padding 0 24px，flex items-center gap 12px |
| Item icon | 16px |
| Item text | `type.body.sm` |
| Item default | `text.secondary`，hover `surface.hover` + `text.primary` |
| Item active | `text.primary` + 左側 2px `text.primary` 邊條 + `surface.hover` bg |
| Item with badge | 右側 Tag.sm 顯示 `New` / 數字 |
| Bottom user | h 64px，border-top hairline，padding 12px 16px，hover `surface.hover` |

### 10.3 收合狀態

- 寬 56px，僅顯示 icon
- Hover 時展開 tooltip 顯示 item 名
- Logo 區改為 32×32 logo mark
- Group label 隱藏，但 group 之間保留 hairline 分隔

---

## 11. Data Table

### 11.1 結構

```
 ┌──────────────────────────────────────────────────────────────────┐
 │ Search...                          [Filter] [Sort] [Add row +]   │
 ├──────────────────────────────────────────────────────────────────┤
 │ ☐  NAME              STATUS   USERS   CREATED       ⋯            │
 ├──────────────────────────────────────────────────────────────────┤
 │ ☐  Project Alpha     ● Active  12     2026-04-01    ⋯            │
 │ ☐  Project Beta      ○ Paused  3      2026-03-22    ⋯            │
 │ ☐  Project Gamma     ● Active  47     2026-02-14    ⋯            │
 ├──────────────────────────────────────────────────────────────────┤
 │ Showing 1–10 of 247       [< Prev]  1  2  3  ...  25  [Next >]  │
 └──────────────────────────────────────────────────────────────────┘
```

### 11.2 規格

| 屬性 | 值 |
|------|-----|
| 容器 | Card.flat，無 padding（border 由表格自處理） |
| Toolbar 高 | 56px |
| Toolbar padding | 0 16px |
| Toolbar border-bottom | 1px `border.hairline` |
| Search | Input.sm，width 280px |
| Header row 高 | 40px |
| Header bg | `surface.default` |
| Header text | `type.label.sm` uppercase + `text.tertiary`，letter-spacing 0.06em |
| Row 高 | 56px |
| Row border-bottom | 1px `border.hairline` |
| Row padding | 0 16px |
| Row hover | bg `surface.hover` |
| Row selected | bg `surface.elevated` + 左側 2px `text.primary` 邊條 |
| Cell font | `type.body.sm` |
| Numeric cell | font-mono + tabular-nums + 右對齊 |
| Status cell | `Tag.sm` |
| Action cell | IconButton.ghost.sm，` ⋯ ` 觸發 dropdown |

### 11.3 Sortable Header

```
 NAME ↕   ← 預設（雙向箭頭，text.tertiary）
 NAME ↑   ← 升冪（text.primary）
 NAME ↓   ← 降冪（text.primary）
```

### 11.4 Empty State

當無資料時，將表格 body 替換為 §12 Empty State。

### 11.5 Density Variants

| Variant | Row 高 |
|---------|-------|
| Compact | 40px |
| Default | 56px |
| Comfortable | 72px |

---

## 12. Empty State

```
              [icon 48px stroke 1.5]

           No projects yet

           Create your first project to start
           building with Grok.

                  [Create project]
```

| 屬性 | 值 |
|------|-----|
| 容器 padding-y | 80–120px |
| text-align | center |
| Icon | 48px，`text.tertiary`，margin-bottom 24px |
| 標題 | `type.heading.lg` + `text.primary` |
| 標題 margin-bottom | 8px |
| 描述 | `type.body.md` + `text.secondary`，max-width 32em |
| 描述 margin-bottom | 32px |
| CTA | Button.md（主要動作） |

### 12.1 Variants

| Variant | 用途 |
|---------|------|
| `default` | 上述標準 |
| `error` | icon `text.tertiary` 改 `status.danger`，加 retry CTA |
| `search-empty` | 「沒有符合的結果」，搭配 Search icon |
| `permission-denied` | 鎖頭 icon，無 CTA 或顯示「Request access」 |

---

## 13. Form Section

複合表單區塊。

### 13.1 結構

```
 ─── ACCOUNT (eyebrow.with-line) ─────────────────

 Profile

 Tell us about yourself.

 ┌─────────────────────────┬─────────────────────┐
 │ Name                    │ [input]             │
 ├─────────────────────────┼─────────────────────┤
 │ Email                   │ [input]             │
 │ We'll never share it.   │                     │
 ├─────────────────────────┼─────────────────────┤
 │ Bio                     │ [textarea]          │
 │ Markdown supported.     │                     │
 └─────────────────────────┴─────────────────────┘

                                        [Save]
```

### 13.2 規格

| 屬性 | 值 |
|------|-----|
| Eyebrow | `Eyebrow.with-line` |
| Section title | `type.display.sm` |
| Section description | `type.body.md` + `text.secondary`，max-width 48em |
| 標題與表單間距 | 48px |
| Form layout | `grid grid-cols-1 md:grid-cols-[280px_1fr] gap-6 md:gap-12` |
| Field row | border-bottom 1px `border.hairline`，padding-y 24px |
| Field label | `type.label.md` + `text.primary` |
| Field hint | `type.body.sm` + `text.tertiary`，margin-top 4px |
| Field input | 右側 max-width 480px |
| Save 按鈕 | 右下角，與最後一個 field 距離 32px |

### 13.3 Inline Form Variant

```
 [Email input]                    [Subscribe →]
 - 單行水平表單，常用於 Newsletter
 - input 寬 320px，按鈕緊鄰右側
```

---

## 14. Stats Strip

```
 ┌──────────────┬──────────────┬──────────────┬──────────────┐
 │ 99.9%        │ 12B          │ 50ms         │ 2,400+       │
 │ uptime SLA   │ requests/day │ p99 latency  │ teams        │
 └──────────────┴──────────────┴──────────────┴──────────────┘
```

| 屬性 | 值 |
|------|-----|
| 容器 | `grid grid-cols-2 md:grid-cols-4 gap-px bg-border-hairline` |
| 單格 | `canvas.base`，padding 32px 24px |
| 數字 | `type.display.md` font-mono tabular-nums |
| 數字色 | `text.primary` |
| 標籤 | `type.body.sm` + `text.tertiary`，margin-top 8px |

### 14.1 Variant：with-trend

```
 99.9% ↗ +0.2%       ← 趨勢箭頭 + 變化量
 uptime SLA
```
- 箭頭 + 變化量：12px font-mono，正數 `status.success`、負數 `status.danger`

---

## 15. Chat Conversation

Grok 對話介面標誌設計。

### 15.1 結構

```
 [User msg]                                    8:42 PM
 ─────────────────────────────────────────────────────
                              ┌──────────────────────┐
                              │ Hey Grok, ...        │
                              └──────────────────────┘

 ─────────────────────────────────────────────────────
 [Grok msg]                                    8:42 PM
 ┌────────────────────────────────────────────────────┐
 │ ◆ Sure, here's...                                  │
 │                                                    │
 │ ```py                                              │
 │ ...                                                │
 │ ```                                                │
 │                                                    │
 │ [↻ Regenerate]  [👍] [👎]  [📋 Copy]              │
 └────────────────────────────────────────────────────┘
```

### 15.2 規格

| 元素 | 樣式 |
|------|------|
| User bubble | 右對齊，max-width 70%，bg `surface.elevated`，padding 12px 16px，radius `radius.md`，文字 `type.body.md` |
| Grok bubble | 左對齊，無 bg（或 `canvas.raised` 全寬），文字 `type.body.md` |
| Avatar / Mark | Grok 訊息開頭加 ✕ 12px `text.tertiary` 字符標記（不顯示頭像，亦不用 ◆） |
| 時間戳 | `type.body.xs` + `text.tertiary`，bubble 上方 4px |
| Action toolbar | bubble 下方 8px，IconButton.ghost.sm 排列，hover 才顯示完整 |
| 串流游標 | 文字結尾 ▌ 閃爍（500ms），結束時消失 |
| 訊息間距 | 24px |

### 15.3 輸入區

```
 ┌────────────────────────────────────────────────────┐
 │ Ask anything...                          [↑ Send]  │
 │ ─────────                                          │
 │ [📎] [/]              [Model: Grok-3 ▼]            │
 └────────────────────────────────────────────────────┘
```

| 屬性 | 值 |
|------|-----|
| Container | `canvas.overlay`，border 1px `border.default`，radius `radius.md`，padding 12px 16px |
| sticky bottom | 24px above bottom edge |
| Textarea | 無邊框，bg transparent，min-h 24px max-h 200px，font `type.body.md` |
| 底部工具列 | 上方 hairline，padding-top 8px，flex justify-between |
| Send button | 右上角 IconButton.primary.sm，無內容時 disabled |
| Hint | `type.body.xs` + `text.tertiary`，下方 8px：「Press ⌘ + Enter to send」 |

---

## 16. Command Palette（⌘K）

### 16.1 結構

```
 ┌────────────────────────────────────────────────────┐
 │ ⌕ Type a command or search...               [Esc] │
 ├────────────────────────────────────────────────────┤
 │ RECENT                                              │
 │  →  Open settings                                   │
 │  →  Switch project                                  │
 ├────────────────────────────────────────────────────┤
 │ NAVIGATION                                          │
 │  ◉  Go to dashboard                       ⌘ D      │
 │  ○  Go to projects                        ⌘ P      │
 │  ○  Go to billing                                   │
 ├────────────────────────────────────────────────────┤
 │ ACTIONS                                             │
 │  +  Create new project                    ⌘ N      │
 │  ✕  Delete current item                             │
 └────────────────────────────────────────────────────┘
```

### 16.2 規格

| 屬性 | 值 |
|------|-----|
| 容器 | width 640px，max-height 480px |
| bg | `canvas.overlay` |
| border | 1px `border.default` |
| radius | `radius.lg` |
| z-index | `z.command` (最高) |
| 位置 | 螢幕中上 25% 處（vertical center 偏上） |
| Backdrop | `rgba(0,0,0,0.5) + blur(8px)` |
| Search input 高 | 56px |
| Search input 字 | `type.body.lg` |
| Group label | `type.label.sm` uppercase + `text.tertiary`，padding 12px 16px |
| Item 高 | 40px |
| Item padding | 0 16px |
| Item icon | 16px，左 |
| Item text | `type.body.sm` |
| Item shortcut | `Kbd` group 右對齊 |
| Item hover / selected | bg `surface.hover` + 左側 2px `text.primary` 邊條 |
| 動畫 | scale 0.96 → 1 + fade，280ms |

### 16.3 Variants

- `compact`：寬 480px，無 group，僅扁平 list
- `with-preview`：寬 800px，左 list 右 preview pane

---

## 17. Notification Center

### 17.1 結構（Popover 形式）

```
 ┌─────────────────────────────────────┐
 │ Notifications        [Mark all read]│
 ├─────────────────────────────────────┤
 │ ● [icon] Title                       │
 │   Description text                   │
 │   2 minutes ago                      │
 ├─────────────────────────────────────┤
 │   [icon] Title                       │
 │   Description                        │
 │   1 hour ago                         │
 ├─────────────────────────────────────┤
 │ [View all notifications →]           │
 └─────────────────────────────────────┘
```

### 17.2 規格

| 屬性 | 值 |
|------|-----|
| 容器 | width 400px，max-height 480px |
| 同 Popover 規格 |
| Header 高 | 48px，padding 0 16px，border-bottom hairline |
| Header title | `type.heading.sm` |
| Mark all read | `Button.link` |
| Item 高 | auto，padding 12px 16px |
| Item border-bottom | 1px `border.subtle` |
| Item unread dot | 6px，`text.primary`，左側絕對定位 |
| Item icon | 16px，依 type 著色（system/security/billing） |
| Footer | h 40px，padding 0 16px，border-top hairline，文字 link 置中 |

---

## 18. Compare Slider

```
 ┌────────────────┬────────────────┐
 │ BEFORE         │      AFTER     │
 │ Image left     ⫶  Image right   │
 │                ⫶                │
 └────────────────┴────────────────┘
                  ↑
            可拖曳分隔線
```

| 屬性 | 值 |
|------|-----|
| 容器 | `relative`，aspect-ratio 16/9 |
| Divider | 2px `text.primary` 縱線 + 中央 32px 圓形 handle（white bg + ↔ icon 黑色） |
| Handle | `radius.full`，1px `border.strong` 邊框（**無發光**），cursor `ew-resize` |
| 角落標籤 | `Tag.outline.sm`，左上 BEFORE / 右上 AFTER |
| 動畫 | divider 跟手指即時，clip-path 過渡 |

---

## 19. Code Demo Panel

Hero / Feature 區常用的 Terminal 風 mock 視窗。

### 19.1 結構

```
 ┌────────────────────────────────────────┐
 │ ●  ●  ●     ~/grok                     │  ← 三色點 macOS 風
 ├────────────────────────────────────────┤
 │ $ grok init my-app                     │
 │ ✓ Created project                      │
 │ ✓ Installed dependencies               │
 │                                        │
 │ $ _                                    │
 └────────────────────────────────────────┘
```

### 19.2 規格

| 屬性 | 值 |
|------|-----|
| 容器 | bg `canvas.sunken`，border 1px `border.hairline`，radius `radius.lg` |
| Title bar 高 | 36px，bg `surface.default`，padding 0 16px |
| 三色點 | 12×12 圓，`#FF5F57` `#FEBC2E` `#28C840`，間距 8px |
| 標題 | `type.body.xs` font-mono + `text.tertiary`，置中 |
| Body | padding 20px 24px，font `type.mono.md` |
| 命令前綴 | `$ `（mono，`text.tertiary`），跟隨命令文字 `text.primary` |
| Output | `text.secondary` |
| 成功 | `✓ ` `status.success` |
| 失敗 | `✕ ` `status.danger` |
| Cursor | 結尾 `▌`，blink 1s |

### 19.3 Variants

- `light-syntax`：用於 light mode，bg #F4F4F5
- `with-tabs`：頂部加 tab bar 切換多檔
- `running`：頂部 dot 改為 spinner
- `with-output-pane`：左 code 右 result 兩欄

---

## 20. Marquee Banner

頂部公告 / 特殊宣傳。

### 20.1 結構

```
   ◆ New: Grok 4 is here, 2× faster.    Read more ↗   ◆ ...
   ←──── 緩慢左滑無限循環 ────→
```

| 屬性 | 值 |
|------|-----|
| 高度 | 32px |
| bg | `canvas.base` 純黑（特殊宣傳改用 `surface.elevated` 純色，**不用霓虹底色**） |
| border-bottom | 1px `border.hairline` |
| 字 | `type.body.sm` + `text.secondary` |
| Item 間隔 | `◆` 圓點 / `•`，前後 24px |
| 動畫 | `translateX 0 → -50%`，30s linear infinite |
| Mask | 左右各 24px solid `canvas.base` 同色蓋片（**禁止漸層 fade**） |
| Hover | 暫停動畫 |
| 關閉按鈕 | 右側 IconButton.ghost.sm，可選 |

---

## 模式組合範例

### Landing 頁
```
1. Top Navigation Bar (transparent variant)
2. Hero Section (with-terminal)
3. Stats Strip
4. Bento Grid Showcase
5. Logo Wall (marquee)
6. Feature Triplet × 2
7. Compare Slider
8. Pricing Table
9. FAQ Accordion
10. CTA Block (centered)
11. Footer
```

### Console 頁
```
1. Top Navigation Bar (console variant)
2. Sidebar Navigation
3. Page header (breadcrumb + title + actions)
4. Stats Strip (smaller version)
5. Data Table
6. Footer (minimal)
```

### Docs 頁
```
1. Top Navigation Bar
2. Sidebar Navigation (docs)
3. Article container (max-width 768px)
4. Code Demo Panel inline
5. Compare blocks
6. Pagination (prev/next chapter)
7. Footer (minimal)
```

---

**版本**：v1.0
**最後更新**：2026-05-02
