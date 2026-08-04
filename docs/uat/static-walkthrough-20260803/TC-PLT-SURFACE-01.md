# TC-PLT-SURFACE-01 — 三面 API 交叉呼叫一律 403

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑跨面守衛相關 4 檔 99 項全過（見步驟 6） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/auth.py:30-48`、`api/core/deps.py:34-43/114-150/198-243`、`api/core/db.py:259-272`、`api/main.py:145-213/688-793`、`scripts/deploy/api.sh:96-106`、`SQL/platform/Schema_platform.sql`、`api/routers/platform_*.py` |
| 優先級 / 路徑類型 | P0 / failure |
| 事實結論 | TC 三個判定基準在程式碼中皆有落點：**跨面 403** 由 `get_current_user` 單點守衛（`api/core/deps.py:142-150`，錯誤碼 `CROSS_PORTAL_FORBIDDEN`，403）；**缺 portal claim 的舊 token** 由 `portal_for_role` 即時推導（`api/core/auth.py:40-48`，空/未知 role → `None` → deny）；**平台獨立 guard/資料庫** 為 `require_platform_admin`（`api/core/deps.py:225-243`，僅放行 `role=platform_admin`）＋ `require_platform_conn`（`api/core/db.py:259-272`，`PLATFORM_POSTGRES_URI`）；**拒絕前不讀業務資料** 由 FastAPI 依賴注入順序保證——守衛是 `Depends`，在 handler body 執行前完成（`api/routers/platform_tenants.py:43-47` 等）。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：brand/tech/platform token 與三面 API
- 步驟：交叉呼叫敏感端點、帶缺 portal claim 舊 token、平台 token 查品牌資料
- 預期結果（判定基準）：不允許的跨面一律 403；platform 走獨立 guard/資料庫；拒絕前不讀取目標業務資料
- 路徑類型：failure｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-PLT-09｜屬於旅程腳本：SC-12、SC-14、SC-17

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| tech token 打 brand 端點 → 403 | `api/core/deps.py:142-150` | 有（`CROSS_PORTAL_FORBIDDEN`） |
| brand token 打 platform 端點 → 403 | `api/core/deps.py:237-242` | 有（`FORBIDDEN`，`Platform admin role required`） |
| platform token 打 brand 端點 → 403 | `api/core/deps.py:142-150`（雲端 `ALLOWED_TOKEN_PORTALS=brand`）＋各 brand 端點的 `role_required` | 有（兩層） |
| 缺 portal claim 的舊 token | `api/core/deps.py:144`、`api/core/auth.py:40-48` | 有（由 role 即時推導；空/未知 role → None → deny） |
| platform 獨立 guard | `api/core/deps.py:225-243` | 有 |
| platform 獨立資料庫 | `api/core/db.py:259-272`、`SQL/platform/Schema_platform.sql` | 有（未配置 `PLATFORM_POSTGRES_URI` 時 fallback 主連線） |
| 拒絕前不讀取目標業務資料 | `api/routers/platform_tenants.py:43-47`（`Depends` 於 handler body 前解析） | 有 |
| 部署面路由過濾 | `api/main.py:724-731`（tech）、`:751-757`（platform）、`:784-791`（dispatch） | 有（自述為部署塑形，非安全邊界） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師（tech token） | 打 brand-api 客戶 PII 端點 | `RequestRejected(403)` | 跨面守衛 | `api/core/deps.py:142-150` | portal=`tech` ∉ `{brand}` → 403 `CROSS_PORTAL_FORBIDDEN` |
| 品牌後台（brand token） | 打 `/platform/tenants` | `RequestRejected(403)` | 平台獨立 guard | `api/core/deps.py:237-242` | role ≠ `platform_admin` → 403 `FORBIDDEN` |
| 平台（platform token） | 打品牌 tenant-scoped 端點 | `RequestRejected(403)` | 跨面＋角色 | `api/core/deps.py:143-150`、各 router 的 `role_required` | 雲端 brand 服務 `ALLOWED_TOKEN_PORTALS=brand` → 403；`platform_admin` 亦不在 brand 角色集 |
| 持舊 token 者 | 帶缺 `portal` claim 的 access token | `RequestRejected(403)` 或放行 | 由 role 推導 | `api/core/deps.py:144`、`api/core/auth.py:40-48` | `payload.get("portal") or portal_for_role(role)`；role 空/未知 → `None` → 必 deny |
| 任一 | 打 refresh token 當 access 用 | `RequestRejected(401)` | token 型別 | `api/core/deps.py:128-133` | `type != "access"` → 401 |
| 系統 | 讀平台資料 | — | 獨立庫 | `api/core/db.py:262-272` | `platform_db_enabled()` 為真走平台連線，否則 fallback 主連線 |

---

## 逐層走查

### 步驟 1 — portal claim 的產生（簽發側）

`api/core/auth.py:30-48`

```python
# CR-0182：token 面向（portal claim）——跨面守衛用（UAT-0723-F2：技師 token 讀 brand
# 客戶 PII/金流）。刻意不用標準 JWT `aud` 欄：jose.jwt.decode 未帶 audience 參數時會
# 自動驗 aud → JWTClaimsError 破壞既有 decode（拋棄式測試證實）；亦避與部署塑形
# `surface`（API_SURFACE，明示非安全邊界）撞名。
# 推導方向：枚舉 non-brand（technician→tech、platform_*→platform），其餘→brand（含
# vendor，業主 0726 D2a）；空/缺 role→None（呼叫端 deny，異常 token 不落最敏感的 brand）。
_TECH_PORTAL_ROLES = frozenset({"technician"})
_PLATFORM_PORTAL_ROLES = frozenset({"platform_admin", "platform_keeper"})


