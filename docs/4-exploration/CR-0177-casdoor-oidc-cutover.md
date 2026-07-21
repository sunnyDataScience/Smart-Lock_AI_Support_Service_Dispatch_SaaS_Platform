---
id: CR-0177
title: Casdoor OIDC 統一身分 cutover — 登入改發 Casdoor token + 前端 localStorage 退場
status: in-progress
tier: 4-exploration
type: CIA
date: 2026-07-21
decided: 2026-07-21（業主「照建議」——HD-1~HD-7 全採建議欄）
author: Claude (codegraph 稽核驅動)
related:
  - FR-WEB-02 / FR-PLT-01 / NFR-Sec-002
  - ADR-P003（Casdoor 統一 IdP）/ ADR-024（client SPA 無 BFF / OIDC）
  - CR-0146（OIDC 授權碼流 web 接線）/ CR-0166 D8+D8-a（SSO 三站複製 + claims cookie）
  - WBS 2.1.1（M2，In Progress）
  - docs/audit/v1-gap-codegraph-scan-20260721.md（FR-WEB-02/PLT-01「部分」）
gate: 🛑 停在 §8 等業主裁決，未實作任何 code
---

# CR-0177 — Casdoor OIDC 統一身分 cutover

## §0 TL;DR

- **文件宣稱**（FR-PLT-01 / FR-WEB-02 / NFR-Sec-002）：Casdoor 為**單一身分真相源**，各服務驗 Casdoor OIDC token；前端**棄 localStorage 自解 token**。
- **實作現況**：**半套**。授權碼流 + httpOnly cookie 已落地（CR-0146/D8）、claims cookie 已建（D8-a），但
  ① **登入端仍簽本地 HS256 JWT**（`core/auth.py:50 create_token`，`API_JWT_SECRET_KEY`），Casdoor 僅為 **opt-in 雙驗 fallback**（`deps.py:50` HS256 優先 → 失敗才驗 Casdoor RS256）；
  ② **前端 localStorage 未退場**——四站共 **130 處**命中（brand 37 / tech 38 / platform 36 / landing 19），`decodeJwtPayload`（`api.ts:253`）仍在用。
- **本 CR 目的**：把「Casdoor 是真相源」從半套推到 cutover。**但這牽動三道 per-request 本地安全狀態檢查**（`revoked_jti` 撤銷、`ACCOUNT_DISABLED`、`TOKEN_STALE`）與密碼/鎖定/忘記密碼流程 —— 不是單純換簽章演算法。
- **這是 API contract + 架構邊界 + 外部整合 + user flow 級變更** → change-governance 硬 gate：**先 CIA、停 §8、等裁決**。本文即該 CIA。

---

## §1 觸發判定（7 面向）

| 面向 | 命中 | 說明 |
|---|---|---|
| User/Business flow | ✅ | 登入/登出/刷新/改密/忘記密碼全流程改由 Casdoor 主導 |
| API contract | ✅ | `loginAdmin`/`loginTechnician`/`refreshToken`/`logout` 回應與語意變動 |
| Domain model | ✅ | 身分真相源由 `users`（本地密碼）移向 Casdoor；`users` 降為映射/授權投影 |
| DB schema | ⚠️ | 視 HD-2：若密碼移交 Casdoor，`password_hash`/`failed_login_attempts`/`locked_until`/`password_changed_at` 語意變更或退場 |
| External integration | ✅ | Casdoor 成為**線上關鍵路徑依賴**（原僅 opt-in 驗證備援）→ 可用性 SPOF |
| Test plan | ✅ | 認證測試全面改寫（現測試以 `_make_token` 自簽，見 `api/tests/conftest.py:77`） |
| Architecture boundary | ✅ | ADR-P003/ADR-024 的落地形態改變 |

→ 7 面向命中 6.5，**CIA 必須**。

---

## §2 現況（as-is，codegraph 實據）

**簽發（本地）**
- `api/core/auth.py:50 create_token`：HS256 簽 `{sub, role, tenant_id, type, iat, exp, jti}`，secret＝`API_JWT_SECRET_KEY`；access 60min / refresh 30d（rolling）。
- `api/routers/auth.py`：`loginAdmin:139`、`loginTechnician:151`、`refreshToken:164`、`logout:174`、`changePassword:193`。
- `auth_service._build_login_payload:74`、`platform_admin_service._build_login_payload:45` 各自簽 access+refresh。

