# TC-TEC-LIFE-01 — 技師註冊、KYC、指定服務品牌、重送、未核可不得接單

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑技師生命週期／KYC 註冊／登入 gate 相關 6 檔 45 項全過（見步驟 7） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/services/auth_service.py:619-780`、`api/core/tech_mirror.py`、`api/core/db.py`、`api/services/technician_kyc_service.py`、`api/services/technician_brand_auth_service.py`、`api/services/technician_lifecycle_service.py`、`api/services/dispatch_service.py:185-192/333-388/414-478/603-608`、`api/routers/auth.py:360-375`、`SQL/migrations/089/090/105/126` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | **「身分只寫 lock_tech」**：註冊走 `require_tech_conn()` 寫權威庫（`auth_service.py:654`），但同一函式**在 commit 後把 users/technicians/technician_certification 鏡射到品牌庫**（`auth_service.py:734-748`），此為 CR-0112 方案 B 的刻意投影設計（`api/core/tech_mirror.py:1-19`）；敏感 PII（`technician_kyc`）明確不鏡射（`auth_service.py:728`）。**重送冪等**：以「同 email + role='technician'」擋重，回 409 `EMAIL_TAKEN`（`auth_service.py:658-665`），非冪等回既有資源。**未核可者不進候選池**：`_DISPATCH_INELIGIBLE_STATUSES` 硬排除 `pending_approval/suspended/terminated/rejected`（`dispatch_service.py:187-192`、`:429-431`）。**未授權者不進候選池**：僅在**自動派工**成立（`dispatch_service.py:603-608`），人工候選查詢改為「標示不過濾」（`dispatch_service.py:537-545`），且授權 fail-closed 需 M18 開關 `dispatch_policy.brand_auth_enforce`（預設 off，`dispatch_service.py:310-330`）。**`technician.registered` 事件**在 `api/`、`agent/`、`SQL/`、`web/` 全樹零命中。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：未註冊、已註冊、跨品牌申請技師 fixture
- 步驟：註冊、補 KYC、指定服務品牌、重送註冊、未核可身分嘗試接單
- 預期結果（判定基準）：身分只寫 lock_tech；重送冪等；未核可或未授權者永不進候選池
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-TEC-01｜屬於旅程腳本：SC-12

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 技師自助註冊 | `api/routers/auth.py:367-372`、`api/services/auth_service.py:619-695` | 有 |
| 身分寫入權威庫（lock_tech） | `api/services/auth_service.py:653-654`、`api/core/db.py`（`require_tech_conn`） | 有 |
| 身分「只」寫 lock_tech | `api/services/auth_service.py:734-748`（鏡射品牌庫） | 部分：非敏感投影會鏡射 |
| 敏感 PII 不外流品牌庫 | `api/services/auth_service.py:727-728`、`api/core/tech_mirror.py:44-49` | 有 |
| 補 KYC | `api/services/auth_service.py:696-709`、`api/services/technician_kyc_service.py`（上傳 token） | 有 |
| 指定服務品牌 | `api/services/technician_brand_auth_service.py:75-101`（平台授權）／註冊時 `regions`/`capabilities`（`auth_service.py:628-629`） | 有（授權由平台方 grant，非技師自選即生效） |
| 重送註冊冪等 | `api/services/auth_service.py:658-665` | 部分：回 409 `EMAIL_TAKEN`，非冪等回既有 |
| 未核可者永不進候選池 | `api/services/dispatch_service.py:187-192`、`:429-431` | 有 |
| 未授權者永不進候選池 | `api/services/dispatch_service.py:603-608`（auto）／`:537-545`（manual 僅標示） | 部分 |
| `technician.registered` 事件 | — | **找不到**：全樹零命中 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 未註冊技師 | 送註冊表單 | `TechnicianRegistered` | 身分落權威庫 | `api/services/auth_service.py:674-695` | 同一 transaction 寫 `users`(is_active=FALSE) + `technicians`(status='pending_approval') |
| 系統 | 註冊後鏡射投影 | `TechnicianProjectionMirrored` | 兩庫不分岔 | `api/services/auth_service.py:734-748` | `mirror_rows("users"/"technicians"/"technician_certification")`；失敗 fail-soft（`:741-748`） |
| 技師 | 補 KYC（Tier 2 PII） | `KycSubmitted` | 加密 + 不鏡射 | `api/services/auth_service.py:696-709`、`:727-728` | 寫 `technician_kyc`（`encrypt_pii`），註解明載「**不鏡射**到品牌庫（§8-1 最小揭露）」 |
| 已註冊技師 | 用相同 email 重送註冊 | `RegistrationRejected(409)` | email 角色內唯一 | `api/services/auth_service.py:658-665` | 409 `EMAIL_TAKEN` |
| 平台方 | 授權技師某品牌 | `BrandAuthorizationGranted` | 冪等 upsert | `api/services/technician_brand_auth_service.py:89-101` | `ON CONFLICT (technician_id, brand) DO UPDATE SET authorized=TRUE` + 鏡射 + lifecycle audit |
| 未核可技師 | 出現在派工候選池 | （不應發生） | 生命週期硬排除 | `api/services/dispatch_service.py:429-431` | `if not _is_dispatch_eligible(status): continue` |
| 未授權技師 | 出現在自動派工候選 | （不應發生） | 品牌授權 | `api/services/dispatch_service.py:606-608` | `_auth_ids` 非 None 時過濾；None（無授權資料且開關 off）不過濾 |

---

## 逐層走查

### 步驟 1 — 註冊入口與權威庫寫入

`api/routers/auth.py:367-372`

```python
async def register_technician(
    ...
    payload = await auth_service.register_technician(body.model_dump())
```

`api/services/auth_service.py:653-654`

```python
    # CR-0112 方案 B：技師身分寫入落權威庫（fallback 時即主庫），完成後鏡射投影。
    conn = await db_module.require_tech_conn()
```

寫入內容 `api/services/auth_service.py:674-695`：

```python
    async with conn.transaction():
        # is_active=FALSE：待核准前不可登入（BR-M07-01 上線審核 gate；
        # onboard-approve 時由 technician_lifecycle_service 同步翻 TRUE）
        await conn.execute(
            "INSERT INTO users (id, tenant_id, tenant_type, display_name, phone, email, password_hash, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, 'technician', %s, %s, %s, %s, 'technician', FALSE)",
            ...
        )
        # CR-0115：technicians 加 Tier 1 非敏感欄位（全 nullable）
        await conn.execute(
            "INSERT INTO technicians (id, tenant_id, user_id, name, phone, email, "
            ...
            "'pending_approval', %s, %s, %s, %s, %s, %s, %s)",
```

初始 `status='pending_approval'`、`users.is_active=FALSE`。

### 步驟 2 — 「只寫 lock_tech」與投影鏡射並存

`api/services/auth_service.py:727-748`

```python
    # 投影鏡射（順序 users → technicians，投影側 FK technicians→users）
    # 注意：technician_kyc 敏感 PII **不鏡射**到品牌庫（§8-1 最小揭露）。
    # CR-0178 UAT-0720-11 R1 加固：權威庫已 commit，跨庫投影非原子——鏡射失敗
    # fail-soft（註冊仍成功）＋大聲留痕待補償：...
    try:
        await mirror_rows("users", [user_id])
        await mirror_rows("technicians", [technician_id])
        ...
        if cert_ids:
            await mirror_rows("technician_certification", cert_ids)
    except Exception:  # noqa: BLE001 — fail-soft：鏡射失敗不擋註冊
```

投影機制的設計依據，`api/core/tech_mirror.py:1-19`：

```python
"""技師身分投影鏡射(CR-0112 方案 B)。

架構:tech DB(TECH_POSTGRES_URI)為技師身分**權威庫**;品牌庫保留技師列
作**投影(mirror)** —— 35 張品牌表(work_orders/dispatch_logs/notifications/
revoked_jti…)FK 指向 users/technicians,投影使 FK 與派工/佣金 JOIN 全不用改。
...
單庫 fallback(TECH_POSTGRES_URI 未設)時全部 no-op —— 權威連線即主連線,
```

投影表白名單為 5 張（`api/core/tech_mirror.py:43-49`：`users` / `technicians` / `technician_skill` / `technician_brand_authorization` / `technician_certification`），`users` 另有欄位白名單，同檔 `:51-56` 註明「**不鏡射 password_hash/email/phone/address 等憑證/PII**」。

TC 判定基準寫「身分只寫 lock_tech」（出處：② 測試案例主表 TC-TEC-LIFE-01 列；FR-TEC-01 於 `smartlock-docs/enterprise/04_SRS.md:351` 的驗收欄為「技師身分獨立於任何品牌租戶」）／程式碼把權威寫入落 lock_tech，另以受限欄位投影到品牌庫供 FK 與 JOIN 使用。此處僅並陳，不裁定。

### 步驟 3 — KYC 補件

Tier 2 敏感 PII 於註冊時同交易寫入（若有帶），`api/services/auth_service.py:696-709`：

```python
        # CR-0115 Tier 2：敏感 PII 加密後存獨立 technician_kyc 表（§8-1）
        if has_kyc:
            await conn.execute(
                "INSERT INTO technician_kyc (technician_id, tenant_id, national_id_enc, "
                ...
                    encrypt_pii(national_id), last_n(national_id, 3),
                    bank_code, encrypt_pii(bank_account), last_n(bank_account, 4),
```

事後補件走上傳 token，`api/services/auth_service.py:750-762`：

```python
    # CR-0115 §8-2a：簽發兩階段文件上傳 token（Tier 3；明文僅出現在本 response，
    # 落庫只存 SHA-256）。fail-soft：migration 090 未套的異質部署註冊仍成功、僅少 token。
    upload_token: dict | None = None
    try:
        from services import technician_kyc_service

        upload_token = await technician_kyc_service.issue_upload_token(
            conn, technician_id=technician_id
        )
```

核准端有 KYC 齊全度閘，`api/services/technician_lifecycle_service.py:250-271`：

```python
    from services import technician_kyc_service as kyc_svc

    conn = await db_module.require_tech_conn()
    missing = await kyc_svc.missing_required_doc_types(conn, technician_id=tech_id)

    if not missing:
        return await _change_status_and_audit(
            ... event_type="onboarding_approved", ...
        )

    missing_label = "、".join(missing)
    if not conditional:
        raise ApiError(
            "KYC_DOCUMENTS_INCOMPLETE",
            ...
            422,
        )
```

同函式 docstring `:234-238` 記錄此閘的成因：「在此之前本函式對文件**零檢查**——實測 6 個 active 技師 100% 零文件」。

### 步驟 4 — 指定服務品牌

註冊表單收的是 `capabilities` / `regions`（`api/services/auth_service.py:628-629`），寫入 `technicians.capabilities` / `service_regions`（`:687`）。

派工用的「品牌授權」是另一張表，由平台方 grant，`api/services/technician_brand_auth_service.py:1-12`：

```python
"""技師品牌授權 grant/revoke（CR-0166 R1-4）。

technician_brand_authorization（063）原僅 seed，執行期不可授/撤——但 dispatch
候選過濾與 F9 手動派工 _assert_brand_authorized 都讀它。本 service 讓平台方營運
可即時授權/撤證。
```

`api/services/technician_brand_auth_service.py:89-101`

```python
    cur = await conn.execute(
        "INSERT INTO technician_brand_authorization "
        "  (technician_id, brand, authorized, cert_expires_at, is_mock) "
        "VALUES (%s::uuid, %s, TRUE, %s::date, FALSE) "
        "ON CONFLICT (technician_id, brand) DO UPDATE SET "
        "  authorized = TRUE, cert_expires_at = EXCLUDED.cert_expires_at, is_mock = FALSE "
        f"RETURNING {_SELECT}",
        (technician_id, brand, cert_expires_at or None),
    )
    row = await cur.fetchone()
    await mirror_rows("technician_brand_authorization", [str(row[0])])
    await _audit_lifecycle(tenant_id, technician_id, "brand_auth_granted", actor_user_id, brand, reason)
```

TC 步驟寫「指定服務品牌」／程式碼分兩處：技師自填 `capabilities`（不影響授權判定）與平台方 grant 授權（影響派工）。此處僅並陳，不裁定。

### 步驟 5 — 重送註冊

`api/services/auth_service.py:656-665`

```python
    # 重複 email 檢查（CR-0090：依角色限定 — 同 email 可同時為技師與廠商，
    # 但同一角色內仍唯一。登入端點以 role 過濾故不衝突）
    cur = await conn.execute(
        "SELECT 1 FROM users WHERE email = %s AND role = 'technician' LIMIT 1",
        (email,),
    )
    if await cur.fetchone():
        raise ApiError(
            "EMAIL_TAKEN", f"Email {email} is already registered as a technician", 409
        )
```

TC 判定基準寫「重送冪等」／程式碼對重送回 409 `EMAIL_TAKEN`（拒絕），不建重複列亦不回既有資源。此處僅並陳，不裁定。

同檔 `:729-733` 另記錄一項相關的既有處置：

```python
    # fail-soft（註冊仍成功）＋大聲留痕待補償：核准前投影無剛性消費者（審核讀
    # 權威庫；派工前 ensure_technician_projection 自癒；核准時 lifecycle mirror
    # upsert 補建缺列）。原本未捕捉 → 註冊回 500 但權威庫已寫入，技師重試撞
    # EMAIL_TAKEN 409（幽靈帳號＋投影缺列的狀態分裂）。
```

### 步驟 6 — 未核可 / 未授權者是否進候選池

生命週期硬排除，`api/services/dispatch_service.py:185-192`：

```python
# CR-0051 / BR-M06 / G004-G005：生命週期「不可派工」狀態（未核准/停權/終止/退回）—
# 與「操作性不可用」（inactive/on_leave/circuit）區分；前者一律硬排除候選，不受 exclude_circuit 影響。
_DISPATCH_INELIGIBLE_STATUSES = {"pending_approval", "suspended", "terminated", "rejected"}


def _is_dispatch_eligible(status: str | None) -> bool:
    """BR-M06：技師是否具派工資格（生命週期狀態非未核准/停權/終止/退回）。"""
    return status not in _DISPATCH_INELIGIBLE_STATUSES
```

套用點在共用評分函式 `api/services/dispatch_service.py:427-431`：

```python
        status = r[9]  # 對齊 _TECH_SELECT（生命週期）
        online_state = r[11]  # 對齊 _TECH_SELECT（操作可用性,CR-0117 S5 熔斷判此欄）
        # CR-0051 / BR-M06：生命週期不可派工（未核准/停權/終止/退回）一律硬排除，不受 exclude_circuit 影響
        if not _is_dispatch_eligible(status):
            continue
```

`_score_rows` 同時被 `list_dispatch_candidates`（`:528`）與 `auto_match_dispatch`（`:602`）呼叫，故兩條路徑皆覆蓋。

登入層另有對應 gate：`api/services/technician_lifecycle_service.py:120-133` 於狀態變更時同步 `users.is_active`（`active` → TRUE，其餘 → FALSE），註解 `:120-123` 自述「原本兩者脫鉤 → 停權/待核准技師仍可登入」。

品牌授權過濾則分兩條路徑，`api/services/dispatch_service.py:603-608`：

```python
    # CR-0114 R4（裁決 7）：**自動派工維持只選已授權**——人工派工可挑未授權
    # (list_dispatch_candidates 標示可見),但自動指派不該自行派給沒修過該鎖品牌
    # 的師傅。無授權資料(None)時保守不過濾(沿用原語意)。
    _auth_ids = await _brand_authorized_ids(pc_brand)
    if _auth_ids is not None:
        scored = [c for c in scored if c["technician"].get("id") in _auth_ids]
```

人工候選查詢 `api/services/dispatch_service.py:537-545`：

```python
    # CR-0114 R4（裁決 3）：鎖品牌授權由「過濾」改「標示」——全部啟用中師傅
    # 皆可見,每人標 brand_authorized（true/false/null）,已授權排前供人工挑選。
    # null = 該品牌無任何授權資料(無從判定;沿用原保守語意,不標未授權)。
    auth_ids = await _brand_authorized_ids(wo_brand)
    for c in candidates:
        if auth_ids is None:
            c["brand_authorized"] = None
        else:
            c["brand_authorized"] = c["technician"].get("id") in auth_ids
```

「查無授權列」的處置由 M18 開關決定，`api/services/dispatch_service.py:372-387`：

```python
    if not rows:
        # 空集合＝誰都不符＝下游自然 fail-closed；None＝不判斷＝維持原本的放行。
        # 由 M18 開關決定走哪一邊（CR-0197 D1(c)）。
        if await brand_auth_enforced():
            logger.warning(...)
            return set()
        # 閘門未啟用：維持 CR-0060 以來的行為。記 info 而非靜默 ——
        logger.info(
            "品牌「%s」無有效授權技師，但 dispatch_policy.brand_auth_enforce 未啟用 "
            "→ 不阻擋（CR-0197 D1(c)：待營運補齊名單後再開）", brand,
        )
        return None
```

該開關預設 off，`api/services/dispatch_service.py:310-330` docstring 自述：「M18 config `dispatch_policy.brand_auth_enforce`，**預設 off**」「目前**平台後台還沒有維護授權名單的 UI**」。

TC 判定基準寫「未核可或未授權者永不進候選池」／程式碼對「未核可」硬排除（兩條路徑皆是），對「未授權」僅在自動派工過濾、人工候選改為標示，且無授權資料時是否阻擋取決於預設 off 的開關。此處僅並陳，不裁定。

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

- `api/tests/test_technician_lifecycle.py`、`api/tests/test_platform_technician_lifecycle.py`、`api/tests/test_platform_technician_management.py`、`api/tests/test_cr_0115_technician_kyc_register.py`、`api/tests/test_technician_login_status_gate.py`、`api/tests/test_duplicate_technician_email.py`：合計 45 項，全過（步驟 7）。
- `api/tests/test_cr_0090_cross_role_email.py:75-77` 直接斷言重送註冊拋錯（同一 email 同角色）。

---

## 觀測到的其他事實

1. **`technician.registered` 事件在程式碼零命中**：

```
git grep -rn "technician.registered\|technician_registered" -- api/ SQL/ web/ agent/
（無輸出，exit=1）
```

FR-TEC-01（`smartlock-docs/enterprise/04_SRS.md:351`）的處理欄含「→ `technician.registered` 事件」。TC 未直接列此識別碼，本項僅列為觀測事實。此處僅並陳，不裁定。

2. **註冊時 tenant 為固定 UUID**：`api/services/auth_service.py:670`

```python
    tenant_id = "00000000-0000-0000-0000-000000000001"
```

`api/services/platform_technician_service.py:27` 註解自述此為「平台建立師傅的預設租戶(師傅身分庫全平台共用;對齊 auth_service.register_technician」。

3. **條件式核准會讓缺件技師成為一般 `active`**：`api/services/technician_lifecycle_service.py:245-248`

```python
    刻意**不**新增狀態值(§8-D2(a)):條件式核准的技師就是一般 active,派工資格
    不打折。要區分兩種 active 就得改 dispatch_service.py:186 的 fail-open
    黑名單與散在 4 個站台的 10 份 exhaustive Record,成本高一個數量級,
```

4. **`levels_filter` 參數收下但不生效**：`api/services/dispatch_service.py:487-495` 註解自述「**本參數目前完全不生效** —— 收下但從未傳給 `_score_rows`」，使用時只記 warning（`:502-506`）。此與 TC-TEC-LIFE-01 無直接關係，列為走查同檔時觀測到的事實。
</content>
