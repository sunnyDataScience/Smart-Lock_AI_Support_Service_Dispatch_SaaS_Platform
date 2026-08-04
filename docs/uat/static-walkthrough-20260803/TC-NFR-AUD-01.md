# TC-NFR-AUD-01 — 稽核可還原、竄改被驗出、匯出受控

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補本機測試庫實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / failure |

判定理由（事實）：TC 判定基準列的五個可還原維度中，**actor**（`audit_events.actor_id` / `actor_role`）、**原因**（`payload`）、**hash**（`prev_hash` / `entry_hash`）三項有落點；**版本**與 **trace** 在 `audit_events` 無對應欄位——`trace_id` 於 `api/services/audit_log_service.py` 與 `SQL/Schema_v2_extensions.sql` 皆零命中（步驟 3），版本資訊只存在於另一張表 `saas.ai_decision_trace.agent_version`，而該表在 `agent/` 全樹無任何寫入呼叫（步驟 6）。「竄改被驗出」有兩層落點（DB trigger + `verify_audit_chain`）。「匯出受權限控制」有落點；「受 tenant 控制」在資料面無對應——`audit_events` 表無 `tenant_id` 欄，`api/services/audit_log_service.py:8` 自述「本期不做 tenant 過濾」（步驟 5）；「受遮罩控制」由寫入時的 `scrub_audit_payload` 提供，匯出端無二次遮罩。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | audit/trace、敏感 mutation 與匯出 fixture |
| 步驟 | 送成功與拒絕 mutation、LLM/transfer、手動竄改／刪除與匯出 |
| 預期結果（判定基準） | actor、原因、版本、trace 與 hash 可還原；竄改被驗出；匯出受權限、tenant 與遮罩控制 |
| 路徑類型 | failure |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | NFR-Aud-002、NFR-Aud-003、NFR-Aud-005、NFR-Aud-006、NFR-Aud-007 |
| 屬於哪條旅程腳本 | — |

需求原文（`smartlock-docs/enterprise/05_NFR.md:160-166`）：