**驗證（雙軌）**
- `api/core/deps.py:50 _decode_any_token`：**自簽 HS256 優先**；失敗且 OIDC 已配置 → `verify_oidc_token`。
- `api/core/oidc.py:56 verify_oidc_token`：驗 Casdoor RS256（issuer/audience），經 `properties.smartlock_user_id`／`smartlock_role`／`tenant_id` 映射回本地身分；**未 bootstrap 映射的帳號一律拒絕**（不 fallback 到 Casdoor 原生 sub）。

**per-request 本地安全狀態（三道，cutover 的真正難點）**
- `revoked_jti` 撤銷查詢（登出即撤）→ 401 TOKEN_REVOKED
- `users.is_active` → 403 ACCOUNT_DISABLED
- `iat < password_changed_at` → 401 TOKEN_STALE（改密踢舊 session）
- 另有 A1 登入鎖定（`failed_login_attempts`/`locked_until`，`auth_service`）

**前端**
- SSO 授權碼流：`web/*/app/auth/callback/route.ts`（`grant_type=authorization_code` → httpOnly cookie）＋ `auth/sso-complete`。
- D8-a claims cookie：`api.ts:140 ClaimsCookie` / `:147 writeClaimsCookie` / `:158 readClaimsCookie`；`getCurrentSession:266` **claims cookie 優先、localStorage 退回（過渡）**。
- `decodeJwtPayload:253` 仍存在；**localStorage 四站共 130 處**（含 auth token / session claims / 疑似 UI 偏好，需 S0 分類）。

---

## §3 目標（to-be）

1. **登入端發 Casdoor token**：`loginAdmin`/`loginTechnician` 改為（a）導向 Casdoor 授權碼流，或（b）後端以 Casdoor password grant 代換 → 回 Casdoor access/refresh。
2. **驗證單軌**：`_decode_any_token` 移除 HS256 分支（或僅留內部服務用途）。
3. **前端零 localStorage 讀 session/token**：token 走 httpOnly cookie、claims 走 claims cookie；`decodeJwtPayload` 退場。
4. **三道安全狀態檢查在 Casdoor 世界仍成立**（見 §8 HD-3）。

---

## §4 契約 / 介面影響

| 端點 | 現況 | cutover 後 |
|---|---|---|
| `POST /auth/login`（loginAdmin） | 回本地 HS256 access+refresh | 依 HD-1/HD-5：回 Casdoor token，或改為回「導向 Casdoor 授權 URL」（**breaking**） |
| `POST /auth/login/technician` | 同上 | 視 HD-1 是否納入技師 |
| `POST /auth/refresh` | 本地 refresh 換新 access（rolling） | 依 HD-4：改用 Casdoor refresh grant，或保留本地 |
| `POST /auth/logout` | 寫 `revoked_jti` | 依 HD-3：可能改/併 Casdoor 撤銷 |
| `POST /auth/change-password` | 改本地 `password_hash` + 更新 `password_changed_at` | 依 HD-2：可能移交 Casdoor（本端點退場或代理） |

前端四站登入頁、AuthGuard、`api.ts` session 層全數受影響。

---

## §5 身分模型影響

- `users` 由「身分真相源（含密碼）」降為「**本地授權/FK 投影**」——`smartlock_user_id` 映射成為關鍵（`verify_oidc_token` 已依賴之）。
- 新增運維要求：**Casdoor 帳號 ↔ users 映射必須完整**，否則該帳號直接鎖死（現行邏輯即拒絕未映射帳號）。既有帳號需 bootstrap 對映（`scripts/idp/casdoor_bootstrap.py` 已有 upsert_user/upsert_role）。

---

## §6 DB schema 影響

依 HD-2：
- **密碼留本地** → schema 不動（Casdoor 僅發 token，密碼仍本地驗）——但這與「Casdoor 為單一真相源」有張力。
- **密碼移交 Casdoor** → `users.password_hash` 退場、A1 鎖定（`failed_login_attempts`/`locked_until`）與 `password_changed_at` 語意移轉到 Casdoor（TOKEN_STALE 需改判準，見 HD-3）；忘記密碼流程改由 Casdoor 提供。

---

## §7 測試計畫影響

- `api/tests/conftest.py:77 _make_token` 全測試以**自簽 token** 建立情境 → cutover 後需 mock Casdoor 或保留測試用簽發路徑（**否則全套認證測試崩**）。
- 新增：Casdoor token 驗證/映射缺漏拒絕、撤銷語意、Casdoor 不可用時的降級行為、四站 SSO 端到端。

---

## §8 🛑 Human Decisions Required（等業主裁決，未動 code）

