# TC-PLT-PROV-01 — 品牌開站 provisioning（License 開通、建庫、綁 LINE、health check）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑既有 License／租戶 registry／品牌申請測試 31 項全過，並實跑 `provision_brand.py` 純邏輯測試 5 項（見步驟 7） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/services/brand_application_service.py`、`api/services/platform_tenant_service.py`、`api/routers/platform_tenants.py`、`scripts/deploy/provision_brand.py`、`scripts/db/provision-brand-tenant.sh`、`SQL/platform/Schema_platform.sql`、`SQL/platform/migrations/001-tenant-license-entitlements.sql`、`api/main.py`、`scripts/deploy/agent.sh` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | TC 四個判定要素在程式碼中三分：**(a) 冪等**——租戶登錄（`platform_tenant_service.py:199-220` ON CONFLICT (slug)）與品牌庫租戶列（`provision-brand-tenant.sh` 檔頭自述全 idempotent）皆冪等，但 `provision_brand.py:143-145` 對已存在的 `.env` 是**拒絕重跑**（return 1）而非冪等覆寫；**(b) License 閘**——License 欄位、更新端點、`assert_module_entitled` 皆存在（`platform_tenant_service.py:98-183`），但**無任何程式碼把「建庫/綁 LINE/health check 完成」設為 License 啟用的前置條件**，License 由平台管理員經 `PUT /platform/tenants/{id}/license` 直接寫入；**(c) provisioning audit**——`provisioning` 一詞在 `api/`、`SQL/` 與 `web/platform-console/` 全樹零命中，平台庫 schema（`SQL/platform/Schema_platform.sql`）無 audit 表，License 更新只落 `logger.info`（`platform_tenant_service.py:160-161`）；**(d) 綁 LINE 與 health check**——為 checklist 文字步驟（`provision_brand.py:100`、`:104-108`），非程式化 gate。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：新品牌申請、License、LINE sandbox、可重建 bundle fixture
- 步驟：核准後建庫、配置、綁定 LINE、health check；中途讓建庫或綁定失敗後重跑
- 預期結果（判定基準）：未完成任一步不得啟用 License；重跑冪等且有 provisioning audit；成功後僅新品牌可登入與進線
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-PLT-03｜屬於旅程腳本：SC-17

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 核准品牌申請 → 登錄租戶 | `api/services/brand_application_service.py:255-292`、`api/services/platform_tenant_service.py:190-220` | 有 |
| 建庫（品牌庫租戶列 + Admin） | `scripts/db/provision-brand-tenant.sh`（bash 腳本，人工執行） | 有（人工步驟） |
| 配置（部署 .env + License） | `scripts/deploy/provision_brand.py:37-63`、`:66-84` | 有（CLI） |
| 綁定 LINE | `scripts/deploy/provision_brand.py:100`（checklist 文字） | 無程式化步驟 |
| health check | `api/main.py:428-431`（服務 `/health`）、`scripts/deploy/agent.sh:275-291`（部署後 retry 探測） | 有（部署腳本層，未與 License 連動） |
| 未完成任一步不得啟用 License | — | **找不到**：License 寫入無前置條件檢查 |
| 重跑冪等 | `platform_tenant_service.py:203`（ON CONFLICT slug）、`provision-brand-tenant.sh:37-42`（檔頭自述）／`provision_brand.py:143-145`（.env 已存在 → 拒絕） | 部分 |
| provisioning audit | — | **找不到**：`provisioning` 於 `api/`、`SQL/`、`web/platform-console/` 零命中 |
| 成功後僅新品牌可登入與進線 | `api/core/deps.py:198-212`（TENANT_MISMATCH）、`:137-150`（CROSS_PORTAL_FORBIDDEN） | 有（tenant/portal 隔離，非 provisioning 專屬） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| platform_admin | 核准品牌申請 | `BrandApplicationApproved` | CAS pending→approved | `api/services/brand_application_service.py:269-280` | `UPDATE ... WHERE status='pending' RETURNING`；非 pending 走 `_raise_not_pending`（404/409） |
| 系統 | 核准連動登錄租戶 | `TenantRegistered` | 冪等 by slug | `api/services/platform_tenant_service.py:199-220` | `ON CONFLICT (slug) DO NOTHING`，撞號回既有 id |
| 系統 | 登錄失敗 | （不回滾核准） | fail-soft | `api/services/brand_application_service.py:282-287` | `except Exception` → `logger.exception`，核准仍成立 |
| 工程 | 產部署參數檔 | `BrandEnvGenerated` | 不覆蓋既有 | `scripts/deploy/provision_brand.py:143-146` | 檔已存在 → 印警告、`return 1`（不覆寫、不視為成功） |
| 工程 | 設 License | `LicenseGranted` | 未完成前置不得啟用 | `scripts/deploy/provision_brand.py:66-84`、`api/services/platform_tenant_service.py:123-162` | **無前置檢查**：直接 `UPDATE tenant SET plan_tier, entitled_modules` |
| 工程 | 建品牌庫租戶列 | `BrandTenantRowCreated` | 冪等 | `scripts/db/provision-brand-tenant.sh:36-42` | 檔頭自述「全 idempotent：租戶走 ON CONFLICT (id) DO NOTHING」 |
| 系統 | provisioning 過程留稽核 | `ProvisioningAudited` | 全程可稽核 | — | **找不到**：無 provisioning audit 表／事件 |
| 新品牌使用者 | 登入 | `LoginSucceeded` | tenant 隔離 | `api/core/deps.py:206-211` | `X-Tenant-ID` ≠ claim → 403 `TENANT_MISMATCH` |