```
| NFR-Aud-001 | 全變更 audit log | append-only、JSON + trace_id、retention eternal；`audit_events` hash chain 完整性可驗證 | hash chain 驗證 job | 合約下限 |
| NFR-Aud-002 | 7 帳本 | borrow = lend；更正一律 reversal entry；reason code 制 | 帳本對帳測試 | 合約下限 |
| NFR-Aud-003 | Evidence retention | 1y / RMA+3y / eternal / GDPR ≤ 7d | retention 稽核 | 合約下限 |
| NFR-Aud-005 | AI 決策可追溯 | `saas.ai_decision_trace` 全量記錄；`transfer_event.rule_triggered_by` 由 deterministic engine 寫入 | trace 抽樣稽核 | 營運目標 |
| NFR-Aud-006 | Config change audit | 100% 記錄 who / when / what diff / why；retention ≥ 7y | audit log API + cron retention check | 營運目標 |
| NFR-Aud-007 | Read-side access log | 稽核員唯讀存取入同一 audit stream；flagged item full deny + log | access log 稽核 | 營運目標 |
```

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| actor 可還原 | `SQL/Schema_v2_extensions.sql:243-244`（`actor_id` / `actor_role`） | 有落點 |
| 原因可還原 | `SQL/Schema_v2_extensions.sql:248`（`payload` JSONB） | 有落點 |
| 版本可還原（audit_events） | — | **無對應**（無版本欄，步驟 3） |
| 版本可還原（ai_decision_trace） | `SQL/migrations/022-ai-decision-trace.sql:46` | 表有欄位；無寫入端（步驟 6） |
| trace 可還原 | — | **無對應**（`trace_id` 零命中，步驟 3） |
| hash 可還原 | `api/services/audit_log_service.py:47-92`、`SQL/migrations/067-audit-hash-chain.sql:8-9` | 有落點 |
| 竄改被驗出（DB 層） | `SQL/migrations/100-audit-events-append-only.sql:21-31` | 有落點 |
| 竄改被驗出（驗證函式） | `api/services/audit_log_service.py:152-204` | 有落點 |
| 驗證有 API 入口 | `api/routers/audit_v2.py:78-105` | 有落點 |
| 拒絕的 mutation 也留痕 | `api/services/gdpr_forget_service.py:266-269` 等 | 有落點（範例） |
| 匯出受權限控制 | `api/routers/audit_v2.py:178-198` | 有落點 |
| 匯出受 tenant 控制 | `api/routers/audit_v2.py:184-190`（path guard） | 路由層有；資料層無（步驟 5） |
| 匯出受遮罩控制 | `api/services/audit_log_service.py:81-83`（寫入時） | 寫入端有；匯出端無二次遮罩 |
| 匯出動作本身入稽核 | `api/routers/audit_v2.py:210-224` | 有落點 |
| Read-side access log（NFR-Aud-007） | — | **無對應**（步驟 8） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 後台使用者 | 敏感 mutation 成功 | `AuditAppended(hash)` | append-only + hash chain | `api/services/audit_log_service.py:476-524` | advisory lock → 算 prev/entry hash → INSERT |
| 後台使用者 | 敏感 mutation 被拒 | `AuditAppended(blocked)` | 拒絕也留痕 | `api/services/gdpr_forget_service.py:266-269` | 先寫 audit 再拋錯 |
| DBA | UPDATE / DELETE audit_events | `MutationBlocked` | 物理 append-only | `SQL/migrations/100-audit-events-append-only.sql:21-31` | trigger `RAISE EXCEPTION` |
| 稽核員 | 呼 `audit/verify` | `ChainVerified(valid/breaks)` | 偵測內容改動與斷鏈 | `api/services/audit_log_service.py:186-204` | 重算 entry_hash 並比對 expected_prev，回所有斷點 |
| admin | 建 re-baseline checkpoint | `CheckpointCreated` | 歷史凍結 | `api/services/audit_log_service.py:116-149` | 於 lock 內快照鏈末 |
| admin / ops | 匯出 audit | `ExportRequested` + `ExportStreamed` | 角色 + path tenant guard | `api/routers/audit_v2.py:184-198`、`:210-224` | 403 非 admin/ops；先寫 `audit.export.requested` 再串流 |
| 稽核員 | 唯讀查閱 | `ReadAccessLogged` | NFR-Aud-007 | — | **找不到**：list/get 端點無 log_event 呼叫 |
| agent | LLM 決策 / transfer | `AiDecisionTraced` | NFR-Aud-005 全量記錄 | — | **找不到**：`log_decision` 於 `agent/` 零命中 |

---

## 逐層走查

### 步驟 1 — DB schema 層：`audit_events` 欄位全表

`SQL/Schema_v2_extensions.sql:240-254`：

```sql
CREATE TABLE IF NOT EXISTS audit_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type          VARCHAR(50) NOT NULL,               -- 'conversation', 'tool_invocation', 'safety_gate',
                                                            -- 'escalation', 'dispatch_decision', 'financial_action', 'admin_action'
    actor_id            UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_role          VARCHAR(50),                        -- actor's role at time of event
    action              VARCHAR(100) NOT NULL,              -- specific action: 'create_refund', 'approve_dispatch', etc.
    target_type         VARCHAR(100),                       -- 'work_order', 'refund_request', 'user', etc.
    target_id           UUID,                               -- ID of the affected entity
    payload             JSONB,                              -- event-specific data (PII should be masked)
    ip_address          VARCHAR(45),
    retention_days      INTEGER NOT NULL DEFAULT 90,        -- auto-calculated from event_type
    expires_at          TIMESTAMP WITH TIME ZONE,           -- computed: created_at + retention_days
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

`SQL/migrations/067-audit-hash-chain.sql:8-9` 另加兩欄：

```sql
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS entry_hash TEXT;
```

全表 14 欄，無 `tenant_id`、無 `trace_id`、無版本欄。

### 步驟 2 — service 層：hash chain 計算與寫入

`api/services/audit_log_service.py:27-36`：

```python
# ── TI-AUDIT-03：append-only sha256 hash chain（合規紅線）────────────────────
# entry_hash = sha256(prev_hash + "|" + 正規化內容)；prev_hash 接前一列 entry_hash。
# 竄改任一列內容 → 其 entry_hash 對不上 → verify_audit_chain 偵測得到。
_AUDIT_GENESIS = "GENESIS"

