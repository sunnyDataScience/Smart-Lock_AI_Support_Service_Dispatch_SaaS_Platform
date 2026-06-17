---
id: CR-0025
title: "Change Impact Analysis — 使用者自助忘記密碼/重設密碼"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-17
target-release: TBD
product-version: null
supersedes: null
superseded-by: null
---

# CR-0025: 使用者自助忘記密碼 / 重設密碼

> **Tier**: 4-exploration → Change Impact Analysis（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 API contract / Domain model / DB schema / External integration / Test plan 多面向）
> **Generated**: 手動（`sunnydata-change-impact-analysis` skill 未註冊，依 `VibeCoding_Workflow_Templates/4-exploration/CIA-0000` 模板產出）

---

## 1. Change Statement

**As-is**：系統**無自助重設**。`admin-reset-password`（`AdminResetPasswordModal`，需另一已登入 admin 操作）是唯一重設路徑。技師登入頁 `/tech-login` 只有不可點的「忘記密碼？請聯絡管理員重設」純文字提示；管理員登入頁 `/login` **完全沒有**忘記密碼入口。

**To-be**：兩個登入頁都提供**可點的「忘記密碼」自助流程** —— 使用者輸入帳號（email）→ 系統發出一次性 reset token 經選定送達管道 → 使用者用 token 設定新密碼。

**Driver**：業主裁決（2026-06-17）**推翻 2026-06-10 會議 Action #7「免 email、admin 代重設」之決策**；驅動點有二：(1) 登入頁缺自助忘記密碼不符使用者預期、兩登入頁不一致；(2) **雞生蛋風險** —— 唯一 admin 忘記密碼時 `admin-reset-password` 無人可操作。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `UX-FLOW-001` (S5 admin journey) | Modified | admin 登入加自助重設入口 |
| 新 auth 子流程（ID 待配，建議 `SF-AUTH-RESET`） | New | 自助重設流程：request → 送達 → confirm；可重用於技師/管理員兩端 |
| `/tech-login` 技師登入流程 | Modified | 不可點提示 → 可點連結 → 重設頁 |

> 註：User Flow 正典 `docs/ux/user-flow-smart-lock-saas.md`（`status: draft`），目前無專門的 auth/login flow 子檔，需新增。

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| 新 `FR-NNNN`（ID 待配） | New | 自助密碼重設規則：token 一次性、TTL、enumeration 防護、rate limit |
| `NFR`（安全） | New/Modified | reset token 雜湊儲存、常數時間比對、防帳號枚舉、防濫用節流 |

> 註：現 codebase 無專門 auth FR 殼（login/change-password 直接實作於 `auth_service.py`）。需補一份 FR 正典。

## 4. Affected API

現有（不動，保留為後備）：`loginAdmin` / `loginTechnician` / `refreshToken` / `logout` / `changePassword` / `adminResetPassword`（`api/routers/auth.py`）。

| API | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `requestPasswordReset` | `POST /auth/request-password-reset` | New | No | body `{email}`；**一律回 200**（不洩漏帳號是否存在）；觸發 token 簽發 + 送達 |
| `confirmPasswordReset` | `POST /auth/confirm-password-reset` | New | No | body `{token, new_password}`；驗 token（未過期/未用）→ 改密碼 → 失效 token + 撤銷既有 refresh token |

需同步更新 `openapi-smart-lock-saas.yaml`（新增兩 operation + error code：`RESET_TOKEN_INVALID` / `RESET_TOKEN_EXPIRED`）。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `password_reset_tokens`（新表） | New | `id uuid PK / user_id uuid FK / token_hash text（存雜湊非明文）/ channel text / expires_at timestamptz / used_at timestamptz NULL / requested_ip inet NULL / created_at`；index on `token_hash`、`user_id` |
| `users` | Unchanged | 已有 `email` + `password_hash`；**但 email 目前未經驗證**（見 §8 Q5） |

