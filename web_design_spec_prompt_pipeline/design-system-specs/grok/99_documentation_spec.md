# 99_Documentation — xAI Grok 風格 設計系統使用文件

> 設計系統的「使用說明書」。讓設計師、前端、PM、QA 都能正確操作這套系統。

---

## v1.2 純化摘要（2026-05-03）

> **核心訴求**：禁止霓虹感、漸層色、發光、Star Field 等「AI 感很重」的設計套路。
> 整套系統改為 **純黑 + 純白 + 灰階** 的嚴格單色主義。

### v1.0 → v1.1 → v1.2 演進

| 主題 | v1.0 | v1.1（依 x.ai 校準） | v1.2（**徹底純化**） |
|------|------|------------|----------|
| 主強調色 | 霓虹電光藍 #5B8DEF | 白色為主，電光藍降為子產品變體 | **唯一強調色 = 白色 #FFFFFF**，霓虹完全刪除 |
| Electric / Violet / Cyan / Amber 變體 | 提供 | 保留 electric 為子產品 | **全部刪除** |
| Glow 系統（focus / accent / pulse） | 提供 6 個 token | 保留 | **完全刪除**，focus 改為 `outline 2px solid` |
| 背景 spotlight / radial gradient | bg.spotlight.* 4 個變體 | 保留 marketing-rich 用 | **全部刪除** |
| Star Field（404 / Auth） | 提供 | 保留 | **完全刪除** |
| Marquee fade mask | linear-gradient | 保留 | **改為 24px solid 同色蓋片** |
| Skeleton shimmer | linear-gradient 移動 | 保留 | **改為 opacity 呼吸** |
| Status 色塊 bg | success.bg / warning.bg / danger.bg | 保留 | **刪除色塊背景**，僅保留去飽和 icon 色 |
| 資料圖表配色 | 8 色彩虹 (viz.1–8) | 保留 | **改為 8 階純灰階**，多系列靠線條粗細/虛實/標記區分 |
| Chat / Command palette 強調邊條 | accent.electric | 保留 | **改為 text.primary 白色** |
| 404 頁 ◆ Mark + glow 數字 | 提供 | 保留 | **刪除 ◆ icon、刪除 glow** |
| Auth 雙色 spotlight + Star Field 背景 | 提供 | 保留 | **改為純黑無特效** |
| Pricing 推薦版 glow border | accent + glow.accent.sm | 保留 | **改為 1.5px 純白邊，無發光** |
| Mode 切換 | electric / manifesto 雙模式 | 雙模式 | **單一模式 = monochrome**，無 electric |

### 嚴格禁止清單

```
✗ 任何霓虹色（電光藍、紫、青、洋紅）
✗ 任何 linear-gradient / radial-gradient / conic-gradient
✗ 任何 box-shadow glow（dark mode 完全不用 box-shadow）
✗ Spotlight / Halo / Aurora 等氛圍光
✗ Star Field / 粒子 / 視差
✗ 彩色資料視覺化
✗ 透明色塊背景（Status.bg 全部刪除）
✗ 大型品牌 ◆ / ♦ / ✦ 圖示（避免「AI 智能」套路）
✗ 毛玻璃大量使用（極克制，僅 Modal backdrop 允許 blur 8px）
```

### 哲學定型

> **v1.2：xAI 風格 = 銳利幾何 + 純黑白單色 + 巨大文字宣言 + 零發光零漸層**

設計能量全部來自：
1. **大字壓制**（120–160px Hero）
2. **極端留白**（160–192px section padding）
3. **1px hairline**（區塊分隔）
4. **白色強調**（CTA、active 邊條、focus ring）

### 單一使用模式

| 模式 | 適用 | 強調色 |
|------|------|------|
| `data-mode="monochrome"`（**唯一模式**） | 所有 x.ai 站、子產品、Console、Docs | `accent.default = #FFFFFF` |

---

## 目錄