# CR-0166 R1-5：hash-chain prev_hash 讀寫並發競態——兩筆同時讀同一 prev_hash
# → 鏈分叉，verify 誤報。全域 advisory xact-lock 序列化「讀末 hash → INSERT」臨界區。
```

正規化與雜湊 `api/services/audit_log_service.py:47-61`：

```python
def _canonical_audit_content(
    event_type: str | None, actor_id: str | None, actor_role: str | None,
    action: str | None, target_type: str | None, target_id: str | None,
    payload_json: str | None,
) -> str:
    """內容正規化為穩定字串（hash 輸入）。None → 空字串；payload 已是序列化 JSON 文字。"""
    parts = [
        event_type or "", actor_id or "", actor_role or "", action or "",
        target_type or "", target_id or "", payload_json or "",
    ]
    return "\x1f".join(str(p) for p in parts)  # 0x1f unit separator 避免欄位邊界混淆


def _compute_entry_hash(prev_hash: str, content: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{content}".encode("utf-8")).hexdigest()
```

hash 輸入為 7 個欄位；`ip_address`、`created_at`、`retention_days` 不入 hash。

寫入路徑 `api/services/audit_log_service.py:501-522`：

```python
    try:
        # CR-0166 R1-5：advisory lock 序列化讀末 hash → INSERT（防鏈分叉並發競態）
        async with db_module._conn.transaction():
            await _acquire_chain_lock()
            prev_hash, entry_hash, payload_json = await _chain_fields(
                event_type, actor_id, actor_role, action, target_type, target_id, payload
            )
            await db_module._conn.execute(
                sql,
                [ ... prev_hash, entry_hash, ],
            )
    except Exception as exc:  # noqa: BLE001 — pragma: no cover; best-effort logging, must not fail caller
        logger.warning("audit log_event failed: %s", exc)
```

`log_event` 吞例外（`:523-524`），另一版本 `log_event_returning_id`（`:527-575`）不吞、拋給呼叫端。

### 步驟 3 — trace 與版本欄位

在 audit service 與 schema 中搜尋 `trace_id`：

```
git grep -n "trace_id" -- api/services/audit_log_service.py SQL/Schema_v2_extensions.sql
（無輸出，exit=1）
```

NFR-Aud-001 原文（`smartlock-docs/enterprise/05_NFR.md:160`）寫「append-only、JSON + trace_id、retention eternal」／`audit_events` 表無 `trace_id` 欄位，`_canonical_audit_content` 的 7 個入 hash 欄位亦不含 trace。此處僅並陳，不裁定。

版本資訊在另一張表：`SQL/migrations/022-ai-decision-trace.sql:46`：

```sql
  agent_version       text        NULL,  -- 'gemini-1.5-pro-002' / 'gpt-4o'
```

### 步驟 4 — 竄改偵測：DB trigger 與驗證函式

`SQL/migrations/100-audit-events-append-only.sql:1-31`：

```sql
-- 100-audit-events-append-only.sql
-- CR-0164 A：audit_events 主稽核表補 append-only 物理保護（NFR-Aud-001 合約下限）。
--
-- Root cause：audit_events（承載 financial/dispatch/security 事件）宣稱 append-only
-- （067-audit-hash-chain 加 prev_hash/entry_hash），但從未於 DB 層強制——實查
-- pg_trigger=0，UPDATE/DELETE 可無痕竄改。
...
CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only (NFR-Aud-001/CR-0164); use session_replication_role=replica for privileged purge';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events;
CREATE TRIGGER trg_audit_events_append_only
  BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
```

該 migration 檔頭 `:14-19` 說明特權繞過路徑：`session_replication_role='replica'`（ORIGIN 觸發器在該模式下不觸發），並自述「目前 audit 無 purge job、實質 eternal」。

驗證函式 `api/services/audit_log_service.py:186-204`：

```python
    for r in rows:
        checked += 1
        payload_json = json.dumps(r[7], ensure_ascii=False, sort_keys=True) if r[7] is not None else None
        content = _canonical_audit_content(
            r[1], str(r[2]) if r[2] else None, r[3], r[4], r[5],
            str(r[6]) if r[6] else None, payload_json,
        )
        recomputed = _compute_entry_hash(r[8] or _AUDIT_GENESIS, content)
        if recomputed != r[9] or (r[8] or _AUDIT_GENESIS) != expected_prev:
            breaks.append(str(r[0]))
        # resync：以本列 entry_hash 為後續 expected_prev（斷後續驗，找出所有斷點）
        expected_prev = r[9]
    return {
        "checked": checked,
        "valid": len(breaks) == 0,
        "broken_at": breaks[0] if breaks else None,
        "breaks": breaks,
        "checkpoint": checkpoint,
    }
```

兩類竄改的偵測條件寫在 docstring（`:156-157`）：「(1) 列內容被改 → entry_hash 重算不符；(2) 列被刪/插/分叉 → prev_hash 不接前一列」。

API 入口 `api/routers/audit_v2.py:78-105`：

```python
@router.get(
    "/tenants/{tenantId}/audit/verify",
    operation_id="verifyAuditChainV2",
    summary="稽核 hash-chain 完整性驗證（NFR-Aud-001；偵測竄改/斷鏈）",
)
async def verify_audit_chain_v2(
    tenantId: str = Path(...),
    limit: int = Query(default=1000, ge=1, le=10000),
    use_checkpoint: bool = Query(default=True, description="CR-0184：有 checkpoint 時只驗基準之後；False 驗全鏈"),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    """CR-0164 A：把既有 audit_log_service.verify_audit_chain 接上 API（原為死機制）。

    audit_events 為部署層級事件（無 tenant_id），鏈為全域——tenant path 僅供
    授權對齊（admin gate + ADR-0030 cross-tenant guard）；驗的是整條部署鏈。
```

re-baseline checkpoint 端點在 `api/routers/audit_v2.py:111` 起（`createAuditChainCheckpointV2`），service 於 `api/services/audit_log_service.py:116-149`；其 docstring（`:120-121`）記錄「用於在歷史斷鏈下重建往後可驗證的乾淨鏈」。

### 步驟 5 — 匯出路徑：權限、tenant、遮罩

`api/routers/audit_v2.py:178-198`：

```python
async def export_audit_events_v2(
    ...
    # cross-tenant guard
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # Authorization: only admin / ops roles may export.
    if user.role not in {"admin", "ops"}:
        raise ApiError(
            error_code="FORBIDDEN",
            message="audit.read.all permission required to export audit events",
            status_code=403,
        )
```

匯出動作本身入稽核，`api/routers/audit_v2.py:210-224`：

```python
    await audit_log_service.log_event(
        event_type="admin_action",
        actor_id=user.user_id,
        actor_role=user.role,
        action="audit.export.requested",
        target_type="audit_events",
        target_id=None,
        payload={
            "filters": body.model_dump(mode="json", by_alias=True),
            "estimated_rows": total,
            "format": body.format,
            "tenant_id": tenantId,
        },
        ip_address=client_ip,
    )
```

實際串流的資料過濾條件在 `api/services/audit_log_service.py:342-376`（`_build_export_filters`），可用的 WHERE 條件為 `event_type` / `created_at` 區間 / `actor_id` / `target_type`——不含 tenant：

```python
    if event_types:
        placeholders = ", ".join(["%s"] * len(event_types))
        where.append(f"event_type IN ({placeholders})")
        args.extend(event_types)
    if from_:
        where.append("created_at >= %s")
    ...
    if actor_id:
        where.append("actor_id = %s::uuid")
    if resource_type:
        where.append("target_type = %s")
```

檔頭 `api/services/audit_log_service.py:8` 自述：

```
audit_events 沒有 tenant_id，本期不做 tenant 過濾（audit 為部署層級事件）。
```

TC 判定基準寫「匯出受權限、tenant 與遮罩控制」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:432`）／程式碼在路由層以 path tenantId 對比 JWT tenant（`audit_v2.py:184-190`），但被串流的列不帶 tenant 條件，`audit_events` 表亦無該欄。此處僅並陳，不裁定。

遮罩發生在寫入端，`api/services/audit_log_service.py:78-84`：

```python
    # CR-0166 R1-8：payload 自由文字欄（reason/notes/email 等）入庫＋入 hash 前先
    # 遮蔽高置信 PII（email/電話/身分證/LINE uid，不含地址啟發式以保稽核證據力）。
    # 在 json.dumps 與 hash 之前——hash 鏈事後不可改。
    if payload:
        from core.pii_scrub import scrub_audit_payload
        payload = scrub_audit_payload(payload)
```

`scrub_audit_payload` 在匯出路徑（`stream_audit_events`，`:404-473`）零命中，即匯出直接輸出入庫時已遮蔽的 payload，無二次處理。

匯出上限 `api/services/audit_log_service.py:324`：

```python
SYNC_EXPORT_THRESHOLD = 100_000
```

超過時回 `job_id` stub（`audit_v2.py:227-232`）；`api/services/audit_log_service.py:321-323` 註解自述非同步路徑尚未實作。

### 步驟 6 — AI 決策 trace（NFR-Aud-005）

`saas.ai_decision_trace` 表定義於 `SQL/migrations/022-ai-decision-trace.sql:13-48`，含三軸溯源欄（`prd_source` / `charter_rule` / `owner_decision_ref`）與 `agent_version`、`agent_session_id`。

寫入函式 `api/services/ai_governance_trace_service.py:32-88`（`log_decision`），HTTP 入口 `api/routers/ai_governance_trace_v2.py:48-66`，其檔頭 `:3` 自述「寫 trace row（agent runtime 呼）」。

搜尋呼叫端：

```
git grep -rn "log_decision\|ai_decision_trace\|ai-governance" -- agent api/routers
api/routers/ai_governance_trace_v2.py:3:1. POST /tenants/{tid}/ai-governance/traces           寫 trace row（agent runtime 呼）
api/routers/ai_governance_trace_v2.py:4:2. GET  /tenants/{tid}/ai-governance/traces           列 trace (多 filter)
api/routers/ai_governance_trace_v2.py:5:3. GET  /tenants/{tid}/ai-governance/traces/summary   聚合 summary 給 dashboard
api/routers/ai_governance_trace_v2.py:48:    "/tenants/{tenantId}/ai-governance/traces",
api/routers/ai_governance_trace_v2.py:60:    result = await svc.log_decision(
api/routers/ai_governance_trace_v2.py:68:    "/tenants/{tenantId}/ai-governance/traces",
api/routers/ai_governance_trace_v2.py:99:    "/tenants/{tenantId}/ai-governance/traces/summary",
```

`agent/` 全樹零命中。

NFR-Aud-005 另指名 `transfer_event.rule_triggered_by`：

```
git grep -rn "rule_triggered_by" -- api agent SQL
（無輸出，exit=1）
```

agent 側的轉真人紀錄落在另一張表，`agent/lockcore/agent/user_memory/escalation.py:47`、`:73`：

```
47:            CREATE TABLE IF NOT EXISTS escalation(
73:            "INSERT INTO escalation(tenant,user_id,reason,is_explicit,facts_snapshot,created_at)"
```

`is_explicit` 由確定性關鍵字比對決定（`agent/lockcore/agent/tools/transfer.py:56-59`）：

```python
def _is_explicit_transfer_request(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in TRANSFER_KEYWORDS)
```

`TRANSFER_KEYWORDS` 為 32 個字面關鍵字（`transfer.py:28-38`）。

TC 步驟寫「送成功與拒絕 mutation、LLM/transfer…版本、trace 可還原」（出處：`20_Test_Cases.md:432`）／程式碼中 LLM/transfer 的紀錄落在 agent 側 `escalation` 表（欄位為 tenant/user_id/reason/is_explicit/facts_snapshot/created_at），無 `agent_version`、無 trace id、不入 `audit_events` hash chain，也不寫 `saas.ai_decision_trace`。此處僅並陳，不裁定。

### 步驟 7 — Config change audit（NFR-Aud-006）

`SQL/migrations/004-config-m18.sql:100-122`：

```sql
CREATE TABLE IF NOT EXISTS saas.config_audit (
  id                bigserial PRIMARY KEY,
  tenant_id         uuid,
  config_version_id uuid NOT NULL REFERENCES saas.config_version(id),
  actor_user_id     uuid NOT NULL,
  action            text NOT NULL CHECK (action IN
                        ('draft_created','rollout_started','stage_advanced',
                         'rolled_back','activated','retired')),
  diff              jsonb,
  ts                timestamptz NOT NULL DEFAULT now()
);
...
CREATE TRIGGER config_audit_no_update
  BEFORE UPDATE ON saas.config_audit
  FOR EACH ROW EXECUTE FUNCTION saas.tg_block_mutation();
```

who（`actor_user_id`）／when（`ts`）／what diff（`diff`）三項有欄位；NFR-Aud-006 原文另要求 why——該表無 reason／why 欄位。

### 步驟 8 — Read-side access log（NFR-Aud-007）

`api/routers/audit_v2.py:47-76`（`list_audit_events_v2`）與 `api/routers/audit_logs.py:45-72`（`list_audit_logs`）皆只做角色守衛與查詢，無 `log_event` 呼叫。匯出端點（`audit_v2.py:210`）為唯一寫回稽核的讀取類動作。

搜尋讀取型稽核的識別碼：

```
git grep -rn "access_log\|read_access\|event_type=\"read\"" -- api --include=*.py | grep -v tests
（無輸出，exit=1）
```

NFR-Aud-007 原文（`05_NFR.md:166`）寫「稽核員唯讀存取入同一 audit stream；flagged item full deny + log」／程式碼中除匯出外的讀取端點未寫入 audit stream，`flagged` 相關識別碼在 api 樹零命中。此處僅並陳，不裁定。

### 步驟 9 — 7 帳本與 reversal（NFR-Aud-002）

`reversal` 在 repo 的命中：

```
git grep -rln "reversal" -- api/services SQL
SQL/migrations/010-vouchers-void.sql
api/services/voucher_void_service.py
```

即 reversal entry 機制存在於折價券作廢一處。NFR-Aud-002 涵蓋的 7 帳本對帳測試不在本 TC 的判定基準文字內（判定基準只列 actor／原因／版本／trace／hash／竄改／匯出），本步驟僅記錄搜尋事實。`smartlock-docs/enterprise/20_Test_Cases.md:194` 對 NFR-Aud-002 的既有標記為「⚠ 完全沒有案例」。

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0166_pii_scrub.py tests/test_observability_pii_scrub.py \
  tests/test_cr_0068_audit_hash_chain.py tests/test_cr_0164_audit_immutable.py \
  tests/test_cr_0184_audit_checkpoint.py tests/test_audit_v2_endpoint.py \
  -p winloop_plugin -q
34 passed in 6.03s
```

覆蓋對應：

- hash chain 計算與 verify：`api/tests/test_cr_0068_audit_hash_chain.py`
- DB 層 append-only：`api/tests/test_cr_0164_audit_immutable.py`
- re-baseline checkpoint：`api/tests/test_cr_0184_audit_checkpoint.py`
- 匯出端點：`api/tests/test_audit_v2_endpoint.py`
- payload 遮罩：`api/tests/test_cr_0166_pii_scrub.py:31-42`（`test_audit_payload_recursive`）

`api/tests/` 中無測試檔涵蓋 `saas.ai_decision_trace` 的 agent 端寫入、`trace_id` 還原，或 read-side access log。

---

## 事實結論

1. `audit_events` 14 欄，含 actor（`actor_id`/`actor_role`）、原因（`payload`）、`prev_hash`/`entry_hash`；不含 `tenant_id`、`trace_id` 與版本欄。
2. hash 輸入為 7 個欄位（`_canonical_audit_content`，`audit_log_service.py:53-57`），以 `\x1f` 分隔；`ip_address` 與時間不入 hash。
3. 竄改偵測有兩層：DB trigger（`100-audit-events-append-only.sql:28-31`，特權繞過路徑為 `session_replication_role='replica'`）與 `verify_audit_chain`（回報所有斷點）。
4. `verify` 與 `checkpoint` 皆有 v2 API 端點，守衛為 `role_required(*FULL_ACCESS_ROLES)` + path tenant guard。
5. 匯出需 `user.role in {"admin","ops"}`，並先寫一筆 `audit.export.requested`；串流的 WHERE 條件不含 tenant。
6. PII 遮罩發生在寫入端（入 hash 之前），匯出端無二次遮罩。
7. `saas.ai_decision_trace` 表與其 API 均存在，`agent/` 全樹無呼叫；`rule_triggered_by` 在 api/agent/SQL 三處皆零命中。
8. agent 的轉真人紀錄寫入獨立的 `escalation` 表，`is_explicit` 由 32 個字面關鍵字的確定性比對決定。
9. `saas.config_audit` 有 who/when/diff 與 append-only trigger，無 why 欄位。
10. 除匯出端點外，稽核讀取端點不寫入 audit stream。
