# i18n — 多語系字串管理

本目錄存放 web admin dashboard 的所有翻譯字串與語系設定。實作為**輕量 DIY**（無新 npm 依賴），鏡像 `ThemeProvider`/`ThemeToggle` 模式。

## 目錄結構

```
src/i18n/
├── config.ts                 # 支援語系列表 + 型別 + storage key
├── messages/
│   ├── zh-TW.json            # 預設語系（繁體中文）
│   └── en.json               # 第二語系（英文）
└── README.md                 # 本檔

src/components/i18n/
├── LocaleProvider.tsx        # context + localStorage + html.lang 同步
└── LocaleToggle.tsx          # icon / segmented 兩變體切換 UI

src/lib/translate.ts          # 純函式 lookup（可在 React 外使用）
```

## 使用方式

### 1. 在 component 內讀字串

```tsx
"use client";
import { useTranslations } from "@/components/i18n/LocaleProvider";

export default function MyComponent() {
  const t = useTranslations("settings.profile");
  return <h1>{t("title")}</h1>;             // → "個人資料" / "Profile"
}
```

支援 `{name}` 占位符（不支援 ICU 複數 / 性別 — 真需要時再換 next-intl）：

```tsx
const t = useTranslations("locale");
t("current", { label: "繁體中文" });
// zh-TW: "切換語言（目前：繁體中文）"
// en   : "Switch language (current: 繁體中文)"
```

### 2. 在 React 外（toast helper / API error mapper）

```ts
import { translate } from "@/lib/translate";

throw new Error(translate("zh-TW", "common.error"));
```

### 3. 切換語系 UI

```tsx
import LocaleToggle from "@/components/i18n/LocaleToggle";

<LocaleToggle />                    // Header 用：圓鈕 + popover
<LocaleToggle variant="segmented" /> // Settings 用：button group
```

## 加新語系

1. 在 `messages/` 加新 JSON 檔（鏡像 `zh-TW.json` 結構）
2. 在 `config.ts` 的 `LOCALES` 陣列加一筆
3. 更新 `lib/translate.ts` 的 `MESSAGES` map（import + 註冊）
4. 完成 — UI 切換器自動列入新選項

## 加新翻譯 key

1. 在 `messages/zh-TW.json` 加 key（先預設語系）
2. 同步加到 `en.json`（**所有 locale 必須結構同步**）
3. 在 component 用 `t("path.to.key")` 讀取

缺 key 行為：先 fallback 到 DEFAULT_LOCALE；還缺則回傳 path 字串（在 UI 直接看到 `settings.foo.bar` — 比空字串好 debug）。

## 範圍與漸進式遷移

V1 scaffold 翻譯涵蓋：

| 範圍 | 狀態 |
|------|------|
| Header（搜尋框 placeholder / aria-label） | ✅ |
| Settings 頁（4 tabs / Profile / Security / 共用按鈕） | ✅ |
| LocaleToggle / ThemeToggle a11y label | ✅ |

未涵蓋（41 頁中其餘 ~38 頁）：

- 字串仍硬編 zh-TW
- 不影響 V1.0 上線（所有用戶仍預設 zh-TW）
- 漸進遷移策略：每次動到該頁時，順手把字串抽到 `messages/`；不單獨開 PR 做 mass extraction

## 為什麼自寫不裝 next-intl

| 因素 | 選擇 |
|------|------|
| 新 npm 依賴 | ❌ 無 |
| App Router 中間件設定 | ❌ 不需 |
| URL routing locale（`/zh-TW/...` vs `/en/...`） | ❌ 不需（admin tool 無 SEO 需求） |
| ICU MessageFormat（複數 / 性別 / 日期） | ⏳ 需要時再換 |
| Hook 形狀（`useTranslations(namespace)`） | ✅ 與 next-intl 一致，未來遷移無痛 |
| 漸進採用 | ✅ 不強制全頁遷移 |

未來若需要 ICU 或 SSR 預載入，遷移為 next-intl 的工作集中在 `LocaleProvider.tsx` + `lib/translate.ts`，**components 的 `useTranslations(...)` callsite 零改動**。

## 相關文件

- 設計決策：[`docs/02-design/specs/i18n-strategy.md`](../../../docs/02-design/specs/i18n-strategy.md)
- E7x readiness：[`docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md`](../../../docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md) §4.2
