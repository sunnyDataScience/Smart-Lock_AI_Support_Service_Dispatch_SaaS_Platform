# TC-COMPLIANCE-01 — GDPR forget 兩階段（T0 軟刪 / T+30 硬刪）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補本機測試庫實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

判定理由（事實）：TC 判定基準四項中，「軟刪即時生效」「T+30 硬刪 cron 存在」「ledger append」三項在程式碼中有對應落點（`api/services/gdpr_forget_service.py:242-341`、`api/realtime/gdpr_hard_delete_cron.py:97-132`、`SQL/migrations/113-purge-audit-ledger.sql:23-51`）；第四項「記憶（`agent.*`）與營運資料同步涵蓋」在程式碼中無對應——`memory_entry`／`agent.escalation` 兩個識別碼在 `api/` 全樹零命中（見步驟 6）。另觀測到 cron 的 `hard_delete` 呼叫參數與 service 簽名不一致（步驟 4）。

---

## TC 原文

（來源：`smartlock-docs/enterprise/20_Test_Cases.md` 之 TC-COMPLIANCE 段，及批次 A 派工單）

| 欄位 | 內容 |
|---|---|
| 章節 | 11. 合規案例（TC-COMPLIANCE） |
| 前置 | （未列） |
| 步驟 | 客戶提 GDPR forget → 觀察 T0 與 T+30 |
| 預期結果（判定基準） | 兩階段：軟刪即時生效 → T+30 硬刪 cron 執行 + ledger append；記憶（agent.*）與營運資料同步涵蓋 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-API-16、NFR-Comp-004、NFR-Priv-005、NFR-Priv-008 |
| 屬於哪條旅程腳本 | SC-19 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| T0 軟刪即時生效（清 PII） | `api/services/gdpr_forget_service.py:296-304` | 有落點 |
| T0 crypto-shred（銷 DEK） | `api/services/gdpr_forget_service.py:311-312` | 有落點 |
| T+30 cooldown 強制 | `api/services/gdpr_forget_service.py:276-278`、`:369-375` | 有落點 |
| T+30 硬刪 cron 執行 | `api/realtime/gdpr_hard_delete_cron.py:97-132` | 有落點；呼叫參數與 service 簽名不一致（步驟 4） |
| ledger append（purge_audit） | `api/services/gdpr_forget_service.py:51-69`、`:336-340`、`:429-433` | 有落點 |
| ledger append（audit_events） | `api/services/gdpr_forget_service.py:33-48` | 有落點 |
| 營運資料涵蓋（users 列） | `api/services/gdpr_forget_service.py:296-304`、`:392-394` | 有落點 |
| 記憶 `agent.*` 涵蓋 | — | **無對應**（`memory_entry` 於 `api/` 零命中，步驟 6） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶／admin／DPO | 提 forget request | `ForgetRequestReceived` | status 起始 `received`；同人 pending 冪等 | `api/services/gdpr_forget_service.py:113-148` | INSERT + 冪等回既有 + audit `gdpr_forget_received` |
| admin | `:soft-delete` | `PiiSoftDeleted` | legal-hold 未持有才可執行 | `api/services/gdpr_forget_service.py:263-274`、`:296-304` | legal-hold 命中則 423；否則 UPDATE users 清 PII 明文與密文欄 |
| admin | `:soft-delete` | `DekDestroyed` | crypto-shredding（NFR-Priv-008 T0） | `api/services/gdpr_forget_service.py:311-312` | 呼 `dek_service.destroy_dek`，回傳值入 audit `dek_crypto_shredded` |
| 系統 cron | T+30 掃 eligible | `PiiHardDeleted` | `hard_delete_eligible_at <= NOW()` | `api/realtime/gdpr_hard_delete_cron.py:102-121` | SELECT 後逐筆呼 `gdpr_forget_service.hard_delete` |
| 系統 | 硬刪後記帳 | `PurgeAuditAppended(phase=hard_delete_t30)` | append-only | `api/services/gdpr_forget_service.py:429-433`、`SQL/migrations/113-purge-audit-ledger.sql:44-51` | INSERT purge_audit；trigger 擋 UPDATE/DELETE |
| 系統 | 清 agent 記憶 | `AgentMemoryPurged` | 記憶同步涵蓋 | — | **找不到**：`api/` 全樹無 `agent.memory_entry` 寫入或刪除 |

---

## 逐層走查

### 步驟 1 — API 路由層：7 個端點與角色守衛

`api/routers/gdpr_forget_v2.py:1-10` 檔頭列出 7 個端點。所有寫入端點的守衛皆為 `role_required(*FULL_ACCESS_ROLES)` + `_require_initiator`。

`api/routers/gdpr_forget_v2.py:138-153`（軟刪）：

```python
@router.post(
    "/tenants/{tenantId}/gdpr/forget-requests/{requestId}:soft-delete",
    operation_id="softDeleteGdprForgetRequest",
    summary="T0+ 軟刪 + clear PII（received → soft_deleted）",
    response_model=dict,
)
async def soft_delete(
    tenantId: str = Path(...),
    requestId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.soft_delete(
        request_id=requestId, tenant_id=tenantId, actor_user_id=initiator)
    return {"data": result}
```