1. [系統定位](#1-系統定位)
2. [快速開始](#2-快速開始)
3. [檔案結構與閱讀順序](#3-檔案結構與閱讀順序)
4. [Token 實作指南](#4-token-實作指南)
5. [元件實作指南](#5-元件實作指南)
6. [常見場景配方](#6-常見場景配方)
7. [Do / Don't 清單](#7-do--dont-清單)
8. [貢獻流程](#8-貢獻流程)
9. [版本與變更管理](#9-版本與變更管理)
10. [常見問題（FAQ）](#10-常見問題)

---

## 1. 系統定位

### 1.1 這套系統是什麼

Grok 風格設計系統 = **xAI / Grok / X 所代表的視覺語言**的設計系統封裝。它不是一個現成的 UI 套件，而是一份**規格 + 規則**，告訴你如何建立同款氣質的介面。

### 1.2 適用情境

| 情境 | 適合？ |
|------|-------|
| AI 產品 / LLM 工具的 Landing 頁 | ✓ 強烈推薦 |
| 開發者導向 SaaS 產品 | ✓ 推薦 |
| 終端 / Console 類介面 | ✓ 推薦 |
| Chat / Conversational AI 應用 | ✓ 推薦 |
| 文件站 / Docs site | ✓ 推薦 |
| 消費級電商 / 零售 | ✗ 過於冷感 |
| 兒童 / 教育類 | ✗ 缺乏親和力 |
| 醫療 / 政府 / 銀行 | △ 需評估冷感是否合宜 |
| 既有產品已有自家設計系統 | △ 不要混用，會破壞一致性 |

### 1.3 與本專案 Smart Lock 系統的關係

本目錄為 `web_design_spec_prompt_pipeline/design-system-specs/grok/`，與 `smartlock/` **平行獨立**：
- 兩套各自完整、互不依賴
- Grok 為「風格參考」，可用於：
  1. 完全採用（新建獨立產品）
  2. 局部嵌入（例如在 Smart Lock Admin 中嵌入 AI 對話模組時切換為 Grok 主題）
- **不要混用 token**。要嘛全 Grok、要嘛全 Smart Lock。

---

## 2. 快速開始

### 2.1 前置需求

```
工具鏈：
- Node.js 20+
- Tailwind CSS 4.x
- React 18+ 或 Next.js 14+
- 字型：Geist Variable + Geist Mono（self-host 或 Google Fonts）
```

### 2.2 5 分鐘啟動

**Step 1：建立 CSS variables**

複製 `00_foundations_spec.md` §12.2 的 token 表，建立 `globals.css`：

```css
:root {
  /* Canvas */
  --color-canvas-base: #000000;
  --color-canvas-raised: #0A0A0A;
  --color-canvas-overlay: #111111;
  --color-canvas-sunken: #050505;

  /* Surface */
  --color-surface-default: #0A0A0A;
  --color-surface-hover: #141414;
  --color-surface-active: #1A1A1A;

  /* Border */
  --color-border-hairline: #1F1F1F;
  --color-border-subtle: #161616;
  --color-border-default: #2A2A2A;

  /* Text */
  --color-text-primary: #FAFAFA;
  --color-text-secondary: #A1A1AA;
  --color-text-tertiary: #71717A;
  --color-text-disabled: #52525B;

  /* Accent (v1.2: 唯一強調色 = 白) */
  --color-accent: #FFFFFF;
  --color-accent-subtle: #1A1A1A;
  --color-accent-muted: #A1A1AA;

  /* Status (v1.2: 去飽和、僅作 icon，不用作 bg) */
  --color-status-warning: #C0A050;
  --color-status-danger: #D06060;

  /* Typography */
  --font-sans: "Geist", "Inter", -apple-system, sans-serif;
  --font-mono: "Geist Mono", "JetBrains Mono", monospace;

  /* Motion */
  --motion-fast: 120ms;
  --motion-default: 180ms;
  --motion-slow: 280ms;
  --motion-ease: cubic-bezier(0.2, 0, 0.13, 1);

  /* Radius */
  --radius-xs: 2px;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
}

[data-theme="light"] {
  --color-canvas-base: #FFFFFF;
  --color-canvas-raised: #FAFAFA;
  --color-canvas-overlay: #FFFFFF;
  --color-canvas-sunken: #F4F4F5;
  --color-surface-default: #FFFFFF;
  --color-surface-hover: #F4F4F5;
  --color-surface-active: #E4E4E7;
  --color-border-hairline: #E4E4E7;
  --color-border-subtle: #F4F4F5;
  --color-border-default: #D4D4D8;
  --color-text-primary: #0A0A0A;
  --color-text-secondary: #52525B;
  --color-text-tertiary: #71717A;
  --color-text-disabled: #A1A1AA;
  --color-accent: #0A0A0A;
  --color-accent-subtle: #F4F4F5;
}

body {
  background: var(--color-canvas-base);
  color: var(--color-text-primary);
  font-family: var(--font-sans);
  font-feature-settings: "ss01", "cv11";
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
}
```

**Step 2：設定 Tailwind**

`tailwind.config.ts`：

```ts
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: {
          base: "var(--color-canvas-base)",
          raised: "var(--color-canvas-raised)",
          overlay: "var(--color-canvas-overlay)",
          sunken: "var(--color-canvas-sunken)",
        },
        surface: {
          DEFAULT: "var(--color-surface-default)",
          hover: "var(--color-surface-hover)",
          active: "var(--color-surface-active)",
        },
        border: {
          hairline: "var(--color-border-hairline)",
          subtle: "var(--color-border-subtle)",
          DEFAULT: "var(--color-border-default)",
        },
        text: {
          primary: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          tertiary: "var(--color-text-tertiary)",
          disabled: "var(--color-text-disabled)",
        },
        accent: {
          DEFAULT: "var(--color-accent)",
          hover: "var(--color-accent-hover)",
          subtle: "var(--color-accent-subtle)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
      transitionDuration: {
        fast: "var(--motion-fast)",
        DEFAULT: "var(--motion-default)",
        slow: "var(--motion-slow)",
      },
      transitionTimingFunction: {
        DEFAULT: "var(--motion-ease)",
      },
    },
  },
};
```

**Step 3：載入 Geist 字型**

Next.js（`app/layout.tsx`）：

```tsx
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

export default function RootLayout({ children }) {
  return (
    <html lang="zh-Hant" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="bg-canvas-base text-text-primary font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
```

**Step 4：建立第一個 Hero**

```tsx
export function Hero() {
  return (
    <section className="min-h-[80vh] flex flex-col justify-center px-12 py-32">
      <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-text-tertiary mb-6">
        ◆ &nbsp;01 / FOUNDATIONS&nbsp; / &nbsp;COLOR
      </p>
      <h1 className="text-[96px] leading-[96px] font-bold tracking-[-0.04em] text-text-primary mb-6 max-w-[14ch]">
        Build truth-seeking AI for the universe.
      </h1>
      <p className="text-lg leading-7 text-text-secondary max-w-[32em] mb-12">
        A new kind of intelligence that understands context, reasons from first principles, and never lies to you.
      </p>
      <div className="flex gap-3">
        <button className="h-12 px-6 bg-text-primary text-canvas-base text-sm font-medium rounded-sm hover:bg-[#E5E5E5] transition">
          Try Grok ↗
        </button>
        <button className="h-12 px-6 bg-transparent text-text-primary text-sm font-medium rounded-sm border border-border hover:bg-surface-hover transition">
          Read paper
        </button>
      </div>
    </section>
  );
}
```

完成。現在你已有一個 Grok 風格 Hero。

---

## 3. 檔案結構與閱讀順序

```
design-system-specs/grok/
├── 00_foundations_spec.md       ← 物理定律（必讀）
├── 01_components_spec.md        ← 原子元件（按需查閱）
├── 02_patterns_spec.md          ← 組合模式（建頁面前讀）
├── 03_templates_spec.md         ← 完整頁面藍圖（規劃時讀）
└── 99_documentation_spec.md     ← 本文件
```

### 3.1 角色閱讀順序

| 角色 | 必讀 | 選讀 |
|------|------|------|
| 設計師 | 00 → 01 → 02 → 03 | 99 |
| 前端工程師 | 99 §2 → 00 §11–12 → 01 → 02 | 03 |
| PM / 產品 | 03 → 00 §設計哲學 | 99 §1 |
| QA | 01 §states → 02 §互動 → 99 §6 | 00 |

### 3.2 修改頻率

| 文件 | 修改頻率 | 修改門檻 |
|------|----------|---------|
| 00 Foundations | 極低 | 需設計負責人核可 |
| 01 Components | 中 | PR review |
| 02 Patterns | 中 | PR review |
| 03 Templates | 高 | PR review |
| 99 Documentation | 隨需求 | 直接更新 |

---

## 4. Token 實作指南

### 4.1 Token 三階層

```
Tier 1: Primitive（原始值）
   ↓
Tier 2: Semantic（語意命名）  ← 設計系統使用者主要用這層
   ↓
Tier 3: Component（元件專用） ← 元件實作者用這層
```

### 4.2 命名規則

```
✓ DO
   --color-text-primary
   --space-section-lg
   --motion-duration-fast
   --type-display-2xl

✗ DON'T
   --gray-900            (太底層，混入語意層)
   --color-1             (數字無語意)
   --large-spacing       (形容詞模糊)
   --custom-color        (無意義)
```

### 4.3 何時新增 Token

```
新增 Token 前先回答：
1. 這個值會在 ≥ 3 個地方重複嗎？
   - 否：直接寫死值
   - 是：考慮 token

2. 這個值有「設計意圖」嗎（不只是隨機選的）？
   - 否：寫死值
   - 是：建 token

3. 是否能用既有 token 組合表達？
   - 是：用組合，不開新 token
   - 否：建 token

4. 命名能精確描述用途嗎？
   - 否：先想清楚再開
   - 是：建 token
```

### 4.4 Token 變更影響範圍

修改 `00_foundations_spec.md` 的 token 時：
1. 寫 PR 並標記 `[breaking]` 或 `[non-breaking]`
2. List 所有受影響的元件 / 模式 / 模板
3. 更新對應 CSS variables、Tailwind config、Penpot 變數
4. 跑 visual regression test
5. 通知設計與前端負責人

---

## 5. 元件實作指南

### 5.1 元件命名

```
✓ Button, Input, Card, Modal, Tooltip, Tabs
✗ MyButton, GrokButton, AppButton（多餘前綴）
```

如果擔心命名衝突，使用 namespace：`grok/Button`，但**檔名不加前綴**。

### 5.2 Variant API 設計

每個元件提供：

```ts
type ButtonProps = {
  variant?: "primary" | "secondary" | "ghost" | "outline" | "danger" | "link";
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  loading?: boolean;
  disabled?: boolean;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  fullWidth?: boolean;
  asChild?: boolean;  // Radix slot pattern
  // ... rest
};
```

**規則**：
- variant 必有合理預設（通常是最中性的）
- size 預設 `md`
- 不允許「自訂顏色」prop（破壞系統）
- 不允許「自訂 padding」prop（破壞系統）
- icon 用 children pattern，不用 string + lookup

### 5.3 元件目錄結構

```
src/components/ui/Button/
├── Button.tsx           ← 元件本體
├── Button.types.ts      ← TS 型別
├── Button.variants.ts   ← cva / tv variants 定義
├── Button.test.tsx      ← 測試
├── Button.stories.tsx   ← Storybook
└── index.ts             ← export
```

### 5.4 cva (class-variance-authority) 範例

```ts
import { cva } from "class-variance-authority";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 font-medium rounded-sm transition-all focus:outline-none focus:ring-2 focus:ring-text-primary focus:ring-offset-2 focus:ring-offset-canvas-base disabled:opacity-40 disabled:cursor-not-allowed",
  {
    variants: {
      variant: {
        primary: "bg-text-primary text-canvas-base hover:bg-[#E5E5E5]",
        secondary: "bg-surface text-text-primary border border-border hover:bg-surface-hover",
        ghost: "bg-transparent text-text-primary hover:bg-surface-hover",
        outline: "bg-transparent text-text-primary border border-border hover:bg-surface-hover",
        danger: "bg-transparent text-status-danger border border-status-danger hover:bg-status-danger/10",
        link: "bg-transparent text-accent hover:underline p-0",
      },
      size: {
        xs: "h-6 px-2 text-[11px]",
        sm: "h-8 px-3 text-[13px]",
        md: "h-10 px-4 text-[13px]",
        lg: "h-12 px-6 text-[15px]",
        xl: "h-14 px-8 text-base",
      },
      fullWidth: {
        true: "w-full",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);
```

### 5.5 元件無障礙清單

| 項目 | 要求 |
|------|------|
| Keyboard | 所有互動元件可鍵盤操作 |
| Focus ring | 必出現，不可移除（可重設樣式） |
| ARIA labels | icon-only button 必有 aria-label |
| Role | 自訂元件用 ARIA role 對齊原生語意 |
| State announce | 動態狀態（loading / error）有 aria-live |
| 對比 | 文字對比 ≥ 4.5:1，UI 元件 ≥ 3:1 |

---

## 6. 常見場景配方

### 6.1 「我要做一個 AI Chat 介面」

```
1. 讀 03 Templates §7 Chat Workspace
2. 用 02 Patterns §15 Chat Conversation 組訊息流
3. 用 02 Patterns §10 Sidebar Navigation 做 thread list
4. 用 02 Patterns §16 Command Palette 加 ⌘K 搜尋
5. 訊息渲染用 01 §16 Code Block 處理程式碼塊
```

### 6.2 「我要做一個產品 Landing」

```
1. 讀 03 Templates §1 Landing 區段順序
2. Hero 用 02 §2，背景純黑（**禁止 spotlight / 漸層**）
3. 中段用 02 §3 Bento Grid + §4 Feature Triplet 交替
4. 結尾 02 §8 CTA Block centered + §9 Footer
5. 全頁加 02 §1 Top Navigation transparent variant
```

### 6.3 「我要做一個 Dashboard」

```
1. 讀 03 Templates §6 Console Dashboard
2. Sidebar 用 02 §10
3. 頁面頭用 page-header pattern（Templates §6.2）
4. 上排 02 §14 Stats Strip
5. 中段 chart cards (Templates §6.4)
6. 底部 02 §11 Data Table
```

### 6.4 「我要切到 Light Mode」

```
1. 在 <html> 加 data-theme="light"
2. 全部 token 自動切換
3. 注意：Star Field 已禁用，Marquee 改 solid mask，bg.dot.dim 僅 Console / Docs 可用
4. Glow 改用 shadow（00 §6.3）
5. 圖片若有 dark only 版本，需準備 light 對偶
```

### 6.5 「我要嵌入 Smart Lock 平台」

```
1. 在隔離容器外加 class="theme-grok"
2. CSS 用 .theme-grok { ... } 覆蓋 token
3. 確保字型已載入 Geist
4. 內部元件不繼承 Smart Lock token
5. 與 Smart Lock 主題切換時加 24px 視覺隔離（hairline 或 padding）
```

---

## 7. Do / Don't 清單

### 7.1 Color

| ✓ DO | ✗ DON'T |
|------|---------|
| 用 `canvas.raised` 抬升卡片 | 用陰影抬升卡片（暗底不可見） |
| 用 hairline 1px 切分區塊 | 用粗框 2px+ 切分（破壞銳利感） |
| 一個強調色貫穿全站 | 多個強調色混用 |
| 數字色用 `text.primary`（白） | 數字用花俏漸層 |

### 7.2 Typography

| ✓ DO | ✗ DON'T |
|------|---------|
| Hero 用 96px 大字 | Hero 用 36-48px（不夠張力） |
| Eyebrow 用 mono uppercase | Eyebrow 用襯線斜體 |
| 數字用 mono + tabular-nums | 數字用 sans 變體 |
| 字距收緊 -0.02 ~ -0.04em | 字距放寬 |

### 7.3 Spacing

| ✓ DO | ✗ DON'T |
|------|---------|
| Section padding 用 96-160px | Section padding 用 32-48px（太擠） |
| 大量留白 | 資訊密集塞滿 |
| 區塊間距遵循 8px 系統 | 出現 11px、17px 等非系統值 |

### 7.4 Radius

| ✓ DO | ✗ DON'T |
|------|---------|
| 預設 radius.sm (4px) | 預設 radius.xl (16px+) |
| 卡片最大 radius.lg (8px) | 卡片用 12-16px 圓角 |
| Avatar / Status dot 用 full | Button 用膠囊（pill） |

### 7.5 Motion

| ✓ DO | ✗ DON'T |
|------|---------|
| 120-280ms 短促動效 | 500ms+ 緩慢動效 |
| Linear / 銳利 ease | Spring / Bounce |
| Hover 切換 bg | Hover translate / scale |
| Reduce motion 自動降級 | 強制動畫 |

### 7.6 結構

| ✓ DO | ✗ DON'T |
|------|---------|
| Eyebrow + 標題 + 段落三段式 | 直接大標無前置 |
| 一頁聚焦一個重點 | 一頁塞 10 個訴求 |
| CTA 一主一次（最多） | 一頁 5+ 個 CTA |
| 留白做主視覺 | 用滿背景填色 |

---

## 8. 貢獻流程

### 8.1 新增 / 修改規格的流程

```
┌─────────────────────────────────────────────────┐
│ 1. 開 issue 描述需求                              │
│    - 為什麼要改？解決什麼問題？                    │
│    - 影響範圍？                                   │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│ 2. 設計負責人 review                              │
│    - 是否與系統一致？                              │
│    - 是否能用現有 token / pattern 表達？           │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│ 3. 寫 PR                                         │
│    - 修改對應 spec.md                             │
│    - 更新 token / Tailwind config                │
│    - 更新對應元件實作                              │
│    - 加 visual test snapshot                     │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│ 4. PR review                                     │
│    - 設計 review                                  │
│    - 前端 review                                  │
│    - QA 確認 visual regression                    │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│ 5. Merge + 同步通知                               │
│    - changelog.md                                │
│    - Slack #design-system 通知                   │
│    - 大型變更：寫 migration guide                  │
└─────────────────────────────────────────────────┘
```

### 8.2 PR 標題與標籤

```
[grok] feat: add new accent color variant
[grok] fix: button focus ring contrast
[grok] docs: update Hero pattern usage
[grok] breaking: rename color.text.muted → color.text.tertiary

標籤：
- breaking：API / token 命名改變
- non-breaking：純新增
- visual：視覺微調，無 API 變動
- docs：純文件
```

### 8.3 變更命名規範

```
新增：feat
修復：fix
文件：docs
重構：refactor
廢棄：deprecate
移除：remove
```

廢棄流程：
1. 標記 `@deprecated` 並提示替代方案
2. 兩個版本後正式移除
3. Migration guide 必須提供

---

## 9. 版本與變更管理

### 9.1 版本號

採用 Semantic Versioning：

```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └─ token 微調、文件補強
  │     └─────── 新增元件 / 模式（向後相容）
  └───────────── 命名 / API 改變（不相容）
```

當前版本：`v1.0.0`（初始版）

### 9.2 Changelog 格式

```markdown
## [1.1.0] - 2026-06-15

### Added
- Marquee Banner pattern (#23)
- Compact density variant for Data Table (#28)

### Changed
- Tooltip delay-open: 300ms → 400ms (#31)

### Deprecated
- `color.accent.electric` → **deleted**（v1.2 移除，改用 `color.accent.default = #FFFFFF`）

### Removed
- N/A

### Fixed
- Button focus ring offset on dark canvas (#35)

### Visual
- Adjusted Hero title letter-spacing for Geist 1.3.0
```

### 9.3 Breaking Change 處理

```
Major bump 之前：
1. 提前 1 個月公告
2. 提供 codemod 自動轉換腳本（如可能）
3. 寫 migration guide
4. Visual regression 全跑一次
5. 共識會議：設計 + 前端 + 主要使用團隊
```

---

## 10. 常見問題

### Q1：可以加 light mode 嗎？

可以。00 §12 已定義 light mode token 對偶。但 Grok 的 DNA 是 dark first，dark mode 為主、light 為「白天閱讀模式」。建議：
- 預設 dark
- 使用者可手動切換
- 不依 prefers-color-scheme 自動切換（除非使用者未明確選擇）

### Q2：可以改主強調色嗎？

**不可**。v1.2 後唯一允許的強調色是 `#FFFFFF`（white）。

如果你的品牌需要彩色強調，請選擇其他設計系統（例如本專案的 `smartlock/`），不要嘗試把彩色硬塞進 grok 系統，那會破壞它的核心氣質。

### Q3：可以加圓角到 12px+ 嗎？

不可。Grok 風格的核心之一是銳利，最大允許 8px。如果要圓滑感請考慮其他設計系統。

### Q4：可以用漸層嗎？

**不可**。v1.2 後完全禁止任何漸層：
- ✗ linear-gradient
- ✗ radial-gradient
- ✗ conic-gradient
- ✗ Spotlight / Halo / Aurora 等氛圍光
- ✗ 按鈕、卡片、文字、邊框漸層
- ✗ Marquee fade mask（改為 solid 同色蓋片）
- ✗ Skeleton shimmer（改為 opacity 呼吸）

唯一例外：CSS `radial-gradient(circle, color 1px, transparent 1px)` 用來繪製 dot grid 的單個圓點，因為**圓點本身為純色**，不是視覺漸層。

### Q5：可以在按鈕加 hover translate 嗎？

不可。Grok 風格 hover 只切換顏色（bg / border / text），保持位置穩定。Translate 屬於彈性動效，與系統氣質衝突。

### Q6：圖示可以用 fill 嗎？

預設用 stroke（Lucide / Phosphor stroke 1.5px）。Fill 圖示僅在語意明確時使用：
- ✓ ★ Star（已收藏）
- ✓ ♥ Heart（已喜歡）
- ✓ Status dot
- ✗ 一般 UI icon 用 fill

### Q7：怎麼處理表情符號 emoji？

謹慎使用：
- ✓ 對話框內使用者輸入（保留原樣）
- ✓ Status indicator（限於 ✓ ✕ ⚠ ℹ）
- ✗ UI 標題、按鈕、選單
- 使用平台原生 emoji，不引入第三方 emoji 字型

### Q8：可以用第三方 UI Kit（Radix / shadcn / Mantine）嗎？

可以，但**只用 unstyled 版本**：
- ✓ Radix UI（headless）+ 自己套 Grok token
- ✓ shadcn/ui 框架，重寫所有 variant
- ✗ Mantine / Chakra / MUI（已有自家樣式，難覆蓋）

推薦組合：**Radix UI + Tailwind + cva + Geist**

### Q9：怎麼處理資料密集型介面（如表格 1000 行）？

- 使用 §11 Data Table 的 `Compact` density variant
- 行高 40px
- 字級降到 `type.body.xs`
- 邊框只保留 row separator（去掉 column separator）
- 必要時考慮虛擬捲動（react-virtual / TanStack Virtual）

### Q10：要支援 RTL 嗎？

預設不支援。如要支援：
- 所有 `border-l` / `border-r` 改為 `border-s` / `border-e`（logical properties）
- 所有 `pl` / `pr` 改為 `ps` / `pe`
- 圖示方向：`→` 在 RTL 自動鏡像為 `←`（CSS `transform: scaleX(-1)`）
- 在 PR 內標記 `[rtl-ready]`

---

## 附錄 A：關鍵 Token 速查表

### A.1 必背 5 個

```
color.canvas.base       ← 頁面底色 (#000)
color.text.primary      ← 主文字 (#FAFAFA)
color.border.hairline   ← 1px 分隔線 (#1F1F1F)
color.accent.default    ← 強調色 (#FFFFFF，唯一允許)
space.section.lg        ← 段落 padding (128px)
```

### A.2 字型速查

```
type.display.2xl  → 96px / 700 / -0.04em   (Hero 主標)
type.heading.xl   → 28px / 600 / -0.02em   (Card 主標)
type.body.md      → 15px / 400 / 0          (預設內文)
type.label.sm     → 11px / 500 / 0.06em     (Eyebrow caps)
type.mono.md      → 14px / 400              (Code)
```

### A.3 間距速查

```
space.section.xl  → 160px (Hero 上下)
space.section.lg  → 128px (大段落)
space.section.md  → 96px  (預設段落)
space.6           → 24px  (卡片間距)
space.4           → 16px  (預設區塊內距)
```

---

## 附錄 B：實作檢查清單

開始實作前確認：

- [ ] CSS variables 已建立（00 §12.2 全表）
- [ ] Tailwind config 已對應 token
- [ ] Geist 字型已 self-host 或 CDN 載入
- [ ] body 預設樣式（dark bg、font-sans、tabular-nums）
- [ ] Reset / Normalize CSS（推薦 Tailwind preflight）
- [ ] prefers-reduced-motion 處理
- [ ] focus-visible 樣式統一
- [ ] selection 顏色（建議 `surface.elevated` bg + `text.primary` 文字）
- [ ] scrollbar 樣式（webkit / firefox 統一）

每完成一個元件確認：

- [ ] 7 個 variant（如適用）已實作
- [ ] 5 個 size（如適用）已實作
- [ ] 5 個 state（default / hover / active / focus / disabled）視覺正確
- [ ] 鍵盤可操作
- [ ] 對比通過 WCAG AA
- [ ] Storybook 文件
- [ ] 單元測試 + visual snapshot

---

**版本**：v1.0
**最後更新**：2026-05-02
**維護者**：Design System Owner
**回饋**：在 PR / Issue 標記 `[grok]` 標籤
