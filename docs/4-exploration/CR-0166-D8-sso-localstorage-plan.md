# CR-0166 D8 — SSO 三站複製＋localStorage 退場（ACT-01）

- **日期**：2026-07-12
- **依據**：2.1.1 R3、CR-0146（brand-portal OIDC 授權碼流參考實作）、ADR-024。

## §1 SSO 三站複製 ✅ 完成

brand-portal 的 OIDC 授權碼流複製到 tech-portal 與 platform-console：

| 元件 | brand（參考） | tech-portal | platform-console |
|---|---|---|---|
| server callback（code→token→httpOnly cookie） | `auth/callback/route.ts` | ✅ 複製（error→/tech-login） | ✅ 複製（error→/platform/login） |
| SSO 落地頁（fragment→session→角色導向） | `auth/sso-complete/page.tsx` | ✅ 複製 | ✅ 複製 |
| 登入頁 SSO 鈕（client 組 redirect_uri） | `login/page.tsx` | ✅ tech-login | ✅ platform/login |

**驗證**：三站 tsc 0；Casdoor（:8005）authorize 端點 200；app redirect_uris 已含
3000/3001/3003（本機四站皆白名單）；callback route 與 brand 版位元組相同（僅 error 導向
路徑差異）——correctness 承 CR-0146 brand-portal live E2E。SSO 鈕 env-gated
（NEXT_PUBLIC_CASDOOR_ENDPOINT 設才顯示，opt-in）。

## §2b localStorage 退場（ACT-01）— ✅ 業主裁決 B 已實作（2026-07-12）

業主裁決 **B（可讀 claims cookie）**。三站 `api.ts` 實作：
- 非 httpOnly `smartlock_claims` cookie（JSON: userId/role/tenantId/email，samesite=lax，
  https 加 secure，1h）——非機密（本就在 JWT 內可讀）。
- **單一寫入點 `auth.setTokens`**：解 JWT payload → 寫 claims cookie（SSO sso-complete
  與密碼登入皆走此，一處覆蓋兩路徑）；`setTenantId`/`setEmail` 同步更新；`clear` 清除。
- `getCurrentSession()`：**優先讀 claims cookie**（退場目標態），退回 localStorage JWT
  解碼（過渡：既有 session／cookie 缺失時，零破壞）。
- `auth.getTenantId()`/`getEmail()`：優先 claims cookie，退回 localStorage。

**過渡安全**：claims cookie 缺失／parse 失敗 → 自動退回 localStorage，既有登入不破。
auth token 仍走 httpOnly cookie（SSO）＋Authorization header（localStorage 過渡）——
本步只退場「前端 session claims 的 localStorage 依賴」（30+ 頁 getCurrentSession/getTenantId），
token 傳輸層的 localStorage→cookie 遷移屬更後續（需 fetch credentials:include＋密碼登入
設 cookie，較大改動面，另排）。

## §2 localStorage 退場（ACT-01）— 架構選項（B 已採用）

**現況（dual-write）**：SSO callback 已寫 **httpOnly cookie**（`smartlock_access_token`，
api 端 R1 cookie 來源支援）＋fragment→localStorage（既有 `getCurrentSession()` 依賴）。
三站現在都有 cookie 基礎。

**退場的技術障礙**：`getCurrentSession()` 為**同步**、從 localStorage 解 JWT 取
role/tenant（30+ 頁同步依賴）。httpOnly cookie **JS 不可讀**（安全設計），故不能直接
用 cookie 取代 localStorage 的 claims 來源。

**兩條路（架構裁決）**：
- **A. 非同步 session（/me 端點）**：getCurrentSession → async fetch `/me`（api 用
  cookie 認證回 role/tenant）。**30+ 頁同步→非同步改造**（每頁 auth 判斷改 async／
  Suspense）——高改動面、高風險（改錯即三站登入壞）。
- **B. 可讀 claims cookie**：callback 額外寫一個**非 httpOnly** 的 `smartlock_claims`
  cookie（僅 role+tenant，非機密路由用途；auth token 仍 httpOnly）；getCurrentSession
  改讀此 cookie。**改動面小、維持同步**，但多一個 cookie＋需確認 role/tenant 非機密可暴露。

**建議＝B**（改動面小、維持同步 getCurrentSession、風險低；auth token 仍 httpOnly 不暴露）。

## §3 🛑 待業主裁決

- **D8-a**：localStorage 退場採 **A 非同步 /me**（乾淨但 30+ 頁大改）還是 **B 可讀 claims
  cookie**（建議，小改維持同步）？
- 裁決後我實作退場（B 約 1 輪；A 需分頁漸進多輪）。SSO 三站複製本身已完成可用。

> **本輪交付**：SSO 三站複製（三站登入皆支援 OIDC，cookie 基礎就緒）。localStorage
> 退場是需架構裁決的獨立步驟——不在無裁決下盲改 30+ 頁 auth（破壞面大）。
