# 13 安全與生產準備檢查清單 — web 子系統

| 欄位 | 值 |
|---|---|
| 文件編號 | web-P3-13 |
| 版本 | v1.0 |
| 日期 | 2026-07-07 |
| 服務 | web（smartlock-admin 多站前端）|
| 作者 | web 技術文件撰寫者 |
| 狀態 | 草稿（現況 as-is baseline）|

> **安全現況摘要**：web 的路由保護、認證、RBAC gate **全部在瀏覽器端執行**，且 **JWT 存 localStorage（非 httpOnly cookie）+ 前端 `atob` 不驗簽**。這意味著：(1) client-side gate 只是 UX 層，不是授權邊界；(2) XSS 可竊 token 為頭號問題；(3) rolePolicy 未列路由 **fail-open**（與 deny-by-default 相反）。真正授權完全依賴後端 `role_required`。前端目前**不應被視為任何安全邊界**。

---

## A. 核心原則

| 項目 | 狀態 | 說明 |
|---|---|---|
| A-01 最小權限（Least Privilege）| ⚠️ 部分實施 | 前端有 role gate（`rolePolicy.ts`）但只影響「能否載入頁面」；真正權限由後端把關。前端 gate 未列路由 fail-open，非最小權限 |
| A-02 縱深防禦（Defense in Depth）| ⚠️ 部分實施 | 後端 api 有 `role_required` 為主防線；前端 gate 為輔（UX）。但前端層可被繞過（直接呼叫 api 帶 token）|
| A-03 安全預設（Secure Defaults）| ❌ 未達標 | `rolePolicy.ts:80` 未列路由**預設放行**（fail-open），非 secure default |
| A-04 可審計性（Auditability）| ⚠️ 部分實施 | 後端有 audit-events（`/admin/audit-events`）；前端 gate 決策無集中日誌 |
| A-05 安全失效（Fail Secure）| ❌ 未達標 | 新增敏感頁若忘記登記 ROUTE_POLICY，即對所有角色開放（fail-open）|

---

## B. 資料安全

| 項目 | 狀態 | 說明 |
|---|---|---|
| B-01 傳輸加密（TLS）| ⚠️ 部分實施 | 本機 compose 用 `http://`/`ws://`；雲端須 `https://`/`wss://`（build ARG 換值）。公網部署須強制 TLS |
| B-02 Cookie 安全屬性 | ❌ **不適用/未採用** | **token 不存 cookie，存 localStorage**（`api.ts:109-118`）。keys：`smartlock.access_token` 等（`api.ts:30-35`）。故無 HttpOnly/Secure/SameSite 保護 |
| B-03 敏感資訊不存 localStorage | ❌ **違反（頭號問題）** | access/refresh token + tenant_id + email 全存 localStorage。**任何 XSS 即可讀取並竊取 token**，冒用身分呼叫後端 |
| B-04 JWT 簽章驗證 | ❌ 未達標（設計如此）| 前端 `atob` decode JWT payload 讀 `sub`/`role`/`tenant_id`（`api.ts:183-206`），**不驗簽**。前端信任 claim 只為 UX 導頁；篡改 role claim 不會通過後端（後端驗簽）但會改變前端 gate 行為 |
| B-05 多租戶隔離 | ❌ **有資料外洩風險** | 無有效 tenant 時 `X-Tenant-ID` 靜默退回 1 號租戶 `FALLBACK_TENANT_ID`（`api.ts:120-135`）。**code 內 TODO 已標「正式環境應擋下並導回登入，多租戶資料外洩風險」**（`api.ts:126-129`），屬跨 12 頁行為變更待業主裁決 |
| B-06 XSS 防護 | ⚠️ 部分實施 | React JSX 預設轉義；但因 token 存 localStorage，一旦有 XSS 洞（如未轉義的 `dangerouslySetInnerHTML`、第三方 script）後果加倍（可直接竊 token）。需稽核所有 HTML 注入點 |
| B-07 WS token 曝露 | ⚠️ 風險 | JWT 走 WS/SSE query param（`realtime.ts:67-68`、`sse.ts`），可能被反代 log 記錄。屬 localStorage token 缺口延伸 |
| B-08 個資最小化 | N/A | web 呈現派工/客戶/工單資料；個資保護主責在後端 |

