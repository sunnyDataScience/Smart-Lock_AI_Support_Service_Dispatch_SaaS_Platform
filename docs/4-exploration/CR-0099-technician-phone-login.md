# CR-0099 — 技師登入支援「手機號或 Email」

> **狀態**: ✅ 已實作（業主 2026-06-23 實測卡關 + 裁決方案 A，同日實作）
> **分支**: `feat/technician-phone-login`（疊於 `dev_new_arch`）
> **觸發面向**: API contract（`/technicians/login` 請求 schema）+ Domain/Auth（lookup 解析）

## 1. 背景 / 問題

業主測試到「指派師傅 → 用師傅登入」時卡住，得到 `VALIDATION_ERROR (422)`。

log 鐵證（08:18–08:19 連續嘗試）：

```
08:18:55  401 Unauthorized   ← 打 email，格式過了但帳密不對
08:19:33  422 Unprocessable  ← 改打手機號，格式直接被擋
```

## 2. 根因（前後端 contract 不一致）

- 前端技師登入框標籤寫 **「手機號碼或 Email」**、提示 `0912xxxxxx 或 tech@example.com`
  （`web/src/i18n/messages/zh-TW.json:2366-2367`），**叫使用者用手機登入**。
- 但後端 `POST /technicians/login` 的 `LoginBody.email` 型別是 `EmailStr`
  （`api/routers/auth.py`），**手機號不是合法 email → 在驗證帳密之前就被 422 擋下**。
- `auth_service.login` → `_find_user_by_email` 只 `WHERE email = %s`，**無手機查詢路徑**。

> UI 承諾的能力（手機登入）後端從未實作 → 使用者照 UI 指示打手機,必 422。

## 3. 決策（§8 業主裁決）

**方向**（業主選 A）：

| 方案 | 做法 | 裁決 |
|---|---|---|
| **A** | 後端支援「手機或 Email」皆可登入 | ✅ **採用**（符合技師用手機最直覺）|
| B | 前端改回只收 Email | 否（縮限能力，不符產品意圖）|

**子決策**（同日 AskUserQuestion 裁決）：

| # | 議題 | 裁決 |
|---|---|---|
| §8.1 | `users.phone` 無唯一約束，手機對到多帳號怎麼辦 | **多筆相符 → 擋下（409），要求改用 Email**（最安全，純後端、免 migration）|
| §8.2 | 登入請求欄位形狀 | **改名 `identifier`**（手機或 email 皆可），契約語意正確；前端改 1 行 + OpenAPI 同步 |

## 4. 實作

**後端**（`api/`）：

- `services/auth_service.py`：
  - `_TW_MOBILE_RE = ^09\d{8}$`（與 `TechnicianRegisterBody.phone` 一致）。
  - `_find_users_by_phone(phone, role_in)`：`WHERE phone = %s AND role IN(...)`，**回全部相符**以偵測歧義。
  - `login_with_identifier(identifier, password, *, allowed_roles)`：符合手機格式 → 查 phone（多筆 → `409 AMBIGUOUS_IDENTIFIER`）；否則走既有 email 查詢。密碼驗證 / 停用檢查 / token 簽發與 `login()` 完全一致。
- `routers/auth.py`：新增 `TechnicianLoginBody { identifier: str(min 1, max 255), password: str(min 8) }`；`login_technician` 改用之，呼叫 `login_with_identifier`。

**前端**（`web/`）：

- `lib/api.ts`：`loginTechnician` 送 `{ identifier, password }`（原 `{ email: identifier }`）。
- `app/tech-login/page.tsx`：密碼欄 `minLength` 4 → 8，與後端對齊（順手修的既有不一致）。

**契約**（tier-2）：

- `docs/architecture/api/openapi.yaml`：`/technicians/login` requestBody `email` → `identifier`（手機或 email），新增 `409 AMBIGUOUS_IDENTIFIER`。

**守備範圍**：僅 `/technicians/login`（role=technician）。`/auth/login`（admin/後台角色）與 `/vendors/login` **維持 email-only，未變**。

## 5. 測試

`api/tests/test_technician_login_identifier.py`（5 passed）：

- 手機號 `0911222333` + `changeme123` → 200（demo-tech 種子）
- Email `test@lock-ai.com` → 200（既有路徑不回歸）
- 密碼錯 → 401；查無手機 → 401
- 手機對應多帳號（monkeypatch `_find_users_by_phone` 回 2 筆）→ 409 `AMBIGUOUS_IDENTIFIER`

回歸：`test_login_roles.py` + `test_auth_guards.py` 共 10 passed（admin/後台/vendor 登入、技師擋 admin-web 皆未變）。

## 6. 影響 / 風險

- **不波及**：token 簽發、refresh、RBAC、admin/vendor 登入、register。
- **資料風險**：`users.phone` 仍無唯一約束。本 CR 以「多筆相符擋下」緩解，**未根治**。
  若日後要支援「手機為主帳號」，可加 `(tenant_id, phone) WHERE role='technician'` 唯一索引（另開 CR + migration）。
- **無 DB migration**：純應用層變更。