---

## 逐層走查

### 步驟 1 — 「核准後開站」在程式碼中的定位

`api/services/brand_application_service.py:1-9` 檔頭自述設計裁決：

```python
"""品牌申請服務(CR-0114 R2)— landing 公開申請 + platform console 審核。

設計要點(業主裁決 2:核准後開站**純手動**):
  - 申請 = 意向書:不建帳號、不收密碼;核准只翻狀態 + 產「開站指引」純文字,
    實際開站由工程手動跑部署腳本。
```

同一裁決亦寫入 DB 註解，`SQL/platform/Schema_platform.sql:101`：

```sql
COMMENT ON TABLE brand_applications IS '品牌廠商鎖店平台使用申請(意向書);核准=記錄+產開站指引文字,開站流程純手動(CR-0114 裁決 2)';
```

TC 步驟寫「核准後建庫、配置、綁定 LINE、health check」為連續流程／程式碼把核准後各步驟定位為人工執行的 CLI 與 checklist（`scripts/deploy/provision_brand.py:87-110`）。此處僅並陳，不裁定。

### 步驟 2 — 核准路徑與租戶登錄的冪等性

`api/services/brand_application_service.py:269-292`

```python
    cur = await conn.execute(
        "UPDATE brand_applications SET status='approved', slug=%s, review_notes=%s, "
        "reviewed_by=%s::uuid, reviewed_at=NOW() "
        "WHERE id=%s::uuid AND status='pending' "
        f"RETURNING {_SELECT_COLS}",
        (final_slug, (review_notes or "").strip() or None, reviewer_id, app_id),
    )
    row = await cur.fetchone()
    if not row:
        await _raise_not_pending(conn, app_id)
    ...
    # CR-0118:核准後登錄租戶 registry(fail-soft:登錄失敗不擋核准,loud log)。
    tenant_id: str | None = None
    try:
        tenant_id = await platform_tenant_service.create_from_application(app)
    except Exception:  # noqa: BLE001 — registry 登錄失敗不可回滾已生效的核准
        logger.exception("brand_application 核准後租戶登錄失敗 app_id=%s slug=%s", app_id, final_slug)
```

`api/services/platform_tenant_service.py:199-220`

```python
    cur = await conn.execute(
        "INSERT INTO tenant "
        "(slug, company_name, contact_name, contact_email, contact_phone, application_id) "
        "VALUES (%s, %s, %s, %s, %s, %s::uuid) "
        "ON CONFLICT (slug) DO NOTHING RETURNING id",
        ...
    )
    row = await cur.fetchone()
    if row:
        logger.info("tenant 登錄 slug=%s from application=%s", slug, app.get("id"))
        return str(row[0])
    # slug 已存在(重複核准同代號)→ 回既有租戶 id
```

TC「重跑冪等」在此段成立：重複核准同 slug 回既有 tenant id，不建重複列。TC「中途讓建庫或綁定失敗後重跑」對應的失敗處置為 fail-soft（`:286-287`）——核准不因登錄失敗回滾。

### 步驟 3 — License 的實際 gate 位置

License 欄位由 `SQL/platform/migrations/001-tenant-license-entitlements.sql:13` 引入：

```sql
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS entitled_modules JSONB NOT NULL DEFAULT '["core"]'::jsonb;
```

寫入端點 `api/routers/platform_tenants.py:103-117`：