def portal_for_role(role: str | None) -> str | None:
    """role → token 面向（brand/tech/platform）；空/未知回 None（呼叫端 deny）。"""
    if not role:
        return None
    if role in _TECH_PORTAL_ROLES:
        return "tech"
    if role in _PLATFORM_PORTAL_ROLES:
        return "platform"
    return "brand"
```

寫入點 `api/core/auth.py:97-101`：

```python
    # CR-0182：寫入面向（belt）；判定端（get_current_user）對缺 portal 的 token 亦由
    # role 即時推導（braces），故部署後 1h 內舊 access token 無 portal 亦被正確歸類。
    _portal = portal_for_role(role)
    if _portal is not None:
        payload["portal"] = _portal
```

### 步驟 2 — 判定側：單點守衛與缺 claim 的處理（TC 步驟②）

`api/core/deps.py:137-150`

```python
    # CR-0182（UAT-0723-F2）：跨面守衛。缺 portal 的 token（部署後 1h 內舊 access token、
    # 或 SSO token——oidc.verify_oidc_token 不經 create_token）由 role 即時推導（braces）。
    # portal 為 None（空/未知 role）或不在本服務允許集 → 403，不落最敏感的 brand。
    # 掛在 get_current_user 單點即涵蓋所有受保護 HTTP 端點（含 F2 目標 bare require_tenant）。
    # 範圍＝HTTP-only；WS 授權由 verify_ws_token/authorize_channel 另行把關。
    _allowed = _allowed_portals()
    if _allowed is not None:
        portal = payload.get("portal") or portal_for_role(token_role)
        if portal not in _allowed:
            raise ApiError(
                error_code="CROSS_PORTAL_FORBIDDEN",
                message="Token is not valid for this service surface",
                status_code=403,
            )
```

允許集來源 `api/core/deps.py:34-43`：

```python
# CR-0182（UAT-0723-F2）：跨面 token 守衛。三面共用 JWT secret，技師 token 過去可直接
# 讀 brand-api 客戶 PII/金流。本服務只接受 ALLOWED_TOKEN_PORTALS 列出的面向 token。
#   - env 未設/空 → None → 不強制（本機單體、pytest 之 API_SURFACE=all 沿用既有行為）
#   - 雲端各服務顯式設定：brand-api=brand、tech-api=tech、platform-api=platform（api.sh）
#   刻意獨立於 API_SURFACE（=部署塑形，all 同時是單體/測試模式，復用會自我失效）。
def _allowed_portals() -> frozenset[str] | None:
    raw = os.environ.get("ALLOWED_TOKEN_PORTALS", "").strip()
    if not raw:
        return None
    return frozenset(p.strip() for p in raw.split(",") if p.strip())
```

部署時的預設值 `scripts/deploy/api.sh:100-106`：

```bash
case "${API_SURFACE}" in
    tech)      _DEFAULT_PORTALS="tech" ;;
    platform)  _DEFAULT_PORTALS="platform" ;;
    *)         _DEFAULT_PORTALS="brand" ;;   # all / dispatch（雲端品牌服務）→ 僅收 brand