`api/routers/gdpr_forget_v2.py:156-171` 為硬刪端點，形狀相同（`svc.hard_delete(request_id=..., tenant_id=..., actor_user_id=...)`）。

### 步驟 2 — service 層：T0 軟刪的實際動作

`api/services/gdpr_forget_service.py:296-304`：

```python
    await _conn.execute(
        "UPDATE users SET "
        "  display_name = '[REDACTED]', "
        "  email = '[REDACTED-' || id::text || ']', "
        "  phone = NULL, "
        f"  updated_at = NOW(){_enc_clear} "
        "WHERE id = %s::uuid",
        (subject_user_id,),
    )
```

`_enc_clear` 於 `api/services/gdpr_forget_service.py:289-295` 組出，對非技師列另清 `display_name_enc / email_enc / phone_enc / email_bidx / phone_bidx`。

30 天 cooldown 常數在 `api/services/gdpr_forget_service.py:30`：

```python
HARD_DELETE_COOLDOWN_DAYS = 30
```

寫入 `hard_delete_eligible_at` 於 `api/services/gdpr_forget_service.py:276-278`、`:315-325`。

### 步驟 3 — service 層：T+30 硬刪與 cooldown 檢查

`api/services/gdpr_forget_service.py:369-375`：

```python
    eligible_at = datetime.fromisoformat(eligible_at_str.replace("Z", "+00:00"))
    if datetime.now(timezone.utc) < eligible_at:
        raise ApiError(
            "STATE_CONFLICT",
            f"cooldown 未滿（eligible_at={eligible_at_str}）",
            409,
        )
```

實體刪除與 FK 阻擋的處理在 `api/services/gdpr_forget_service.py:383-407`；FK 阻擋時 `physical_deleted = False`，狀態仍推進為 `hard_deleted`，處置值記入 audit（`:426-427`）：

```python
        extra={"physical_deleted": physical_deleted,
               "disposition": "physical_delete" if physical_deleted else "anonymized_retained_fk"})
```

### 步驟 4 — cron 層：T+30 自動執行

`api/realtime/gdpr_hard_delete_cron.py:102-121`：

```python
        cur = await db_module._conn.execute(
            "SELECT id FROM saas.forget_request "
            "WHERE status = 'soft_deleted' "
            "  AND hard_delete_eligible_at IS NOT NULL "
            "  AND hard_delete_eligible_at <= NOW() "
            "ORDER BY hard_delete_eligible_at ASC "
            "LIMIT %s",
            (self._batch_size,),
        )
        rows = await cur.fetchall()
        ...
                from services import gdpr_forget_service
                await gdpr_forget_service.hard_delete(
                    request_id=request_id,
                    actor_user_id=None,  # NULL 表系統自動
                )
```

該呼叫傳入 `request_id` 與 `actor_user_id` 兩個具名參數。被呼叫端 `api/services/gdpr_forget_service.py:344-346` 的簽名為：

```python
async def hard_delete(
    *, request_id: str, tenant_id: str, actor_user_id: str | None = None,
) -> dict:
```

以 AST 取出的參數表（探針腳本不在 repo 內，僅於 scratchpad 執行）：

```
kwonly: ['request_id', 'tenant_id', 'actor_user_id']
defaults: [None, None, 'None']
```

即 `tenant_id` 為必填且無預設值。cron 的呼叫未傳 `tenant_id`。`api/realtime/gdpr_hard_delete_cron.py:127-131` 的 `except Exception` 會把該次呼叫計入 `errors` 並 `logger.exception`。

TC 判定基準寫「T+30 硬刪 cron 執行」（出處：批次 A TC 原文第 8 行）／程式碼的 cron 呼叫與 service 簽名不一致（`gdpr_hard_delete_cron.py:118-121` vs `gdpr_forget_service.py:344-346`）。此處僅並陳，不裁定。

### 步驟 5 — DB 層：ledger 與狀態機

`SQL/migrations/021-gdpr-forget-requests.sql:16-59` 定義 `saas.forget_request`，5 個 status：

```sql
  status              text        NOT NULL DEFAULT 'received' CHECK (status IN (
    'received',           -- T0：剛收到 request，待 legal-hold check
    'legal_hold_denied',  -- legal-hold 衝突（爭議/仲裁/警方）→ 拒絕
    'soft_deleted',       -- T0+: 軟刪 + 金鑰銷毀完成
    'hard_deleted',       -- T+30：硬刪完成（physical delete）
    'cancelled'           -- 客戶撤回 request
  )),
```

cron 掃描用的 partial index 在 `SQL/migrations/021-gdpr-forget-requests.sql:65-67`。

`SQL/migrations/113-purge-audit-ledger.sql:23-38` 定義專用帳本 `saas.purge_audit`（`phase IN ('soft_delete_t0','hard_delete_t30')`、`crypto_shredded`、`physical_deleted`）；`:44-51` 為 append-only trigger：