---

## C. 應用程式安全

| 項目 | 狀態 | 說明 |
|---|---|---|
| C-01 身分驗證（Authentication）| ⚠️ 部分實施（client-only）| AuthGuard 只驗「token 存在」不驗「是否過期/有效」（`AuthGuard.tsx:59-64`）；過期 token 靠 api 層 401 兜底導登入（`api.ts:255-278`）。**無 server-side 驗證、無 Next middleware**（`find middleware.ts` 零命中）|
| C-02 授權控制（RBAC）| ⚠️ 部分實施（client-only, 非邊界）| `rolePolicy.canAccessRoute` longest-prefix 表（`rolePolicy.ts:24-82`）只擋「頁面載入」；`admin/tenant_admin/super_admin` 全放行；真正授權在後端 `role_required` |
| C-03 **client-side gate 只是 UX 非授權邊界** | ❌ 未達標（架構性）| APP_MODE gate（`crossModeRedirect`）與 rolePolicy 全在瀏覽器跑（`AuthGuard.tsx`）。**未授權路由的 JS bundle 仍會下載到瀏覽器**，僅靠 client redirect 擋。攻擊者可停用 JS / 直接讀 bundle / 直接呼叫 api（帶 token）繞過整個前端 gate |
| C-04 rolePolicy **fail-open** 缺口 | ❌ 未達標 | `rolePolicy.ts:80`：未列到的路由**預設放行**（`if (matches.length === 0) return true`）。新增敏感頁若忘記登記 ROUTE_POLICY，即對所有登入角色開放。與 deny-by-default 相反。註解自承「demo 安全」|
| C-05 `/platform/*` deny-by-default | ✅ 已實施（唯一例外）| `/platform/*` 在 FULL_ACCESS 早退**之前**特例：只 `platform_admin` 可進，品牌超級角色亦擋（`rolePolicy.ts:73-75`）。此為對稱 deny-by-default，是全表唯一 secure default |
| C-06 Token 刷新機制 | ✅ 已實施 | 401 → refresh once（in-flight 去重）→ 重放；失敗清 token 導登入（`api.ts:316-324`）。refresh 端點依 role 分流（`api.ts:229-232`）|
| C-07 CSRF | N/A（因非 cookie）| token 走 Authorization header 非 cookie，傳統 CSRF 面較小；但 localStorage 換來 XSS 面加大（trade-off 方向相反）|
| C-08 安全 HTTP Headers | ⚠️ 部分實施 | `next.config.ts` 未設 CSP/X-Frame-Options/X-Content-Type-Options（`next.config.ts` 只有 output + optimizePackageImports）。CSP 對緩解 XSS 竊 token 尤其重要 `[待確認]` 是否於反代層補 |
| C-09 Console log 洩漏 | ⚠️ 部分實施 | realtime `logErrors` 預設 false（`realtime.ts:48`）；其餘 console 使用 `[待確認]`，生產應移除 |
| C-10 輸入驗證 | ⚠️ 部分實施 | 表單驗證在各頁 client；後端為主防線。無集中 schema 驗證庫（無 zod/yup 於 package.json）`[待確認]` |
| C-11 Open Redirect | ⚠️ 部分實施 | crossModeRedirect 導向目標來自 build-time 烤入的 `*_PORTAL_URL`（非使用者輸入），面較小；session 失效導頁用固定登入路徑（`api.ts:257-267`）|

---

## D. 基礎設施安全