esac
ALLOWED_TOKEN_PORTALS="${ALLOWED_TOKEN_PORTALS:-${_DEFAULT_PORTALS}}"
ENV_VARS="${ENV_VARS},ALLOWED_TOKEN_PORTALS=${ALLOWED_TOKEN_PORTALS}"
```

`_allowed_portals()` 回 `None`（env 未設）時不強制；本機/pytest 即此情形。

### 步驟 3 — 平台獨立 guard（TC 步驟③）

`api/core/deps.py:225-243`

```python
async def require_platform_admin(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """平台方 console 專用守衛（CR-0114）。

    非 tenant-scoped：不收 X-Tenant-ID（platform console 跨品牌視角）。
    只放行 role=platform_admin —— 該角色不在任何品牌 gate 集合
    （FULL_ACCESS/OPS/DISPATCH…），品牌 token 打平台端點、平台 token 打
    品牌端點皆 deny-by-default。
    """
    user = await get_current_user(request, authorization)
    if user.role != "platform_admin":
        raise ApiError(
            error_code="FORBIDDEN",
            message="Platform admin role required",
            status_code=403,
        )
    return user
```

品牌側對稱守衛為 `require_tenant`（`api/core/deps.py:198-212`），另比對 `X-Tenant-ID` 與 claim，不符回 403 `TENANT_MISMATCH`。

### 步驟 4 — 平台獨立資料庫

`api/core/db.py:259-272`

```python
async def require_platform_conn() -> AsyncConnection:
    """平台域連線（CR-0114）：配置平台庫時回平台庫，否則回主連線（fallback）。

    與 require_tech_conn 同款安全閥：PLATFORM_POSTGRES_URI 未設（pytest/CI/
    單庫部署）時行為與主連線完全相同。
    """
    if platform_db_enabled():
        if not await _ensure_platform_conn():
            raise RuntimeError("Platform DB unavailable")
        return _platform_conn  # type: ignore[return-value]
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    return _current_conn()  # type: ignore[return-value]
```

平台庫 schema 為獨立檔 `SQL/platform/Schema_platform.sql`，其 `:4-8` 自述「平台方(Lock AI)console 自有資料,與品牌庫/技師庫物理分離」並列出 `users` / `revoked_jti` / `brand_applications`；同檔另建 `monitor_target`（`:112`）與 `tenant`（`:139`）。平台服務全部走此連線：`api/services/platform_tenant_service.py:33-37`、`api/services/brand_application_service.py:42-46` 皆以 `require_platform_conn()` 取連線，失敗回 503 `DB_UNAVAILABLE`。

### 步驟 5 — 拒絕發生在讀取業務資料之前

平台 router 的 handler 全部把守衛掛在 `Depends`，FastAPI 於進入 handler body 前解析依賴：

`api/routers/platform_tenants.py:43-47`

```python
async def list_tenants(
    status: str | None = None,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_tenants(status)
```

`require_platform_admin` 內部順序為：`get_current_user`（解 token → portal 檢查 → jti 撤銷 → 帳號狀態）→ role 比對 → 才 return。整條路徑上唯一的 DB 讀取是 `is_jti_revoked` 與 `load_user_security_state`（`api/core/deps.py:155`、`:165`），兩者查的是 token 主體自身的撤銷清單與帳號狀態，非目標業務資料；業務查詢（`svc.list_tenants`）在守衛通過後才發生。

### 步驟 6 — 執行既有測試

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest -p winloop_plugin \
  tests/test_cr_0182_portal_guard.py tests/test_platform_surface.py \
  tests/test_cr_0183_intra_portal_guards.py tests/test_api_surface.py -q
99 passed in 3.15s
```

對到 TC 步驟的測試：

- role → portal 推導與「空 role 必 deny」：`api/tests/test_cr_0182_portal_guard.py:19-38`

```python
def test_technician_maps_to_tech():
    assert portal_for_role("technician") == "tech"
...
def test_empty_or_none_role_denied():
    # 空/缺 role = 異常 token → None（呼叫端 deny，不落最敏感的 brand）
    assert portal_for_role("") is None
    assert portal_for_role(None) is None
```

- 該測試檔頭 `:1-5` 明載其對應的 UAT 發現：「F2＝技師 token（role=technician）打 brand-api 讀客戶 PII/退款金流」。

---

## 既有測試證據

`api/tests/test_cr_0182_portal_guard.py`、`api/tests/test_platform_surface.py`、`api/tests/test_cr_0183_intra_portal_guards.py`、`api/tests/test_api_surface.py`：合計 99 項，全過（步驟 6）。

---

## 觀測到的其他事實

1. **`API_SURFACE` 路由過濾自述為部署塑形而非安全邊界**：`api/main.py:734-735`

```python
# 平台端點收在 legacy /api/v1/platform 與新面 /api/v2/platform 前綴下。
# 同 tech 面:部署塑形非安全邊界,權限由 require_platform_admin 把關。
```

三種過濾模式分別在 `api/main.py:724-731`（tech，保留式）、`:751-757`（platform，保留式）、`:784-791`（dispatch，剔除式）。

2. **守衛範圍限 HTTP**：`api/core/deps.py:141` 註解「範圍＝HTTP-only；WS 授權由 verify_ws_token/authorize_channel 另行把關」。

3. **平台庫未配置時 fallback 主連線**：`api/core/db.py:262-264` docstring 自述「`PLATFORM_POSTGRES_URI` 未設（pytest/CI/單庫部署）時行為與主連線完全相同」。TC 判定基準寫「platform 走獨立 guard/**資料庫**」／程式碼在未設該環境變數的部署形態下與品牌庫同連線。此處僅並陳，不裁定。

4. **三面共用同一 JWT secret 是本守衛存在的前提**：`api/core/deps.py:34-35` 註解「三面共用 JWT secret，技師 token 過去可直接讀 brand-api 客戶 PII/金流」。另 `api/main.py:160-164` 對 `API_SURFACE=platform` 有啟動期檢查，要求 `API_JWT_SECRET_KEY` 為 ≥16 字元的獨立密鑰，否則拒絕啟動。
</content>