```python
@router.put(
    "/platform/tenants/{tenantId}/license",
    operation_id="updatePlatformTenantLicense",
    summary="更新租戶 License（訂閱級距／模組開通／到期日）",
    status_code=200,
)
async def update_tenant_license(
    body: LicenseUpdateBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
```

service 實作 `api/services/platform_tenant_service.py:123-162` 的驗證只有三項：`plan_tier` 值域（`:140-142`）、模組白名單（`:146-149`）、`core` 強制保留（`:145`）。**無**「建庫是否完成」「LINE 是否綁定」「health check 是否通過」等前置條件。

TC 判定基準寫「未完成任一步不得啟用 License」（出處：② 測試案例主表 TC-PLT-PROV-01 列）／程式碼在 License 寫入路徑上無任何 provisioning 完成度檢查（`platform_tenant_service.py:123-162` 全函式）。此處僅並陳，不裁定。

另：模組 gate 函式 `assert_module_entitled`（`platform_tenant_service.py:178-183`）在 `api/` 內除自身定義外零呼叫點：

```
git grep -rn "assert_module_entitled\|is_module_entitled" -- api/ | grep -v test
api/services/platform_tenant_service.py:165:async def is_module_entitled(...)
api/services/platform_tenant_service.py:178:async def assert_module_entitled(...)
api/services/platform_tenant_service.py:180:    if not await is_module_entitled(tenant_id, module):
```

實際消費該 License 的是 refinery 側 `knowledge-pipeline/refinery/refinery/entitlement.py:25-49`（獨立連平台庫查 `entitled_modules`）。

### 步驟 4 — 「建庫」與「.env」兩支腳本的冪等差異

`scripts/deploy/provision_brand.py:143-147`

```python
    if env_path.exists():
        print(f"⚠️  {env_path} 已存在，不覆蓋（手動處理避免蓋掉既有品牌設定）", file=sys.stderr)
        return 1
    env_path.write_text(env_content, encoding="utf-8")
    print(f"✅ 已產生 {env_path}")
```

退出碼語意在檔頭 `scripts/deploy/provision_brand.py:17`：「0 成功；1 參數/驗證錯誤；2 DB 操作失敗」——即重跑同一 slug 回 exit 1（歸類為驗證錯誤），不是冪等成功。

`scripts/db/provision-brand-tenant.sh:36-42` 檔頭：

```
# 全 idempotent：租戶走 ON CONFLICT (id) DO NOTHING；admin 因**品牌庫 users 沒有
# email 唯一約束**（只有 id PK 與 line_user_id unique，與平台庫不同）不能用
# ON CONFLICT (email)，改以「同 tenant + 同 email」為邏輯鍵的 NOT EXISTS /
# UPDATE-or-INSERT。預設不覆寫既有密碼，要重設加 --reset-password。
```

同檔 `:5-16` 記錄了兩支腳本之間的既有斷點事實：

```
#   而 `scripts/deploy/provision_brand.py` 會把**平台庫**的租戶 UUID 寫進
#   `brands/<slug>.env` 的 `AGENT_TENANT_ID`。兩者一對照就是：新品牌的
#   AGENT_TENANT_ID 指向一個**在它自己品牌庫裡並不存在**的租戶 →
#   任何 per-tenant 寫入都會 FK violation，第二個品牌從第一天就是壞的。
```

### 步驟 5 — provisioning audit 的搜尋結果

```
git grep -rn "provisioning" -- api/ SQL/ web/platform-console
（無輸出，exit=1）
```

全 repo 帶 `provision` 字樣的**程式碼**檔僅三支：`scripts/db/provision-brand-tenant.sh`、`scripts/deploy/provision_brand.py`、`scripts/deploy/test_provision_brand.py`；其餘命中全在文件（`smartlock-docs/`、`CHANGELOG.md`、`docs/`、`drawio/`）。

平台庫 schema `SQL/platform/Schema_platform.sql` 的建表語句共五處：`users`（`:17`）、`revoked_jti`（`:50`）、`brand_applications`（`:63`）、`monitor_target`（`:112`）、`tenant`（`:139`），無 audit／event 表。

License 變更留痕僅為 log 行，`api/services/platform_tenant_service.py:160-161`：

```python
    logger.info("license updated tenant=%s tier=%s modules=%s by=%s",
                tenant_id[:8], new_tier, mods, (actor_user_id or "?")[:8])
```

TC 判定基準寫「重跑冪等且有 provisioning audit」／程式碼無 provisioning audit 落點（表、事件、稽核服務皆無）。此處僅並陳，不裁定。