State machine：reset token 狀態 `pending → used`（或 `expired`，由 `expires_at` 判定，免額外欄位）。

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-NNNN` | New | request happy path：存在帳號 → 簽 token + 送達 → 回 200 |
| `TC-NNNN` | New | request 不存在帳號 → 仍回 200（enumeration 防護）、不送達 |
| `TC-NNNN` | New | confirm happy path：有效 token → 改密碼成功 + token 標 used |
| `TC-NNNN` | New | confirm 過期 token → `RESET_TOKEN_EXPIRED` |
| `TC-NNNN` | New | confirm 已用 token → `RESET_TOKEN_INVALID` |
| `TC-NNNN` | New | confirm 後既有 refresh token 全失效（不能用舊 session） |
| `TC-NNNN` | New | rate limit：同 email/IP 短時間多次 request → 節流 |
| `TC-NNNN` | New（E2E） | 兩登入頁可點連結 → 重設頁 → 改密碼 → 新密碼可登入（Playwright） |

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| 送達管道（External integration） | **新增** | **§8 Q1 待裁決**：email（**無 infra**，需接 SendGrid/SES/SMTP + secret）/ LINE（**有 infra** `line_push_service`，但對象是終端 LINE 客戶；後台 staff 用 email 登入、未綁 LINE）/ SMS（無 infra） |
| 新 ADR？ | **Yes** | `ADR-NNNN`：記錄送達管道選擇 + token 設計 + 推翻 Action #7 之留痕 |
| Module 邊界 | 擴充 | `auth_service.py` 加 reset 邏輯；新 token service；不動 agent 架構鎖 |
| Secret 管理 | 視管道 | email/SMS provider 走 GCP Secret Manager + deploy 腳本接線 |
| Rate limiting | 待確認 | 需確認現有節流機制可否重用（敏感端點防濫用） |

## 8. Human Decisions Required

✅ **業主已裁決（2026-06-17）—— gate 解除，依 §9 實作。**

| # | Question | Owner | Status | Decision（2026-06-17）|
|---|---|---|---|---|
| 1 | **送達管道** | 業主 | ✅ resolved | **(a) Email** —— staff/技師都有 email、都用 email 登入，單管道涵蓋兩端。接寄信 provider（抽象化 `EmailProvider`，預設 SMTP，可配 SendGrid/SES）+ secret |
| 2 | **範圍** | 業主 | ✅ resolved | **(a) 管理員 + 技師兩頁都做** |
| 3 | **Admin 雞生蛋 break-glass** | 業主 | ✅ resolved | **(a)** —— Q1=email 即解，admin 可自助重設（仍保留 seed/DB 為終極 break-glass） |
| 4 | **Token TTL + 一次性** | 架構 | ✅ resolved | **30 分鐘、單次用**；confirm 後撤銷該 user 既有 refresh token |
| 5 | **email 信任度（未驗證）** | 業主 | ✅ resolved | **(b) 接受現狀**，首次重設視同驗證；完整 email 驗證另開 CR |
| 6 | **帳號枚舉防護** | 安全 | ✅ resolved | **(a) 是** —— request 一律回 200「若帳號存在已寄出」 |
| 7 | **保留 `admin-reset-password` 後備** | 業主 | ✅ resolved | **(a) 保留** |

## 9. Suggested Implementation Order

§8 裁決後，依相依順序：

1. **Decisions** → 寫 `ADR-NNNN`（送達管道 + token 設計 + 推翻 Action #7 留痕）
2. **Schema** → migration 新增 `password_reset_tokens` 表 + index
3. **送達管道整合** → 依 Q1 接 provider（email/LINE/SMS）+ secret + deploy 腳本接線
4. **Domain/Service** → `auth_service` 加 `request_reset` / `confirm_reset` + token service（簽發雜湊、驗證、失效、撤 refresh）
5. **API** → openapi 加兩 operation + error code，router handler
6. **Tests** → 補 §6 TC（含 enumeration / 過期 / 已用 / rate limit；用 TDD）
7. **UI** → 兩登入頁「忘記密碼」改可點連結 + 新重設頁（request 表單 + confirm 表單）；技師頁 span 改回可點連結
8. **Traceability** → 更新 traceability matrix（新 SF/FR/API/TC）
9. **Docs sync** → 更新 `user-flow` + `system-completion-status` + CHANGELOG + `auth.py` 旁的 Action #7 註解（標 superseded by CR-0025）

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| email deliverability（進垃圾桶/未送達）| Medium | High | 選信譽 provider（SES/SendGrid）；先小範圍測 |
| reset token 外洩/被猜 | Low | High | 高熵 token、只存雜湊、短 TTL、單次用、confirm 後撤 refresh |
| 帳號枚舉 | Medium | Medium | request 一律 200（Q6=a）|
| 濫用（洗 request 灌信/簡訊費）| Medium | Medium | per-email + per-IP rate limit |
| users email 未驗證 → 寄到錯誤信箱 | Medium | High | Q5 裁決；至少首次重設後標記 email 已驗證 |

**Rollback plan**：新功能掛 feature flag；出事關 flag 即回到「僅 admin 代重設」。schema 為新增表（不動既有），可逆。

## 11. Out of Scope

- MFA / 2FA、passwordless、SSO（另開 CR）
- 帳號鎖定 / 登入失敗次數政策（另開 CR）
- email 驗證流程本身的完整重構（若 Q5=a，最小化處理，完整版另開 CR）

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-06-17 | ✅（§8 全裁決）|
| Architect | | | |
| Engineering Lead | | | |
| QA Lead | | | |

## 13. 實作進度

- ✅ S1 Decisions → `ADR-0114`（merge 待）
- ✅ S2 Schema → migration `035-password-reset-tokens.sql`
- ⏳ S3 送達管道整合 → `email_provider.py`（SMTP 抽象）已寫；**prod 待配 SMTP secret + api.sh 接線**
- ✅ S4 Domain/Service → `password_reset_service.py`（request/confirm）
- ✅ S5 API → `request/confirm-password-reset` 端點（openapi 正式 yaml 待補登）
- ✅ S6 Tests → `test_password_reset.py` 8 案（**需 dev stack：DB + migration 035 才能跑**，尚未執行）
- ✅ S7 UI → `/forgot-password` + `/reset-password` + 兩登入頁連結 + i18n（tsc 0 error）
- ⏳ S8 Traceability matrix → 待補
- ⏳ S9 Docs sync → CHANGELOG ✅ / completion-status ✅ / auth.py 註解 ✅ / doc-freshness 待跑

**已知 follow-up（§10）**：confirm 後未全域撤該 user refresh token（需 `users.password_changed_at` epoch 檢查，另開 CR）。