| 項目 | 狀態 | 說明 |
|---|---|---|
| D-01 NEXT_PUBLIC_* build-time 曝露 | ⚠️ 設計限制 | 8 個 `NEXT_PUBLIC_*` 於 `next build` 烤入 bundle（`Dockerfile:44-73`），**全數會出現在瀏覽器可讀的前端 bundle**。皆為非機密（API base、portal URL、APP_MODE），無 secret 誤放。但改後端網域須 rebuild 全部 web image（見 D-02）|
| D-02 環境切換僵化 | ⚠️ 設計限制 | 同一 image 無法 runtime 切 API base / portal URL；每環境每 portal 各一 build（4 portal = 4 build，雖共用 Dockerfile）。改後端網域須 rebuild 全部 web image（`Dockerfile:44-73`）|
| D-03 Container 映像安全 | ✅ 部分實施 | runtime 用 node:20-alpine **非 root**（uid 1001，`Dockerfile:87-102`）；standalone 只 copy 必要檔（無 npm/build tool），攻擊面小 |
| D-04 Secrets 管理 | ✅ 已實施（web 端無 secret）| web 前端本質不持機密（token 由使用者登入取得）；build ARG 皆非機密 |
| D-05 健康檢查端點 | ⚠️ 部分實施 | standalone `node server.js` EXPOSE 8080；健康探針 `[待確認]` |
| D-06 相依服務斷線處理 | ✅ 已實施 | WS/SSE base 未配置或斷線 → 靜默降級（`realtime.ts:50-53`、`sse.ts:10-14`），頁面仍以一般 fetch 運作，不 crash |
| D-07 依賴鎖定 | ✅ 已實施 | `package-lock.json`（`npm ci`，`Dockerfile:23-26`）|
| D-08 依賴 CVE 掃描 | ⚠️ 部分實施 | `npm ci --no-audit`（build 時關閉 audit）；CI 是否獨立跑 `npm audit` `[待確認]` |

---

## E. 合規

| 項目 | 狀態 | 說明 |
|---|---|---|
| E-01 OWASP Top 10 對照 | ❌ 未實施 | 無正式對照文件。**A01 Broken Access Control（client-only gate + fail-open）與 A07 Identification/Auth（localStorage token + 不驗簽）為本系統最高風險** |
| E-02 SAST/DAST | ⚠️ 部分實施 | TS strict（`tsconfig.json:7`）；ESLint `[待確認]`；無 SAST/DAST 工具跡象 |
| E-03 第三方套件授權 | ⚠️ 部分實施 | 主要套件（Next/React/Radix/Tailwind/lucide/recharts）為 MIT，一般無商業限制；完整審查 `[待確認]` |
| E-04 滲透測試 | ❌ 未實施 | 無記錄。在 cookie 認證 + deny-by-default 修復後應做基礎 pentest |

---

## F. 審查結論

### F.1 具體行動項

| 編號 | 行動項 | 優先度 | 說明 |
|---|---|---|---|
| ACT-01 | **JWT 改 httpOnly cookie + server 端驗證** | P0 | 消除 localStorage token（B-03）+ 不驗簽（B-04）。token 移入 httpOnly cookie，路由保護改由 Next middleware / RSC 在 server 端驗簽 + 驗過期。屬架構變更，須走 CIA |
| ACT-02 | **rolePolicy catch-all 改 deny-by-default** | P1 | 修 `rolePolicy.ts:80` fail-open（C-04）：未列路由改拒絕；新增敏感頁強制登記，並加 CI 檢查漏登記 |
| ACT-03 | **fallback tenant 擋下導登入** | P1 | 修 `api.ts:120-135`（B-05）：無有效 tenant 不再靜默退 1 號租戶，改擋下導登入。屬跨 12 頁行為變更，**須先出 CIA 等業主裁決**（code 內 TODO 已標）|
| ACT-04 | **設定安全 HTTP Headers（CSP 優先）** | P1 | `next.config.ts` 或反代加 CSP / X-Frame-Options / X-Content-Type-Options（C-08）。CSP 對緩解 XSS 竊 token 特別關鍵 |
| ACT-05 | **評估抽出 BFF / route handler** | P2 | 讓 token/tenant 不再全暴露瀏覽器，並可在 server 端做真正 gate（見 ADR-003 重評觸發）|
| ACT-06 | **runtime env 注入取代 build-time 烤入** | P2 | 消除 D-01/D-02 部署僵化，4 portal 共用單一 image |
| ACT-07 | **建立 XSS 注入點稽核 + 依賴 CVE 掃描** | P2 | 稽核所有 `dangerouslySetInnerHTML`；CI 加 `npm audit` gate |