| # | 決策 | 選項 | 我的建議 |
|---|---|---|---|
| **HD-1** | **cutover 範圍** | (a) 僅品牌 staff 登入 (b) +平台 admin (c) +技師登入（技師在權威庫、另有註冊流） | **(a) 先行 → (b) → (c) 分批**：技師端有獨立註冊/KYC 流程，一次全上風險過高 |
| **HD-2** | **密碼歸屬** | (a) 留本地（Casdoor 僅發/驗 token） (b) 移交 Casdoor（單一真相源） | **(a) 先行**：移交會連動 A1 鎖定/改密踢 session/忘記密碼三條已驗收流程；(b) 列為第二階段 |
| **HD-3** | **token 撤銷 + 三道安全檢查** | (a) 保留本地 `revoked_jti`＋以 Casdoor `jti` 為鍵 (b) 改用 Casdoor introspection (c) 兩者併行 | **(a)**——現行 `verify_oidc_token` 已回 `jti`，本地撤銷與 ACCOUNT_DISABLED 可續用；**但須先驗證 Casdoor 確實簽發 jti**（S0 驗證項）。TOKEN_STALE 若 HD-2 選 (a) 亦可續用 |
| **HD-4** | **refresh 流程** | (a) 保留本地 refresh (b) 改 Casdoor refresh grant | **(a) 先行**：refresh 換新是已驗收的滾動機制；改動會牽動閒置登出（60min）等既有行為 |
| **HD-5** | **過渡策略** | (a) big-bang 切換 (b) **dual-accept 過渡期**（HS256 + RS256 並存，新登入發 Casdoor、舊 token 自然到期） | **(b)**——零停機、可回退；現行 `_decode_any_token` 本就雙軌，只需反轉優先序 |
| **HD-6** | **Casdoor 可用性降級** | (a) 純度優先：Casdoor 掛 = 無法登入 (b) 保留本地 fallback 登入（緊急） | **(b)**——Casdoor 成為線上關鍵路徑後即 SPOF；建議保留 break-glass 本地登入（限 admin + 稽核告警） |
| **HD-7** | **localStorage 退場範圍** | (a) 僅 auth（token + session claims） (b) 全部 130 處（含 UI 偏好） | **(a)**——UI 偏好留 localStorage 無安全疑慮；S0 先分類 130 處 |

---

## §9 Suggested Implementation Order（待 §8 定案後）

- **S0 盤點/驗證**：① 四站 130 處 localStorage 分類（auth token / session claims / UI 偏好）② **實測 Casdoor 是否簽發 jti**（決定 HD-3 可行性）③ 既有帳號 Casdoor 映射覆蓋率盤點。
- **S1 後端雙軌反轉**（HD-5=b）：`_decode_any_token` 改 **RS256 優先、HS256 過渡接受**；測試 harness 保留自簽路徑。
- **S2 登入端切換**（HD-1 範圍）：`loginAdmin` 改發 Casdoor token（password grant 或導向授權碼流）；`revoked_jti`/ACCOUNT_DISABLED/TOKEN_STALE 依 HD-3 續接。
- **S3 前端 localStorage 退場**（HD-7 範圍）：`decodeJwtPayload` 移除、session 全走 claims cookie、四站同步（四站邏輯需位元組級一致，沿 D8 慣例）。
- **S4 break-glass**（HD-6=b）：本地緊急登入路徑 + 稽核告警。
- **S5 收尾**：移除 HS256 分支（過渡期滿）、更新 21_Traceability_Matrix / CHANGELOG / 完成度、WBS 2.1.1 收斂。

---

## §10 風險 / 回滾

- **R1（最高）Casdoor SPOF**：cutover 後 Casdoor 不可用＝全員無法登入。緩解：HD-6 break-glass + Casdoor HA（ADR-P003 已要求）。
- **R2 帳號映射缺漏鎖死**：未 bootstrap 的 Casdoor 帳號直接被拒。緩解：S0 覆蓋率盤點 + 上線前全量對映 + 缺漏告警。
- **R3 測試 harness 崩塌**：全套認證測試依 `_make_token` 自簽。緩解：S1 保留測試簽發路徑。
- **R4 三道安全檢查失效**（撤銷/停權/改密踢 session 是已驗收的 A1-A3 成果）。緩解：HD-3 定案後逐條回歸測試。
- **回滾**：S1-S2 於 dual-accept 期間可即時回退（反轉優先序）；S5 移除 HS256 為不可逆點，須確認過渡期無舊 token。

---

## §11 進度（branch `feat/cr-0177-casdoor-cutover`）

**§8 業主 2026-07-21 裁決：「照建議」全採建議欄。**

