# TC-TEC-REVOKE-01 — 撤銷認證／停權／復權對候選集與通知的影響

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑技師生命週期與平台技師管理相關 6 檔 45 項全過（見步驟 7） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/services/technician_lifecycle_service.py`、`api/services/technician_brand_auth_service.py`、`api/services/technician_certification_service.py`、`api/routers/platform_technicians.py:140-193/414-488`、`api/routers/technician_certifications_v2.py`、`api/services/dispatch_service.py:185-192/333-388/414-478/537-545/603-608`、`SQL/migrations/105-tech-lifecycle-brand-auth-events.sql` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | **停權即時排除候選集**成立：`suspended` 在 `_DISPATCH_INELIGIBLE_STATUSES`（`dispatch_service.py:187`），且候選查詢每次 live 讀權威庫無快取（`technician_brand_auth_service.py:8-9` 自述 pull-on-read）。**撤銷品牌授權**成立於自動派工（`dispatch_service.py:606-608`），人工候選僅標示不排除（`:537-545`）。**撤銷認證（`technician_certification`）不影響候選集**——`dispatch_service.py` 全檔對 `technician_certification` 零引用，該表與 `technician_brand_authorization` 職責分離（`technician_certification_service.py:4-5` 自述）。**復權前不得自行恢復**成立：`reactivate` 為 CAS `suspended→active` 且端點掛 `require_platform_admin`（`platform_technicians.py:164-171`）。**重送不重複通知**：撤銷/停權路徑在 `api/` 內**無任何通知發送程式碼**（`technician_lifecycle_service.py`、`technician_brand_auth_service.py`、`technician_certification_service.py` 三檔 `notification` 零命中），故「重複通知」無對應落點；`technician.certification_revoked` 事件名全樹零命中。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：已排班且已獲品牌授權技師、兩品牌候選池
- 步驟：撤銷認證、停權、復權、重送事件並檢查候選集與通知
- 預期結果（判定基準）：撤銷/停權後各品牌候選集立即排除；重送不重複通知；復權前不得自行恢復可派狀態
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-TEC-08｜屬於旅程腳本：SC-14

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 撤銷認證端點 | `api/routers/platform_technicians.py:414-426`（平台）／`api/services/technician_certification_service.py:166-181` | 有 |
| 撤銷品牌授權端點 | `api/routers/platform_technicians.py:472-488`、`api/services/technician_brand_auth_service.py:104-126` | 有 |
| 停權端點 | `api/routers/platform_technicians.py:140-156`、`api/services/technician_lifecycle_service.py:331-347` | 有 |
| 復權端點 | `api/routers/platform_technicians.py:158-174`、`api/services/technician_lifecycle_service.py:350-360` | 有 |
| 停權後候選集立即排除 | `api/services/dispatch_service.py:187`、`:429-431` | 有 |
| 撤銷品牌授權後候選集排除（自動派工） | `api/services/dispatch_service.py:606-608` | 有 |
| 撤銷品牌授權後候選集排除（人工候選） | `api/services/dispatch_service.py:537-545` | 部分：只標示 `brand_authorized=false`，不排除 |
| 撤銷認證後候選集排除 | — | **找不到**：`technician_certification` 不進派工判定 |
| 重送事件不重複通知 | — | **找不到**：撤銷/停權路徑無通知發送 |
| 復權前不得自行恢復可派狀態 | `api/services/technician_lifecycle_service.py:79-86`、`:350-360`、`api/routers/platform_technicians.py:164-171` | 有 |
| `technician.certification_revoked` 事件 | — | **找不到**：全樹零命中 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| platform_admin | 撤銷品牌授權 | `BrandAuthorizationRevoked` | 軟撤留歷史 | `api/services/technician_brand_auth_service.py:114-126` | `UPDATE ... SET authorized = FALSE RETURNING`；查無列 404；鏡射投影；寫 `brand_auth_revoked` lifecycle audit |
| platform_admin | 重送同一撤銷 | （不應重複） | 冪等 | `api/services/technician_brand_auth_service.py:115-123` | 第二次 UPDATE 仍 RETURNING 命中（`authorized` 已 FALSE）→ 200，並**再寫一筆** audit（`:125`） |
| platform_admin | 停權 | `TechnicianSuspended` | 有進行中工單需先改派 | `api/services/technician_lifecycle_service.py:338-347` | `force=False` 時查孤兒工單，有則 409 `TECHNICIAN_HAS_ACTIVE_WORK_ORDERS` |
| 系統 | 停權連動登入資格 | `TechnicianLoginDisabled` | status 為 SoT | `api/services/technician_lifecycle_service.py:125-133` | `UPDATE users SET is_active = (target_status == 'active')` |
| 系統 | 停權寫稽核 | `LifecycleEventAppended` | 稽核為硬性要求 | `api/services/technician_lifecycle_service.py:192-216` | 寫 `saas.technician_lifecycle_event`；寫失敗 → 回滾整個操作並回 500 `AUDIT_WRITE_FAILED` |
| 派工系統 | 產生候選集 | `CandidatesListed` | 停權硬排除 | `api/services/dispatch_service.py:429-431` | `pending_approval/suspended/terminated/rejected` 一律 `continue` |
| 停權技師 | 自行恢復可派狀態 | （不應發生） | CAS + 平台守衛 | `api/services/technician_lifecycle_service.py:79-86`、`api/routers/platform_technicians.py:164-171` | `_check_transition` 只允許 `suspended→active`；端點 `Depends(require_platform_admin)` |
| 系統 | 撤銷/停權後通知 | `TechnicianNotified` | 重送不重複 | — | **找不到**：三個 service 檔皆無通知程式碼 |

---

## 逐層走查

### 步驟 1 — 三種「撤銷」在程式碼中是三張不同的表

- `technician_certification`：具名認證（cert_name / brand / obtained_at / expires_at）。`api/services/technician_certification_service.py:1-5`

```python
"""Technician Certification Service — CR-0104 技能認證矩陣（真資料模組）。

承載師傅詳情頁「技能認證矩陣」的結構化認證資料（取代前端寫死的 5 列 mock）。
與 technician_brand_authorization（063，dispatch 品牌過濾用，UNIQUE(tech,brand)）職責分離：
一技師可有多筆具名認證，每筆含 cert_name / brand / obtained_at / expires_at。
```

- `technician_brand_authorization`：派工用的品牌授權（`api/services/technician_brand_auth_service.py:1-9`）。
- `technicians.status`：生命週期（`api/services/technician_lifecycle_service.py:39-46`）。

`api/routers/technician_certifications_v2.py:1-12` 記錄了寫端點的收斂：

```
**寫端點已於 CR-0114 收斂輪移除**（認證屬師傅身分域資質，歸平台方職權）：
  - POST createTechnicianCertification / PATCH updateTechnicianCertification /
    DELETE deleteTechnicianCertification → 廢止。認證登錄途徑=3001 /tech-register
    自助註冊時填報；平台方認證管理功能為後續輪（platform console）。
```

現行認證刪除端點在平台面：`api/routers/platform_technicians.py:414-426`。

### 步驟 2 — 撤銷認證是否影響候選集

```
git grep -n "technician_certification" -- api/services/dispatch_service.py
（無輸出，exit=1）
```

`dispatch_service.py` 讀的技師欄位為 `_TECH_SELECT`（生命週期 status 在索引 9、online_state 在索引 11，見 `:427-428`），品牌判定讀 `technician_brand_authorization`（`:365-370`）。認證表不進任何派工判定。

`api/services/technician_certification_service.py:166-181` 的刪除實作：

```python
async def delete_certification(
    *, tenant_id: str, technician_id: str, cert_id: str
) -> None:
    """刪除一筆認證。"""
    ...
    cur = await conn.execute(
        "DELETE FROM technician_certification "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND technician_id = %s::uuid "
        "RETURNING id",
        (cert_id, tenant_id, technician_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "Certification not found", 404)
    await mirror_rows("technician_certification", [cert_id])  # 權威已刪 → 投影同步刪
```

為硬刪（DELETE），無 audit 寫入，重送同一 cert_id 第二次回 404。

TC 步驟寫「撤銷認證…並檢查候選集」／程式碼中認證刪除與候選集無耦合；影響候選集的是品牌授權（`technician_brand_authorization`）與生命週期 status。此處僅並陳，不裁定。

### 步驟 3 — 撤銷品牌授權的即時性與重送行為

`api/services/technician_brand_auth_service.py:104-126`

```python
async def revoke_brand_authorization(
    *, tenant_id: str, technician_id: str, brand: str,
    actor_user_id: str | None = None, reason: str = "platform revoke",
) -> dict:
    """撤銷技師某品牌授權（軟撤 authorized=FALSE，保留歷史；查無列 404；重複撤 200 no-op）。"""
    ...
    cur = await conn.execute(
        "UPDATE technician_brand_authorization SET authorized = FALSE "
        "WHERE technician_id = %s::uuid AND brand = %s "
        f"RETURNING {_SELECT}",
        (technician_id, brand),
    )
    row = await cur.fetchone()
    if row is None:
        raise ApiError("NOT_FOUND", f"技師無品牌「{brand}」授權紀錄", 404)
    await mirror_rows("technician_brand_authorization", [str(row[0])])
    await _audit_lifecycle(tenant_id, technician_id, "brand_auth_revoked", actor_user_id, brand, reason)
```

即時性設計依據，同檔 `:7-10`：

```python
身分域：師傅為平台權威（CR-0112/CR-0114），寫入走 require_tech_conn 權威庫 +
mirror_rows 鏡射品牌庫投影（維持 split-tech-db.sh --verify 對帳）。撤證即時性走
pull-on-read（候選查詢每次 live 重查權威庫，無快取；與 F15 停權一致，不需 WS 廣播）。
```

重送同一撤銷（docstring 稱「重複撤 200 no-op」）：資料面為 no-op，但 `_audit_lifecycle`（`:125`）位於 `row is None` 分支之後、無條件執行，故第二次撤銷仍會 append 一筆 `brand_auth_revoked` 稽核列（`:62-72`）。

### 步驟 4 — 停權 / 復權的狀態機與守衛

狀態機 `api/services/technician_lifecycle_service.py:39-46`：

```python
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending_approval": {"active", "rejected"},
    "active": {"suspended", "terminated"},
    "suspended": {"active", "terminated"},
    "rejected": {"terminated"},
    "terminated": set(),  # 終態
    "inactive": {"active", "terminated"},  # 既有狀態
}
```

檢查點 `:79-86`：

```python
def _check_transition(current: str, target: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot transition from '{current}' to '{target}'",
            409,
        )
```

DB 層再以 CAS 保證併發安全 `:110-118`：

```python
    upd = await conn.execute(
        "UPDATE technicians SET status = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = %s "
        "RETURNING id, status, updated_at",
        (target_status, tech_id, current),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
```

端點守衛 `api/routers/platform_technicians.py:158-171`（復權）：

```python
@router.post(
    "/platform/technicians/{technicianId}:reactivate",
    ...
async def reactivate(
    ...
    user: CurrentUser = Depends(require_platform_admin),
```

技師本人的 token role 為 `technician`（`api/core/auth.py:36`），不滿足 `require_platform_admin`（`api/core/deps.py:237-242`），亦不滿足雲端平台面的 `ALLOWED_TOKEN_PORTALS=platform`（`api/core/deps.py:142-150`、`scripts/deploy/api.sh:100-106`）。

停權另有孤兒工單軟阻擋 `api/services/technician_lifecycle_service.py:336-341`：

```python
    # CR-0164 E：孤兒工單軟阻擋——名下有進行中工單須先改派；主管帶 force 可越過
    # （緊急停權安全閥，孤兒仍在但已停權，須事後補改派）。
    if not force:
        orphans = await _active_work_orders(tech_id)
        if orphans:
            raise _orphan_conflict(orphans, "停權")
```

### 步驟 5 — 稽核與投影的失敗處置

`api/services/technician_lifecycle_service.py:174-216` 在鏡射與稽核兩處各有一段補償回滾：

```python
    try:
        if user_row:
            await mirror_rows("users", [str(user_row[0])])
        await mirror_rows("technicians", [tech_id])
    except Exception as exc:  # noqa: BLE001
        await _revert_authority()
        await _mirror_best_effort()
        raise ApiError(
            "MIRROR_FAILED",
            "技師身分投影鏡射失敗，狀態變更已回滾——請稍後重試或檢查投影同步",
            500,
        ) from exc

    # audit row（UAT-0718 R1：成功路徑保證稽核落地——寫不進就回滾整個操作，
    # 不再 best-effort 吞掉導致稽核斷鏈）。
    try:
        await conn.execute(
            "INSERT INTO saas.technician_lifecycle_event "
            ...
    except Exception as exc:  # noqa: BLE001
        ...
        raise ApiError(
            "AUDIT_WRITE_FAILED",
            "生命週期稽核寫入失敗，狀態變更已回滾（稽核為硬性要求，不可缺漏）",
            500,
        ) from exc
```

「重送事件」在此路徑上的行為：第二次停權時 `_fetch_status` 讀到 `suspended`，`_check_transition('suspended','suspended')` 因 `suspended` 的允許集為 `{active, terminated}` 而拋 409 `STATE_CONFLICT`，不會重複寫稽核列。

### 步驟 6 — 通知路徑的搜尋結果

```
git grep -rn "notification\|push_notification" -- \
  api/services/technician_lifecycle_service.py \
  api/services/technician_brand_auth_service.py \
  api/services/technician_certification_service.py
（無輸出，exit=1）

git grep -rn "technician.certification_revoked\|certification_revoked" -- api/ SQL/ web/ agent/
（無輸出，exit=1）
```

FR-TEC-08（`smartlock-docs/enterprise/04_SRS.md:358`）的處理欄為「排班/可用性設定；停權/認證撤銷即時廣播 `technician.certification_revoked`」，驗收欄為「各品牌訂閱後更新派工可用性」。程式碼實作的即時性機制是 pull-on-read（`technician_brand_auth_service.py:8-9`），非事件廣播。

TC 判定基準寫「重送不重複通知」／程式碼在撤銷、停權、復權三條路徑上皆無通知發送落點。此處僅並陳，不裁定。

### 步驟 7 — 執行既有測試

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest -p winloop_plugin \
  tests/test_technician_lifecycle.py tests/test_platform_technician_lifecycle.py \
  tests/test_platform_technician_management.py tests/test_cr_0115_technician_kyc_register.py \
  tests/test_technician_login_status_gate.py tests/test_duplicate_technician_email.py -q
45 passed in 7.88s
```

---

## 既有測試證據

- `api/tests/test_technician_lifecycle.py`、`api/tests/test_platform_technician_lifecycle.py`、`api/tests/test_platform_technician_management.py`：與其他三檔合跑 45 passed（步驟 7）。
- `api/tests/test_technician_login_status_gate.py`：涵蓋「停權/待核准技師不可登入」的 `users.is_active` 連動。
- 無對應既有測試涵蓋「撤銷認證後候選集變化」與「重送事件不重複通知」——對應行為在程式碼中不存在。

---

## 觀測到的其他事實

1. **`_EVENT_TRANSITIONS` 是描述性文件而非 gate**：`api/services/technician_lifecycle_service.py:48-52`

```python
# event_type ↔ (from, to) 對應
# ⚠️ 這張表目前**沒有任何地方讀它**（全檔唯一出現處就是這個定義）——它是描述性
# 文件而非 gate。真正的守衛是 _ALLOWED_TRANSITIONS + _check_transition，
# 值域守衛則在 DB 的 event_type CHECK（migration 126）。維護時兩邊都要補，
```

2. **DB 層 CHECK 曾在兩庫分岔**：`SQL/migrations/MIGRATION_REGISTRY.md:196` 記載 migration 105 「在兩庫 `schema_migrations` 都已登記，但技師庫 CHECK 實際只有 8 值（品牌庫 10 值）＝『登記了卻沒真的套』的假綠」，由 migration 126 收斂為 11 值。

3. **兩品牌候選池的隔離依據是 `brand` 字串**：`api/services/dispatch_service.py:365-370` 以 `WHERE brand = %s AND authorized = TRUE AND (cert_expires_at IS NULL OR cert_expires_at >= CURRENT_DATE)` 取授權集合，即 A 品牌撤證不影響 B 品牌的授權列。

4. **品牌授權閘門預設關閉**：`api/services/dispatch_service.py:310-330` docstring 自述「**預設 off**」且「目前**平台後台還沒有維護授權名單的 UI**」；`api/routers/platform_technicians.py:439-488` 顯示平台面已有 grant/revoke API 端點（CR-0166 R1-4）。兩段敘述的時點不同，本文件僅並陳，不裁定。
</content>