### 步驟 6 — health check 與 LINE 綁定的落點

服務層 health endpoint `api/main.py:428-431`：

```python
@app.get("/health")
async def health():
    ...
    db_ok = await healthcheck()
```

部署腳本層 `scripts/deploy/agent.sh:275-291` 有 `health_check_with_retry()`，於 `:402` 部署後呼叫。

LINE 綁定與品牌庫租戶列則落在 `scripts/deploy/provision_brand.py:87-110` 的 checklist 純文字：

```python
        "[6] ⬜ LINE 綁定：webhook URL 填入 LINE console，rich menu 建立",
        ...
        "[7] ⬜ 品牌庫租戶列 + Admin 帳號（缺租戶列 → per-tenant 寫入全部 FK violation）：",
        "      ./scripts/db/provision-brand-tenant.sh \\",
```

checklist 的 `[2]` 項是唯一與 License 相關的一行（`:92`），其勾選狀態只依「有沒有帶 `--tenant-id`」決定：

```python
        f"[2] {'✅' if tenant_id else '⬜'} 租戶 License 已設定" + (f"（tenant={tenant_id}）" if tenant_id else "（--tenant-id 未帶，略過）"),
```

### 步驟 7 — 執行既有測試

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest -p winloop_plugin \
  tests/test_cr_0166_license.py tests/test_platform_tenants.py \
  tests/test_platform_brand_applications.py -q
31 passed in 10.21s

python -m pytest scripts/deploy/test_provision_brand.py -q
5 passed in 0.10s
```

License 值域與 `core` 強制保留由 `api/tests/test_cr_0166_license.py:108-124` 釘住：

```python
    assert r.json()["data"]["entitled_modules"] == ["core"]
    ...
                          json={"plan_tier": "pro", "entitled_modules": ["refinery"]})
    ...
    assert set(d["entitled_modules"]) == {"core", "refinery"}  # core 強制保留
    ...
                         json={"entitled_modules": ["bogus_module"]})
```

`scripts/deploy/test_provision_brand.py` 檔頭自述範圍為「純邏輯 smoke test（不需 DB/部署）」，涵蓋 `render_brand_env` 與 slug 驗證，未涵蓋 `set_license` 與 checklist 的 provisioning 順序。

---

## 既有測試證據

- `api/tests/test_cr_0166_license.py`、`api/tests/test_platform_tenants.py`、`api/tests/test_platform_brand_applications.py`：合計 31 項，全過（步驟 7）。
- `scripts/deploy/test_provision_brand.py`：5 項，全過。
- 無對應既有測試涵蓋「provisioning 中途失敗後重跑」與「provisioning audit」——`git grep -rn "provisioning" -- api/tests scripts` 零命中。

---

## 事實結論

1. 品牌申請核准 → 平台庫租戶登錄的路徑存在且冪等（`platform_tenant_service.py:203` ON CONFLICT slug），登錄失敗為 fail-soft（`brand_application_service.py:286-287`）。
2. License 資料模型（`SQL/platform/migrations/001-tenant-license-entitlements.sql:13`）、讀寫端點（`api/routers/platform_tenants.py:90-117`）、模組 gate 函式（`platform_tenant_service.py:178-183`）皆存在。
3. License 寫入路徑無 provisioning 完成度前置檢查；`assert_module_entitled` 在 `api/` 內無呼叫點，實際消費者為 refinery（`knowledge-pipeline/refinery/refinery/entitlement.py:52-57`）。
4. `provisioning` 於 `api/`、`SQL/`、`web/platform-console/` 零命中；平台庫 schema 無 audit 表；License 變更只留 `logger.info`（`platform_tenant_service.py:160-161`）。
5. 重跑冪等在三處落點不一致：租戶登錄冪等、品牌庫租戶列冪等（腳本自述）、`.env` 產生為拒絕重跑（`provision_brand.py:143-145`，exit 1）。
6. LINE 綁定與 health check 於 provisioning 流程中為 checklist 文字步驟（`provision_brand.py:100`），未與 License 啟用狀態連動；服務層 `/health`（`api/main.py:428`）與部署腳本的 retry 探測（`scripts/deploy/agent.sh:275-291`）獨立存在。
7. 「成功後僅新品牌可登入與進線」對應的機制為既有 tenant/portal 隔離（`api/core/deps.py:206-211`、`:143-150`），非 provisioning 專屬邏輯。
</content>
</invoke>