```sql
CREATE TRIGGER trg_purge_audit_append_only
    BEFORE UPDATE OR DELETE ON saas.purge_audit
    FOR EACH ROW EXECUTE FUNCTION saas.purge_audit_immutable();
```

service 側兩處寫入：`api/services/gdpr_forget_service.py:336-340`（`phase="soft_delete_t0"`）與 `:429-433`（`phase="hard_delete_t30"`）。

### 步驟 6 — 記憶（`agent.*`）涵蓋範圍

agent 記憶 schema 於 `SQL/migrations/033-agent-memory-schema.sql:14`、`:20`、`:47`：

```
14:CREATE SCHEMA IF NOT EXISTS agent;
20:CREATE TABLE IF NOT EXISTS agent.memory_entry (
47:CREATE TABLE IF NOT EXISTS agent.escalation (
```

在 `api/` 全樹搜尋該表名：

```
git grep -rn "memory_entry" -- api
（無輸出，exit=1）
```

`api/services/gdpr_forget_service.py` 與 `api/realtime/gdpr_hard_delete_cron.py` 兩檔對 `agent.` 亦零命中：

```
git grep -n "agent\." -- api/services/gdpr_forget_service.py api/realtime/gdpr_hard_delete_cron.py
（無輸出，exit=1）
```

agent 側自有一份記憶存取實作（`agent/lockcore/agent/user_memory/postgres_store.py`、`store.py`），未見由 forget 流程觸發的刪除入口。

TC 判定基準寫「記憶（agent.*）與營運資料同步涵蓋」／程式碼的 forget 流程只操作 `users`、`saas.forget_request`、`saas.data_encryption_key`、`saas.purge_audit` 四處。此處僅並陳，不裁定。

### 步驟 7 — 前端呼叫端

`web/brand-portal/src/app/admin/gdpr-forget-queue/page.tsx` 為後台佇列頁；`web/brand-portal/src/components/phase-ii/api-client.ts` 內含 GDPR forget 端點的呼叫封裝（`git grep -l gdpr -- web/brand-portal/src` 命中此二檔與 `labels.ts`、`types.ts`）。

---

## 既有測試證據

環境：本機 Docker 測試庫（`postgresql://lock:0000@localhost:5433/lock_scratch_test`），Windows 上加掛 `-p winloop_plugin`（該 plugin 位於 scratchpad，不在 repo 內）。

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_gdpr_forget.py tests/test_cr_0164_gdpr_forget.py \
  tests/test_gdpr_hard_delete_cron.py -p winloop_plugin -q
2 failed, 23 passed in 1.31s
```

兩項失敗為：

```
FAILED tests/test_gdpr_forget.py::test_soft_delete_sets_eligibility_30_days
FAILED tests/test_gdpr_forget.py::test_hard_delete_cooldown_passed_happy
```

失敗原因為該兩測試的 `FakeConn` 依序排入 4 個假 cursor（`api/tests/test_gdpr_forget.py:213-233`），而現行 `soft_delete` 於該序列外另發出 legal-hold 查詢（`gdpr_forget_service.py:74-78`）、DEK 銷毀與 purge_audit 寫入（`:312`、`:336-340`），假 cursor 用罄後 `_get_request` 取不到列而拋 `NOT_FOUND`。本次走查未修改任何 repo 內程式碼或測試。

cron 測試 `api/tests/test_gdpr_hard_delete_cron.py:60`、`:96`、`:127` 三處皆以

```python
    async def fake_hard_delete(*, request_id, actor_user_id):
```

取代真實 `gdpr_forget_service.hard_delete`，故該測試的通過與否不涵蓋步驟 4 所述的簽名差異。

---

## 事實結論

1. 兩階段狀態機（`received → soft_deleted → hard_deleted`）在 service 與 DB CHECK 兩層皆存在（`gdpr_forget_service.py:242-434`、`SQL/migrations/021-gdpr-forget-requests.sql:26-33`）。
2. T0 軟刪同時做明文覆寫（`:296-304`）、密文欄清空（`:289-295`）與 DEK 銷毀（`:311-312`）。
3. 30 天 cooldown 由常數（`:30`）+ 寫入 `hard_delete_eligible_at`（`:276-278`）+ 硬刪前比對（`:369-375`）三處共同構成。
4. ledger append 有兩條並行鏈：泛用 `audit_events`（`:33-48`）與專用 `saas.purge_audit`（`:51-69`），後者有 DB 層 append-only trigger（`SQL/migrations/113-purge-audit-ledger.sql:44-51`）。
5. cron 存在且有分散式鎖與批次（`gdpr_hard_delete_cron.py:77`、`:102-110`）；其對 `hard_delete` 的呼叫未傳必填的 `tenant_id`（`:118-121` vs `gdpr_forget_service.py:344-346`）。
6. `agent.memory_entry` 在 `api/` 全樹零命中；forget 流程未觸及 agent 記憶表。
7. 硬刪遇 FK 阻擋時保留匿名化列並將 `physical_deleted=False` 記入 audit 與 purge_audit（`:397-407`、`:426-433`）。