> ⚠️ **裁決連動**：HD-2＝密碼留本地 → 「登入端改發 Casdoor token」的 **password-grant 路徑不可行**
> （Casdoor 無密碼無法簽發）。cutover 正解調整為：**SSO 授權碼流成為主要登入路徑**（已建），
> 本地密碼登入退為 HD-6 的 break-glass。與 HD-6 自洽。

### ✅ S0 盤點/驗證 done（實測，非推論）

| 項 | 結果 |
|---|---|
| ① localStorage 分類 | auth key＝`access`/`refresh`/`email`/`tenant`；四站 130 處（brand 37/tech 38/platform 36/landing 19）多為這些 + helper |
| ② **Casdoor 是否發 jti** | ✅ **確認發**（本機 Casdoor `lock-platform-casdoor-1`:8005，password grant 實測 payload 含 `jti`/`iat`/`exp`/`iss`/`aud`/`sub`/`properties`）→ **HD-3(a) 本地 `revoked_jti` 可行** |
| ③ 帳號映射覆蓋率 | locksmart org 6/6 皆有 `properties.smartlock_user_id`，**0 人會被拒登**（本機；**prod 需重驗**，R2） |

### 🔴 S0 附帶發現（cutover 阻斷級，CIA 原文未涵蓋）

**`smartlock-portal` 的 `tokenFormat='JWT'`（Casdoor 預設）會把整個 user 物件塞進 access token**——
實測 payload 含 `password`（雜湊）、`passwordSalt`、`passwordType`、`totpSecret`、`recoveryCodes`、
`mfaEmailEnabled/PhoneEnabled`、`signinWrongTimes` 等。現況 OIDC 僅 opt-in fallback 故未爆；
**一旦 SSO 轉主要路徑，每個瀏覽器持有的 token 即內含密碼雜湊 + TOTP 金鑰 + 復原碼**
（httpOnly cookie 擋不住——token 本身就是載體）。

- **修法**：該 app `tokenFormat` 改 **`JWT-Custom`** + `tokenFields` 白名單（至少需
  `sub`/`name`/`owner`/`email`/`roles`/`properties`——`verify_oidc_token` 依賴
  `properties.smartlock_user_id`/`smartlock_role`/`tenant_id` 與 `roles`）。
- **不可用 `JWT-Empty`**：會連 `properties` 一起砍，身分映射直接失效。
- **S2 的硬前置**：此項未修前不得讓 SSO 轉主要路徑。本機可由 admin API 改；**prod 屬共用 infra 需 OPS**。
- 附帶確認：`expireInHours=1`／`refreshExpireInHours=720` 與本地 access 60min／refresh 30d 對齊。

#### ✅ tokenFormat 修復 done（2026-07-21，本機已套 + 三項驗收全過）

🚨 **踩到的雷：`tokenFields` 吃 Go struct 欄位名（首字大寫），小寫 JSON 名「靜默失效」**
——不報錯、`update-application` 回 ok、就是不吐該欄位。四變體實測：

| tokenFields | token 欄位數 | properties | 洩密 |
|---|---|---|---|
| `["Owner",…,"Properties"]`（大寫） | 19 | ✅ | 無 |
| `["Properties"]`（大寫） | 12 | ✅ | 無 |
| `["properties"]`（小寫） | 11 | ❌ | 無 |
| `[]`（空） | 11 | ❌ | 無 |

**定案值（本機已套）**：
```
tokenFormat = "JWT-Custom"
tokenFields = ["Owner","Name","DisplayName","Email","Id","Type","Roles","Properties"]
```
**驗收三項全過**：① properties 三欄齊全（映射可用）② 無 `password`/`passwordSalt`/`passwordType`/
`totpSecret`/`recoveryCodes`/`mfa*`/`ldap`/`permissions` ③ 標準 claim（`jti`/`iat`/`exp`/`iss`/`aud`/`sub`）
齊全 → **本地 `revoked_jti` 撤銷模型可續用，HD-3(a) 確認成立**。
token 由 80 欄（含憑證類）收斂為 19 欄（純身分/顯示）。

> ⚠️ **prod 待辦（OPS）**：prod Casdoor 的 `smartlock-portal` 需套**完全相同**的
> `tokenFormat`/`tokenFields`（**注意大小寫**）。未套前 prod 不得讓 SSO 轉主要路徑。

### ✅ S1 done — 後端 dual-accept（alg 路由）

