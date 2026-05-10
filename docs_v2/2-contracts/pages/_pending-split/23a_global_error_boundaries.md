# Page-Level Prompt: Global — Next.js Error Boundaries 全域錯誤邊界

> IA 編號 **G3**（Global 類）。涵蓋 Next.js App Router 三層 segment-level error pages：404 not-found、500 segment error、global root error。
> 與 [[23_global_offline]] 互補：23 處理「無網路」，23a 處理「有網路但伺服器/路由出錯」。

---

## [PAGE META]

- **page_name**: Next.js Error Boundaries
- **route_path**: 多重（依層級）
  - `/not-found` (Next.js convention，不可路由直達)
  - `/error` (segment-level)
  - global-error 為 root layout 錯誤備援
- **page_type**: full-screen error pages
- **ia_pages**: G3
- **openapi_ops**: none
- **asyncapi_ops**: none
- **primary_goal**: 任何路由 / segment / root layout 錯誤時提供明確訊息與恢復路徑
- **secondary_goal**: 開發環境提供 debug 資訊，生產環境保護敏感堆疊
- **target_users**: 全部使用者（Admin 與 Tech 共用）
- **entry_point**:
  - 404: 路由匹配失敗 / `notFound()` 拋出
  - error.tsx: server component / route segment 拋出未捕獲 error
  - global-error.tsx: root layout / providers 自身崩潰
- **expected_time_on_page**: 5-15 秒（讀訊息後返回或重試）

---

## [STRUCTURE: SECTIONS]

### G3.1 Not-Found Page (`web/src/app/not-found.tsx`)
1. **icon_section** - lucide `FileQuestion` 或 `MapOff`，64px，灰色
2. **title** - H1「頁面不存在」
3. **subtitle** - Body「您訪問的頁面可能已被移除或網址有誤」
4. **action_row** - 「返回上一頁」（client subcomponent BackButton 用 useRouter().back()）+ 「返回儀表板」連結 to /dashboard

### G3.2 Segment Error Page (`web/src/app/error.tsx`)
1. **icon_section** - lucide `AlertCircle` 或 `ServerCrash`
2. **title** - H1「發生錯誤」
3. **subtitle** - Body「請稍後再試或聯絡技術支援」
4. **error_digest** - Mono text / required / 顯示 `error.digest`（生產） / 完整 stack（開發）
5. **action_row** - 「重試」（呼叫 reset() prop）+ 「返回儀表板」

### G3.3 Global Error (`web/src/app/global-error.tsx`)
1. **inline_styles** - 樣式內聯（不依賴 globals.css，root layout 可能已掛）
2. **html_body** - 自帶 `<html>` `<body>` tag（Next.js 規範）
3. **system_font_stack** - 不依賴 next/font
4. **title** - 「系統發生嚴重錯誤」
5. **action** - 「重新載入」（window.location.reload()）

### G3.4 Network Error Banner (`web/src/components/ui/NetworkErrorBanner.tsx`)
- 不是頁面而是 component，由 layout 或頁面 mount
- listener: `navigator.onLine` + `window.addEventListener('online'/'offline')`
- 斷線：fixed top 紅橙色橫幅「網路連線中斷，正在嘗試重連...」
- 重連：3 秒「已恢復連線」綠色後自動消失
- SSR safety: `mounted` flag 守住 hydrate 前不渲染

---

## [INTERACTION & STATE FLOW]

| 觸發 | 顯示頁面 | 主要動作 |
|:---|:---|:---|
| 路由不存在 / `notFound()` | not-found.tsx | 返回上一頁 / 返回儀表板 |
| Server component throw | error.tsx | 重試（reset） / 返回儀表板 |
| Root layout / provider crash | global-error.tsx | 重新載入頁面 |
| `navigator.offline` event | NetworkErrorBanner | 等待自動重連 |

### 開發 vs 生產差異

- **開發**：error.tsx `<details>` 展開完整 error stack；global-error 顯示 error.message
- **生產**：error.tsx 僅顯示 `error.digest`（給 SRE 對應 log 使用）；global-error 不洩漏 stack

---

## [ACCEPTANCE CRITERIA]

- [ ] 訪問不存在路由顯示 not-found.tsx，圖示與字體正常
- [ ] segment 拋錯顯示 error.tsx，重試按鈕呼叫 reset() 後恢復
- [ ] root layout 拋錯顯示 global-error.tsx，內聯樣式正常（不依賴外部 CSS）
- [ ] NetworkErrorBanner 在 navigator.onLine=false 時顯示，恢復後 3s 自動消失
- [ ] 生產模式不洩漏 error.message / stack
- [ ] 無障礙：error.digest 用 monospace + 可選取（方便用戶複製給支援）
- [ ] 鍵盤可達：所有 action button focus 順序正確

---

## 導航與狀態 (Navigation & State)

- **Upstream**: 任何路由 / 任何 segment
- **Downstream**: 重試成功回原路由；返回儀表板進 /dashboard
- **State Persistence**: 無
- **Error Navigation**: error.tsx 的「reset」呼叫 Next.js 提供的 reset prop，自動清除錯誤邊界狀態

完整規範參考 [[02-design/E5x--frontend-architecture]] 錯誤處理章節。

---

## 校對檢核表

- [ ] 開發模式 stack 顯示在 `<details>` 收起 vs 直接展開？
- [ ] error.digest 字體大小是否方便複製？
- [ ] NetworkErrorBanner 是否在路由切換時保持顯示？
- [ ] global-error 是否需要 i18n（V2.0 才考慮）？