### F.2 整體評估

> **結論：前端不可視為安全邊界；上線安全依賴後端 `role_required` 是否完整 enforce。**

**主要理由：**

1. **client-side gate 只是 UX**（C-03）：APP_MODE gate 與 rolePolicy 全在瀏覽器跑，未授權路由 bundle 仍下載，可被停用 JS / 直接呼叫 api 繞過。web 層擋不住惡意存取。
2. **localStorage token + 不驗簽**（B-03/B-04）：頭號問題。任何 XSS 即可竊 token 冒用身分。
3. **fail-open**（C-04）：未登記敏感頁對所有登入角色開放，與 deny-by-default 相反。
4. **多租戶 fallback 資料外洩風險**（B-05）：無 tenant 靜默退 1 號租戶。

**與平台層一致性**：本結論對應平台 L1 缺口 **G-11「前端認證全 client-side」**（`00_platform/P1/05` §5）。真正 enforce 缺口在平台 **G-02「RBAC 授權矩陣 shadow-mode」**（後端 80+ 寫入端點僅 `require_tenant` 不檢角色）——即前端 gate 與後端 enforce **雙層都尚未成為真正邊界**，須並行修復。

**上線前必要條件**：完成 ACT-01/ACT-02/ACT-03 後重新驗收——
- localStorage 不再存 token（改 cookie），XSS 無法直接竊取。
- 未登記敏感頁對非授權角色預設拒絕（deny-by-default）。
- 無有效 tenant 時導登入而非退 1 號租戶。
- 後端 `role_required` 對所有寫入端點 enforce（跨 api 子系統，非 web 單獨可達成）。

---

## G. 生產準備

| 項目 | 狀態 | 說明 |
|---|---|---|
| G-01 建置流程 | ✅ 已實施 | `npm run build`（standalone）+ 三階段 Dockerfile |
| G-02 E2E 測試 | ⚠️ 部分實施 | Playwright（`package.json:26`）；覆蓋範圍 `[待確認]`。無單元測試框架 |
| G-03 錯誤邊界 | ✅ 已實施 | `error.tsx` / `global-error.tsx` / `not-found.tsx` / `_error-parts/`（App Router）|
| G-04 完成度落差揭露 | ⚠️ 部分實施 | page-status.md 統計 **✅ 85 / 🟡示意 UI 12 / ⏳待接入 25**（更新 2026-06-07）。platform console 為 R1 骨架 |
| G-05 **假流程隱藏（UAT）** | ✅ 已實施 | `UAT_HIDE_FAKE_FLOWS = true`（`src/lib/uatFlags.ts`）：把「畫面有反應但金流/後端未接通」的假流程隱藏。**退款核准不真退錢**，整條入口 + `/admin/refunds` 整頁 + 側欄以此 flag 隱藏（`Sidebar.tsx:98-100`）。另隱藏：工單遙測示意、遠端開鎖/重置密碼、SLA 達標率寫死卡、KPI/營收佔位塊。UAT 結束或模組接通後改 `false` 恢復（code 都留著）|
| G-06 健康端點 | ⚠️ 部分實施 | standalone server；liveness probe `[待確認]` |
| G-07 依賴鎖定 | ✅ 已實施 | `package-lock.json` |
| G-08 Rollback | ⚠️ 部分實施 | Docker image tag 管理；CD `[待確認]`（平台 L1 G-12「無 CD pipeline」）|

---

*文件結尾 — web 安全與生產準備 v1.0 / 2026-07-07*
</content>