`core/deps.py:_decode_any_token` 由「HS256 先試、失敗才試 OIDC」改為**依 JWT header `alg` 路由**：
RS256→`verify_oidc_token`（第一級公民）、HS256→`decode_token`（過渡接受）、alg 不可判讀→保守雙試（沿舊行為）。
**無 alg-confusion 風險**（兩路各自釘死演算法：HS256／RS256），並修正原本 RS256+OIDC 未配置時回傳誤導性 HS256 錯誤。
驗證：unit **6 passed**（RS256 路由／HS256 路由／**alg-confusion 防護斷言**／未配置明確錯誤／壞 token 雙試 ×2）。

### ⬜ 待續

- **S2 SSO 轉主要登入路徑** — ✅ **本機前置已解除**（tokenFormat 修復完成）。四站登入頁預設走 SSO、
  本地密碼降為 break-glass。⚠️ **prod 仍卡 OPS 套 tokenFormat**（見上）。
### 🔴 S3 撞到架構級阻斷：cookie 跨網域（2026-07-21 查證）

S3 目標態＝token 只存 httpOnly cookie（XSS 偷不到）。查證發現**在 prod 不會運作**：

| 事實 | 出處 |
|---|---|
| prod web＝`smart-lock-web-<projnum>.<region>.run.app` | `scripts/deploy/api.sh:283` |
| prod api＝`smart-lock-api-*.run.app`（**不同 hostname**） | `api.sh:34-35` |
| api 動態把 web URL 設為 `CORS_ORIGINS` | `api.sh:270-285`（證實跨源） |
| SSO callback 設 cookie **未帶 `domain`** → host-only 綁 **web** 網域 | `auth/callback/route.ts:61` |
| 前端 fetch 原**無** `credentials` | `api.ts`（僅注入 Authorization） |

**cookie 依「網域」共用、不看 port**：本機 web:3000／api:8000 同為 `localhost` → 天然共用
（本機測起來會「像可行」）；prod 兩個不同 hostname → **cookie 送不到 api**，且 `run.app` 在
Public Suffix List → **無法**設 `.run.app` 共用父網域 cookie。
→ 這解釋了 code 內「雙寫：httpOnly cookie（目標態）+ localStorage（過渡）」——cookie 路徑一直是
理想態，實際 API 認證全靠 localStorage + Authorization header。
**若貿然移除 localStorage：本機會過、prod 全站 401。**

**業主 2026-07-21 裁決：採「自訂網域」**（web/api 掛同一父網域，cookie 設共用 domain）。

#### ✅ S3a done（code 先就緒，不動現況行為）

- **後端** `api/core/auth_cookie.py`：`set_access_cookie`／`clear_access_cookie`，
  網域由 **`AUTH_COOKIE_DOMAIN`** 控（未設＝host-only＝**現況行為不變**）、
  `AUTH_COOKIE_SECURE` 未設時「有共用網域即 Secure」。
  接線 `routers/auth.py`：`loginAdmin`／`loginTechnician`／`refreshToken` 寫 cookie、`logout` 清 cookie。
  與 response body 的 token **並存**（過渡期不改前端取用方式）。
- **前端** 四站 `api.ts` 新增 `apiFetch` wrapper（`credentials:"include"`），11 個呼叫點全數改走，
  helper 內保留原生 fetch。**四站 tsc 0 errors**。
- 驗證：unit **8 passed**（env 網域/Secure 推導、cookie 屬性 HttpOnly/SameSite/Path/Domain、清除）。

#### ⬜ S3b（移除 localStorage）— **gated on 自訂網域上線**

**OPS runbook（自訂網域）**：
1. 取得網域並於 Cloud Run 建 domain mapping：web→`app.<domain>`、api→`api.<domain>`（同父網域）。
2. api 設 `AUTH_COOKIE_DOMAIN=.<domain>`（含前導點）＋確認 `AUTH_COOKIE_SECURE` 未設或為 true。
3. `CORS_ORIGINS` 改為 `https://app.<domain>`（`api.sh` 目前動態解析 run.app URL，需一併調整）。
4. Casdoor application `redirectUris` 加 `https://app.<domain>/auth/callback`。
5. 驗證：登入後 devtools 確認 cookie 帶 `Domain=.<domain>`、對 api 請求有送出 → 才做 S3b。

S3b 內容：`decodeJwtPayload` 移除、token 不再寫 localStorage、session claims 全走 claims cookie。
- **S4 break-glass** 本地登入路徑 + 稽核告警（HD-6）。
- **S5** 過渡期滿移除 HS256 分支（不可逆點）+ 收尾（WBS 2.1.1／Traceability／CHANGELOG）。

---

> 🛑 原 §8 gate 已由業主「照建議」解除；**新增 gate＝tokenFormat 修復為 S2 硬前置**（prod 需 OPS 協同）。
