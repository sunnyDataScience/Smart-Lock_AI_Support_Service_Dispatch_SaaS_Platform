# TC-NFR-A11Y-01 — 四 portal a11y 綜合（axe / 鍵盤 / 縮放 200% / 斷網重試）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | 四站台 `src/app/globals.css`（`:focus-visible` / `.skip-link` / `.sr-only` / `prefers-reduced-motion`）、`web/*/src/components/layout/SkipLink.tsx`、`web/landing/src/components/i18n/LocaleChrome.tsx:20`、`web/tech-portal/src/app/layout.tsx:60-66`、`web/shared-contract/src/mutation.ts:1-231`、`web/brand-portal/src/lib/preferences.ts:67`、`web/brand-portal/src/components/layout/NotificationDrawer.tsx:224`、`web/brand-portal/src/lib/apiError.ts:109-123`、`web/brand-portal/tests/unit/mutation.test.ts:22-196`、`web/brand-portal/tests/e2e/admin/cr-0190-mutation-recovery.spec.ts:58-108`、`smartlock-docs/enterprise/05_NFR.md:203-207` |
| 優先級 / 路徑類型 | P1 / recovery＋boundary |

四項步驟的落點狀態不同。**axe**：TC 前置寫「四 portal + LIFF keyboard/axe fixture」，該 fixture 在程式碼中零命中——`AxeBuilder` 全 repo 零命中，`axe-core` 只以 `eslint-plugin-jsx-a11y` 相依身分出現在 lockfile，無任何測試或腳本呼叫，故「critical a11y=0」無法取得。**鍵盤流程**：四站 `globals.css` 皆有全域 `:focus-visible` 兜底與 `.skip-link` 樣式，但 skip link 目標 `#main-content` 只有 brand-portal 三頁定義。**縮放 200%**：四站皆無 `user-scalable=no` / `maximum-scale`（全 `web/` 零命中），tech-portal 另顯式宣告 viewport 並在註解寫「允許放大(a11y)」；實際 200% 下的版面是否可用需渲染後觀測。**斷網重試不靜默遺失表單**：`web/shared-contract/src/mutation.ts` 有明文的 mutation 契約（同一 action retry 沿用同一 idempotency key、offline/5xx/409 一律 rollback），並有 6 項 vitest 與 2 項 Playwright 案例；但其使用端只有 brand-portal 的兩處（通知抽屜、偏好設定），一般表單頁未走此契約，且四站台皆無草稿本地暫存（`localStorage` 用途只有主題、語系、閒置時間戳、PWA 提示）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | 四 portal + LIFF keyboard/axe fixture |
| 步驟 | 跑 axe、鍵盤流程、縮放 200%、斷網重試 |
| 預期結果（判定基準） | critical a11y=0；焦點、錯誤與對比可用；斷網不靜默遺失表單 |
| 路徑類型 | recovery＋boundary |
| 驗證面向 | 功能 |
| 優先級 | P1 |
| 驗證哪些需求 | NFR-A11y-001、NFR-A11y-003、NFR-A11y-004、NFR-A11y-005 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:431`。四條需求原文（`smartlock-docs/enterprise/05_NFR.md:203-207`）：

```
| NFR-A11y-001 | LINE 端 | LINE 原生 a11y | 平台保證 | 營運目標 |
| NFR-A11y-003 | 對比 | ≥ 4.5:1 | 設計系統 token 檢核 | 營運目標 |
| NFR-A11y-004 | 鍵盤導覽 | 全功能可鍵盤操作 | E2E 鍵盤測試 | 營運目標 |
| NFR-A11y-005 | Screen reader | ARIA labels 完整 | axe + 人工抽測 | 營運目標 |
```

同檔 `20_Test_Cases.md:221`、`:223-225` 記載這四條需求的追溯狀態皆為「⚠ 完全沒有案例」。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 存在 axe fixture | `AxeBuilder` 全 repo 零命中；`axe-core` 僅 lockfile 相依 | 不一致 |
| critical a11y = 0 | 無掃描器可跑 | 無法靜態判定 |
| 存在 keyboard fixture | 四站 `tests/` 內無鍵盤流程 spec | 不一致 |
| 焦點指示器 | 四站 `globals.css`：brand `:228`、tech `:239`、landing `:221`、platform `:221` | 一致 |
| skip link | `SkipLink.tsx`（brand / tech / platform）、`LocaleChrome.tsx:20`（landing） | 一致 |
| skip link 目標 | `id="main-content"` 僅 brand-portal 3 頁 | 不一致 |
| 縮放不被禁止 | `user-scalable` / `maximum-scale` 全 `web/` 零命中；`tech-portal/src/app/layout.tsx:60-66` | 一致 |
| 縮放 200% 版面可用 | — | 無法靜態判定 |
| 錯誤訊息可用 | `apiError.ts:109-123`；`role="alert"` 四站合計 38 處 | 一致 |
| 對比可用（NFR-A11y-003 ≥ 4.5:1） | `web/tech-portal/tests/unit/themeContrast.test.ts:80`（僅 tech-portal 有 token 檢核） | 部分實作 |
| ARIA labels 完整（NFR-A11y-005） | `aria-label` 命中：brand 71、tech 44、landing 32、platform 40 | 無法靜態判定（完整性需逐元件核對） |
| 斷網 rollback 不留假成功 | `mutation.ts:203-215`；`cr-0190-mutation-recovery.spec.ts:58`、`:108` | 一致（限已接入的兩處） |
| retry 沿用同一 idempotency key | `mutation.ts:180-186`、`:207`；`mutation.test.ts:141` | 一致 |
| 表單內容不遺失（草稿保存） | 四站 `localStorage` 用途無草稿；`draft` 於 tech-portal 僅命中 SOP 型別與日期選擇器 | 不一致 |
| LINE 端 a11y（NFR-A11y-001） | 需求欄位為「平台保證」，無程式碼落點 | 無法靜態判定 |

---

## Event Storming

本案例為前端無障礙與復原行為。有 domain 語意的只有 mutation 契約一段：

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 後台使用者 | 送出低風險 mutation（通知已讀 / 偏好） | `MutationApplied` | optimistic 僅限低風險 | `mutation.ts:167-174`、`:190-193` | `SERVER_CONFIRMED_RISKS` 命中即 throw |
| 系統 | 斷網 / 5xx | `MutationRolledBack` | 不留假成功 UI | `mutation.ts:203-212` | catch 內 `state.write(rollback ?? snapshot)` |
| 使用者 | 重試 | `MutationRetried(同 actionId)` | 同 action 同 key | `mutation.ts:180-186`、`:222-224` | `actionId` 建構期產生一次，`retry` 即 `execute` |
| 系統 | 409 | `MutationConflict` | 轉成具版本資訊的錯誤 | `mutation.ts:161-165`、`:104-136` | `MutationConflictError`（帶 `currentVersion`） |
| 使用者 | 一般表單頁送出後斷網 | — | — | — | **找不到**：一般表單頁未接入 `createMutationAction`（使用端僅兩處） |

---

## 逐層走查

### 步驟 1 — axe 與 keyboard fixture

```
git grep -rn "AxeBuilder\|@axe-core" -- web api agent
（無輸出）
git grep -rn "axe-core" -- web | grep -v package-lock
（無輸出）
```

`axe-core` 只存在於四站 `package-lock.json`，其父節點為 `eslint-plugin-jsx-a11y@6.10.2`（`web/brand-portal/package-lock.json:4715-4726`）：

```json
    "node_modules/eslint-plugin-jsx-a11y": {
      "version": "6.10.2",
      ...
      "dependencies": {
        "aria-query": "^5.3.2",
        ...
        "axe-core": "^4.10.0",
```

`web/*/package.json` 的 `scripts` 中無 a11y 相關指令（brand / tech 為 `dev` / `build` / `start` / `lint` / `test:e2e` / `test:e2e:ui` / `test:unit`；landing / platform 無 e2e）。

四站 `tests/` 內無鍵盤流程 spec：

```
git grep -rn "keyboard" -- web/brand-portal/tests web/tech-portal/tests
web/brand-portal/tests/e2e/admin/comprehensive-functional.spec.ts:107:  await page.keyboard.press("Escape");
```

唯一命中是關閉彈窗用的 `page.keyboard.press("Escape")`，非鍵盤導覽斷言。

TC 前置寫「四 portal + LIFF **keyboard/axe fixture**」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:431`）／repo 內無此 fixture。此處僅並陳，不裁定。

### 步驟 2 — 焦點與 skip link（NFR-A11y-004）

四站 `globals.css` 的全域焦點兜底（以 brand-portal `:228` 為例，四站內容相同，僅行號不同）：

```css
  :focus-visible {
    outline: 2px solid var(--border-focus);
    outline-offset: 2px;
  }

  /* outline-none 後仍要保證 :focus-visible 看得到（unset Tailwind reset） */
  :focus-visible.outline-none,
  .outline-none:focus-visible {
    outline: 2px solid var(--border-focus);
    outline-offset: 2px;
  }
```

其前方註解（tech-portal `:235-238`）記載動機：「專案散落 30+ 個 outline:none / outline-none，鍵盤使用者全部看不到焦點。這條 base-layer 規則做最後一道保險」。

skip link 元件（brand / tech / platform 三站為 `SkipLink.tsx`，landing 為 `LocaleChrome.tsx:20`）：

```tsx
    <a href="#main-content" className="skip-link">
      {t("skipToMain")}
    </a>
```

目標錨點分佈：

```
git grep -c 'id="main-content"' -- web/<site>/src
brand-portal: 3（conversations/page.tsx:124、dashboard/page.tsx:217、work-orders/page.tsx:239）
tech-portal: 0
landing: 0
platform-console: 0
```

landing 的內容 `<main>` 在 `web/landing/src/app/page.tsx:151`，無 `id`。

`role="dialog"` + `aria-modal` 僅 brand-portal 各 2 處（`components/admin/RolePermissionsEditor.tsx:144`、`components/layout/CommandPalette.tsx:101`），tech / landing / platform 各 0 處。`Escape` 鍵處理集中在語系切換、主題切換、Sidebar context 與 CommandPalette 共 13 檔。

### 步驟 3 — 縮放 200%

全 `web/` 對 `user-scalable`、`maximum-scale`、`maximumScale` 三者零命中。

tech-portal 顯式宣告 viewport（`web/tech-portal/src/app/layout.tsx:60-66`）：

```tsx
export const viewport: Viewport = {
  themeColor: "#2563EB",
  width: "device-width",
  initialScale: 1,
  // PWA 全螢幕體驗:允許放大(a11y)但預設貼合裝置
  viewportFit: "cover",
};
```

brand-portal / landing / platform-console 的 `layout.tsx` 無 `export const viewport`（`git grep -c "export const viewport"` 各為 0），採 Next.js 預設。

版面在 200% 縮放下是否出現內容截斷或水平捲動，需渲染後觀測，**無法靜態判定**。

### 步驟 4 — 斷網重試與表單內容

`web/shared-contract/src/mutation.ts:1-9` 的契約宣告：

```ts
/** @smartlock/shared-contract 0.1.0
 * ADR-034 mutation contract。
 *
 * 目標不是取代 React state library，而是把四個不可分割的語意固定下來：
 * 1. 同一次使用者 action 的 retry 沿用同一 idempotency key。
 * 2. optimistic 僅允許低風險、可逆操作。
 * 3. offline／5xx／409 一律 rollback，不留下假成功 UI。
 * 4. 成功後只失效宣告的 query key；不在此層廣域清空所有 GET。
 */
```

rollback 實作（`:203-215`）：

```ts
      .catch((error: unknown) => {
        if (contract.mode === "optimistic") {
          const current = contract.state.read();
          contract.state.write(
            contract.rollback
              ? contract.rollback(current, snapshot, error)
              : snapshot,
          );
        }
        throw normalizeMutationError(error, actionId);
      })
```

`actionId` 在 `createMutationAction` 建構期產生一次（`:180`），`retry` 與 `run` 是同一個 `execute`（`:222-224`）：

```ts
  return {
    actionId,
    get attempts() {
      return attempt;
    },
    run: execute,
    retry: execute,
  };
```

敏感風險強制 server-confirmed（`:143-152`、`:167-174`）：

```ts
const SERVER_CONFIRMED_RISKS = new Set<MutationRisk>([
  "quote",
  "work-order-status",
  "dispatch",
  "settlement",
  "refund",
  "permission",
  "consent",
]);
```

使用端只有兩處（排除契約自身與測試）：

```
git grep -rn "createMutationAction" -- web | grep -v "shared-contract/src" | grep -v tests
web/brand-portal/src/components/layout/NotificationDrawer.tsx:20 / :224
web/brand-portal/src/lib/preferences.ts:3 / :67
```

即報價、工單狀態、派工、結算、退款、權限、同意等頁面的送出並未接入此契約；tech-portal / landing / platform-console 對 `createMutationAction` 零命中。

表單草稿的本地暫存：四站 `localStorage` 的用途為主題（`ThemeProvider.tsx`）、語系（`LocaleProvider.tsx`）、閒置登出時間戳（`IdleLogoutGuard.tsx:45`）、PWA 提示關閉旗標（`PwaProvider.tsx:33/65/74`）；`draft` 在 tech-portal 的命中為 SOP 型別字串（`components/phase-ii/types.ts:17/25/274`）與日期區間選擇器的暫存 state（`components/ui/DateRangePicker.tsx:80`），皆非表單草稿保存。

斷網時的錯誤文案在 `web/brand-portal/src/lib/apiError.ts:116-121`：

```ts
  if (e instanceof Error) {
    if (e.name === "AbortError") return "請求已取消。";
    // fetch 連線失敗（後端未啟動／網路中斷）
    if (e.name === "TypeError" && /fetch/i.test(e.message)) return "連線失敗，請檢查網路後再試。";
    if (looksUserFriendly(e.message)) return e.message;
  }
```

`navigator.onLine` 與 `window.addEventListener("offline")` 在四站 `src/` 內零命中。

### 步驟 5 — 對比（NFR-A11y-003）與 ARIA（NFR-A11y-005）的落點

- 對比：唯一的 token 層檢核是 `web/tech-portal/tests/unit/themeContrast.test.ts`（`AA_BODY = 4.5`，`:80`），另三站無同型測試。NFR-A11y-003 的驗證方式欄寫「設計系統 token 檢核」（`05_NFR.md:205`），與此測試的做法一致，但覆蓋範圍只有一站。
- ARIA：`aria-label` 命中數 brand 71、tech 44、landing 32、platform 40；`aria-live` 直接命中 1 處（`ChatTimeline.tsx:162`）＋`LiveRegion` 元件 4 份（使用端 1 處）；`role="alert"` 四站合計 38 處。「ARIA labels 完整」的完整性需逐互動元件核對，**無法靜態判定**。

---

## 既有測試證據

`web/brand-portal/tests/unit/mutation.test.ts` 六項與 `web/brand-portal/tests/e2e/admin/cr-0190-mutation-recovery.spec.ts` 兩項是與「斷網不靜默遺失表單」直接對應的既有測試：

```
web/brand-portal/tests/unit/mutation.test.ts:22:  it("低風險 optimistic mutation 會先更新，成功後 reconcile 並精準失效", ...)
web/brand-portal/tests/unit/mutation.test.ts:89:  it("409 會轉成帶 currentVersion 的 MutationConflictError 並 rollback", ...)
web/brand-portal/tests/unit/mutation.test.ts:116:  it("支援 API 標準 details 陣列中的 409 current version", ...)
web/brand-portal/tests/unit/mutation.test.ts:141:  it("retry 沿用同一 actionId，attempt 遞增", ...)
web/brand-portal/tests/unit/mutation.test.ts:168:  it("server-confirmed 在伺服器成功前不修改 state", ...)
web/brand-portal/tests/unit/mutation.test.ts:191:  it("runtime 也會拒絕把敏感操作偽裝成 optimistic", ...)

web/brand-portal/tests/e2e/admin/cr-0190-mutation-recovery.spec.ts:58:  test("offline rollback 後 retry 沿用同一 Idempotency-Key", ...)
web/brand-portal/tests/e2e/admin/cr-0190-mutation-recovery.spec.ts:108:  test(`${scenario.name} 會 rollback，不留下假成功 UI`, ...)
```

該 e2e 的受測對象是通知抽屜（`NOTIFICATION_ID`，`:4`），即前述兩個使用端之一。

四站台 `node_modules` 均未安裝，本次未實跑 vitest 與 Playwright。

---

## 事實結論

1. `AxeBuilder` 全 repo 零命中；`axe-core` 僅以 `eslint-plugin-jsx-a11y` 相依身分存在於四站 lockfile，無呼叫端。
2. 四站 `package.json` 的 `scripts` 無 a11y 掃描指令。
3. 四站 `tests/` 內 `keyboard` 僅一處命中（`comprehensive-functional.spec.ts:107` 的 `page.keyboard.press("Escape")`），無鍵盤導覽斷言。
4. 四站 `globals.css` 皆有全域 `:focus-visible` 兜底與 `.skip-link` 樣式，並皆有 `prefers-reduced-motion` 區塊。
5. skip link 目標 `#main-content` 僅 brand-portal 3 頁定義，其餘三站 0 處。
6. `user-scalable` / `maximum-scale` 全 `web/` 零命中；tech-portal 顯式宣告 viewport 且註解寫「允許放大(a11y)」；另三站無 `viewport` export。
7. `web/shared-contract/src/mutation.ts` 明文定義 retry 同 key、offline/5xx/409 rollback、敏感操作禁用 optimistic（`:1-9`、`:143-152`、`:203-215`）。
8. `createMutationAction` 的使用端只有 brand-portal 兩處（`NotificationDrawer.tsx:224`、`preferences.ts:67`）；另三站零命中。
9. 四站無表單草稿本地暫存；`localStorage` 用途為主題、語系、閒置時間戳、PWA 提示。
10. `navigator.onLine` 與 `offline` 事件監聽在四站 `src/` 零命中；斷網文案由 `apiError.ts:119` 產生。
11. 對比的 token 層檢核只有 tech-portal 一站（`themeContrast.test.ts:80`，門檻 4.5）。
12. NFR-A11y-001（LINE 端）的驗證方式在 `05_NFR.md:203` 記為「平台保證」，無程式碼落點。
13. `20_Test_Cases.md:221`、`:223-225` 記載 NFR-A11y-001/003/004/005 的追溯狀態為「⚠ 完全沒有案例」，同檔 `:431` 又列有 TC-NFR-A11Y-01 一列。
14. critical a11y 數、200% 縮放版面、實際 tab 順序與螢幕閱讀器播報屬執行期量測，本次未取得。
