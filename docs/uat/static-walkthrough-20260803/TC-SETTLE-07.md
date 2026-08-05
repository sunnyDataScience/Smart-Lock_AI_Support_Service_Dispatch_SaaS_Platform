# TC-SETTLE-07 — 稽核 ledger append-only 與 hash chain 抽驗

> ## 🔄 判定更正（2026-08-05 回程式碼查證）
>
> **原判定「部分實作」→ 更正為「一致」。以下原文保留未改動。**
>
> 兩條判定基準（UPDATE/DELETE 遭拒、抽驗 hash 全數相符）在 `audit_events` 上都完整實作：`SQL/migrations/100-audit-events-append-only.sql:18-27` 為 BEFORE UPDATE OR DELETE 無條件 RAISE；`api/services/audit_log_service.py:60-61` 的 `sha256(f"{prev_hash}|{content}")` 正是 TC 寫的前綴形式；`:152-204` 的 `verify_audit_chain` 提供抽 N 筆驗證，`api/routers/audit_v2.py:79-104` 已接上 API。
> 本文件判部分實作的唯一理由是**欄位名**（實作 `entry_hash`/`prev_hash` vs TC 寫的 `hash_self`/`hash_prev`）——屬命名差異，非缺口。
> （查證期間另發現 `api/openapi.yaml` 的 `hash_self` 描述把演算法寫錯（`sha256(hash_prev + serialize(row))`，實際 hash_prev 在最後），已於 commit `fddbbffe` 勘誤。）
>
> 更正依據：對本文件引用的每個 `檔案:行號` 逐一開檔覆核、對宣稱「零命中」的識別碼
> 以多種命名寫法重跑 grep。走查基準 commit 與查證當下 HEAD 之間，
> `api/` `agent/` `web/` `SQL/` 原始碼零差異，故原引用仍然有效。
>
> **此更正不需要改動任何 code。**

---

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑既有測試 50 項全過，另以 scratchpad 探針（**未寫入 repo**）實測 UPDATE/DELETE 遭拒與 100 筆 hash 抽驗（見「既有測試證據」） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試與探針實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `SQL/migrations/100-audit-events-append-only.sql:1-31`、`SQL/migrations/067-audit-hash-chain.sql:1-16`、`api/services/audit_log_service.py:28-92`、`:150-206`、`api/routers/audit_v2.py:79-104`、`SQL/migrations/010-vouchers-void.sql:33-34`、`:55-68`、`:94-100`、`api/services/voucher_void_service.py:68-92`、`:160-172`、`api/tests/conftest.py:229-243` |
| 優先級 / 路徑類型 | P0 / 例外 |

「append-only（UPDATE/DELETE 遭拒）」完全成立且已實測：`audit_events` 有 `BEFORE UPDATE OR DELETE` trigger 一律 `RAISE EXCEPTION`（`SQL/migrations/100-audit-events-append-only.sql:18-27`），本機測試庫實測兩者皆回「audit_events is append-only (NFR-Aud-001/CR-0164)」。「抽 100 筆驗 hash 全數相符」亦已實測：`verify_audit_chain(limit=100, use_checkpoint=False)` 回 `{'checked': 100, 'valid': True, 'broken_at': None}`、`breaks` 為空。判為部分實作的是欄位命名：TC 指名的 `hash_self` / `hash_prev` 在 `audit_events` 上不存在，該表用的是 `entry_hash` / `prev_hash`（`SQL/migrations/067-audit-hash-chain.sql:8-9`）；`hash_self` / `hash_prev` 是另一張表 `saas.voucher` 的欄位（`SQL/migrations/010-vouchers-void.sql:33-34`），而該表的雜湊組成把 `hash_prev` 放在**末位**而非前綴（`api/services/voucher_void_service.py:76-90`），與 TC 寫的 `sha256(hash_prev + content)` 順序不同；`audit_events` 的組成則是前綴形式（`api/services/audit_log_service.py:60-61`）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 7. 結算與退款案例（TC-SETTLE） |
| 前置 | 憑證/審計 ledger |
| 步驟 | 直接 UPDATE/DELETE audit 列 + 抽 100 筆驗 hash |
| 預期結果（判定基準） | 遭拒（append-only）；hash_self = sha256(hash_prev + content) 全數相符 |
| 路徑類型 | 例外 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-API-12、FR-DAT-06、FR-WEB-05、NFR-Aud-001 |
| 屬於哪條旅程腳本 | SC-11、SC-18、SC-19 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 直接 UPDATE audit 列 → 遭拒 | `SQL/migrations/100-audit-events-append-only.sql:18-27`；探針實測回 exception | 有落點（已實測） |
| 直接 DELETE audit 列 → 遭拒 | 同上（trigger 為 `BEFORE UPDATE OR DELETE`） | 有落點（已實測） |
| 拒絕訊息 | `100-audit-events-append-only.sql:20` `'audit_events is append-only (NFR-Aud-001/CR-0164); ...'` | 有落點 |
| 欄位名 `hash_self` | `audit_events` 無此欄；`SQL/migrations/067-audit-hash-chain.sql:9` 為 `entry_hash` | 名稱不同 |
| 欄位名 `hash_prev` | `audit_events` 無此欄；`067-audit-hash-chain.sql:8` 為 `prev_hash` | 名稱不同 |
| `hash_self` 存在於他表 | `SQL/migrations/010-vouchers-void.sql:33-34`（`saas.voucher.hash_prev` / `hash_self`） | 有落點（不同表） |
| `sha256(hash_prev + content)` 前綴組成 | `api/services/audit_log_service.py:60-61` `sha256(f"{prev_hash}|{content}")` | 有落點（`audit_events`） |
| `saas.voucher` 的組成順序 | `api/services/voucher_void_service.py:78-90`：`sha256(voucher_no\|amount\|debit\|credit\|reverses_voucher_id\|hash_prev)` | 順序不同（`hash_prev` 在末位） |
| 抽 N 筆驗 hash 的機制 | `api/services/audit_log_service.py:150-206` `verify_audit_chain(limit=...)` | 有落點 |
| 對外驗證入口 | `api/routers/audit_v2.py:79-104` `GET /tenants/{tenantId}/audit/verify` | 有落點（`FULL_ACCESS_ROLES`） |
| 100 筆全數相符 | 探針實測 `{'checked': 100, 'valid': True, 'broken_at': None}` | 已實測 |
| 特權繞過路徑 | `100-audit-events-append-only.sql:12-16`、`api/tests/conftest.py:229-243`（`session_replication_role='replica'`） | 有落點（設計上的例外） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 系統 | 寫稽核事件 | `AuditEventAppended` | 接鏈 | `api/services/audit_log_service.py:77-92` | 取鏈末 `entry_hash` 為 `prev_hash`，算 `entry_hash` 後 INSERT |
| 系統 | 序列化 payload | `PayloadScrubbed` | 入 hash 前遮 PII | `api/services/audit_log_service.py:79-83` | `scrub_audit_payload(payload)` 在 `json.dumps` 與 hash 之前 |
| DBA / 攻擊者 | `UPDATE audit_events` | `MutationBlocked` | append-only | `SQL/migrations/100-...sql:18-27` | `RAISE EXCEPTION 'audit_events is append-only ...'` |
| DBA / 攻擊者 | `DELETE FROM audit_events` | `MutationBlocked` | append-only | 同上 | 同上 |
| 具權者 | `SET session_replication_role='replica'` 後 DELETE | `PrivilegedPurgeAllowed` | 刻意保留 | `100-...sql:12-16`、`api/tests/conftest.py:238-242` | ORIGIN trigger 於 replica 模式不觸發 |
| admin | `GET /audit/verify?limit=100` | `ChainVerified` | 全鏈或基準後 | `api/routers/audit_v2.py:84-104` | 回 `{checked, valid, broken_at, breaks, checkpoint}` |
| 驗證器 | 重算每列 hash | `BreakDetected` | 兩類竄改 | `api/services/audit_log_service.py:186-196` | 內容改 → 重算不符；列被刪/插 → `prev_hash` 不接前一列 |
| admin | 建 re-baseline checkpoint | `ChainRebaselined` | 只驗基準後 | `api/services/audit_log_service.py:117-146`、`api/routers/audit_v2.py:107-113` | `use_checkpoint=True` 時歷史凍結不驗 |
| 記帳者 | 沖銷傳票 | `VoucherReversed` | 原傳票不改 | `api/services/voucher_void_service.py:160-212` | 建反向分錄，`hash_prev = 原 voucher.hash_self` |
| DBA | `UPDATE saas.voucher` | `MutationBlocked` | append-only | `SQL/migrations/010-vouchers-void.sql:55-68` | `tg_saas_voucher_block_mutation` |

---

## 逐層走查

### 第 1 層 — append-only 的 DB 層強制

`SQL/migrations/100-audit-events-append-only.sql:1-31`（全檔）

```sql
-- 100-audit-events-append-only.sql
-- CR-0164 A：audit_events 主稽核表補 append-only 物理保護（NFR-Aud-001 合約下限）。
--
-- Root cause：audit_events（承載 financial/dispatch/security 事件）宣稱 append-only
-- （067-audit-hash-chain 加 prev_hash/entry_hash），但從未於 DB 層強制——實查
-- pg_trigger=0，UPDATE/DELETE 可無痕竄改。對照 saas.config_audit(004)/
-- voucher_void_event(010)/pricing_rule_snapshot(098) 皆有 tg_block_mutation。
-- 唯獨主稽核表漏掉物理保護（UAT wave2 F11 live-confirmed）。
--
-- 修：BEFORE UPDATE OR DELETE trigger 一律 RAISE（owner 亦擋）。
--
-- 特權繞過（測試 / 未來 retention purge）：ORIGIN 觸發器在
-- session_replication_role='replica' 下不觸發（PostgreSQL 標準機制）。需 purge
-- 或測試注入時，於該 session 先 SET session_replication_role='replica'（限
-- superuser/具權者），操作後復原。CR-0164 §8-A3：目前 audit 無 purge job、
-- 實質 eternal；未來 retention 分級 purge 走此特權路徑。

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

本機測試庫的 trigger 現況：

```
docker exec smartlock-test-db psql -U lock -d lock_scratch_test -tAc \
  "SELECT tgname FROM pg_trigger WHERE tgrelid='audit_events'::regclass AND NOT tgisinternal;"
trg_audit_events_append_only
```

### 第 2 層 — hash chain 的欄位與組成

`SQL/migrations/067-audit-hash-chain.sql:8-15`

```sql
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS entry_hash TEXT;
COMMENT ON COLUMN audit_events.entry_hash IS
  'CR-0068/TI-AUDIT-03：sha256(prev_hash + 正規化內容)；篡改偵測用';
COMMENT ON COLUMN audit_events.prev_hash IS
  'CR-0068/TI-AUDIT-03：鏈接前一列 entry_hash（genesis = "GENESIS"）';
CREATE INDEX IF NOT EXISTS idx_audit_events_entry_hash
  ON audit_events (created_at, id) WHERE entry_hash IS NOT NULL;
```

`api/services/audit_log_service.py:28-30`

```python
# entry_hash = sha256(prev_hash + "|" + 正規化內容)；prev_hash 接前一列 entry_hash。
# 竄改任一列內容 → 其 entry_hash 對不上 → verify_audit_chain 偵測得到。
_AUDIT_GENESIS = "GENESIS"
```

`api/services/audit_log_service.py:60-71`

```python
def _compute_entry_hash(prev_hash: str, content: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{content}".encode("utf-8")).hexdigest()


async def _latest_entry_hash() -> str:
    """取最後一列 entry_hash 作 prev_hash；無鏈段 → GENESIS。"""
    cur = await db_module._conn.execute(
        "SELECT entry_hash FROM audit_events WHERE entry_hash IS NOT NULL "
        "ORDER BY created_at DESC, id DESC LIMIT 1"
    )
    row = await cur.fetchone()
    return row[0] if row and row[0] else _AUDIT_GENESIS
```

正規化內容以 `\x1f` unit separator 串接欄位（`api/services/audit_log_service.py:55-57`）：

```python
        target_type or "", target_id or "", payload_json or "",
    ]
    return "\x1f".join(str(p) for p in parts)  # 0x1f unit separator 避免欄位邊界混淆
```

- TC 判定基準寫「`hash_self` = sha256(`hash_prev` + content)」
- `audit_events` 上的欄位名為 `entry_hash` / `prev_hash`（`SQL/migrations/067-audit-hash-chain.sql:8-9`）；組成為 `sha256(prev_hash + "|" + content)`（`api/services/audit_log_service.py:61`），即前綴形式與 TC 描述相同，欄位名稱不同

此處僅並陳，不裁定。

### 第 3 層 — `hash_self` / `hash_prev` 的實際所在

`SQL/migrations/010-vouchers-void.sql:33-34`

```sql
    hash_prev            text,
    hash_self            text,
```

`SQL/migrations/010-vouchers-void.sql:55-68`

```sql
-- ── Step 4: append-only trigger（HD-VCH-002 / BR-AUDIT-007）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'tg_saas_voucher_block_mutation'
          AND tgrelid = 'saas.voucher'::regclass
    ) THEN
        CREATE TRIGGER tg_saas_voucher_block_mutation
            BEFORE UPDATE OR DELETE ON saas.voucher
            FOR EACH ROW EXECUTE FUNCTION saas.tg_block_mutation();
    END IF;
END $$;
```

`api/services/voucher_void_service.py:68-92`

```python
def _compute_hash_self(
    voucher_no: str,
    amount: str,
    debit_account: str | None,
    credit_account: str | None,
    reverses_voucher_id: str | None,
    hash_prev: str | None,
) -> str:
    """計算 hash_self（HD-VCH-001 hash chain V1）。

    格式：sha256(voucher_no|amount|debit|credit|reverses_voucher_id|hash_prev)
    各欄位若為 None 則用空字串。
    """
    parts = "|".join(
        [
            voucher_no or "",
            amount or "",
            debit_account or "",
            credit_account or "",
            reverses_voucher_id or "",
            hash_prev or "",
        ]
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()
```

`api/services/voucher_void_service.py:160-161`

```python
        # hash chain：hash_prev = 原 voucher.hash_self
        hash_prev = original["hash_self"]
```

- TC 寫的組成為 `sha256(hash_prev + content)`（`hash_prev` 在前）
- `saas.voucher` 的實作為 `sha256(content | hash_prev)`（`hash_prev` 在末位，`api/services/voucher_void_service.py:78`、`:83-89`）

此處僅並陳，不裁定。

本機測試庫的 `saas.voucher` 現況：

```
docker exec smartlock-test-db psql -U lock -d lock_scratch_test \
  -tAc "SELECT count(*) FROM saas.voucher;" \
  -tAc "SELECT tgname FROM pg_trigger WHERE tgrelid='saas.voucher'::regclass AND NOT tgisinternal;"
0
tg_saas_voucher_block_mutation
```

即 trigger 已在，但無資料列可供抽驗；本 TC 的 100 筆抽驗以 `audit_events` 為對象（見「既有測試證據」）。

### 第 4 層 — 抽驗機制

`api/services/audit_log_service.py:150-206`

```python
async def verify_audit_chain(*, limit: int = 1000, use_checkpoint: bool = True) -> dict:
    """驗證 audit hash chain 完整性（只驗有 entry_hash 的鏈段，依時序）。

    偵測兩類竄改：(1) 列內容被改 → entry_hash 重算不符；(2) 列被刪/插/分叉 →
    prev_hash 不接前一列。CR-0184 增強：
      - use_checkpoint（預設 True）：有 re-baseline checkpoint 時，只驗基準列「之後」
        的鏈段（expected_prev 從 baseline_entry_hash 起）；歷史凍結不驗。
      - 回報**所有**斷點（breaks 陣列），非只第一個；遇斷後 resync（以該列 entry_hash
        為新起點續驗）以找出後續斷點。broken_at 保留為第一個斷點（向下相容）。
    回 {checked, valid, broken_at, breaks:[...], checkpoint:{...}|None}。
    """
```

核心比對，`api/services/audit_log_service.py:184-196`：

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
```

### 第 5 層 — 對外驗證入口與前端

`api/routers/audit_v2.py:79-104`

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

前端方面，brand-portal 的稽核頁只呼叫事件列表端點，`web/brand-portal/src/app/admin/audit-events/page.tsx:152-154`：

```tsx
  // CR-0002-α：遷至 tenant-scoped v2 端點（GET /tenants/{tenantId}/audit/events）
  const auditEventsPath = `/tenants/${encodeURIComponent(tenantId)}/audit/events`;
```

`/audit/verify` 在 `web/` 中的命中只有型別產物 `web/shared-contract/src/api-generated.ts:3682`、`:3698`、`:22774`，無 UI 呼叫端。此為事實陳述，不涉判定。

---

## 既有測試證據

### 既有測試（本機 Docker 測試庫，Windows 加 `-p winloop_plugin`）

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0164_audit_immutable.py tests/test_cr_0068_audit_hash_chain.py \
  tests/test_audit_v2_endpoint.py tests/test_technician_statement.py \
  tests/test_dispatcher_commission.py -q -p winloop_plugin
50 passed in 3.67s
```

對到 TC 步驟前半的 `api/tests/test_cr_0164_audit_immutable.py:26-45`：

```python
async def test_trigger_blocks_update_and_delete():
    """一般 UPDATE/DELETE audit_events → append-only trigger RAISE。"""
    ...
        with pytest.raises(Exception) as ue:
            await db_module._conn.execute(
                "UPDATE audit_events SET action='hacked' WHERE id=%s::uuid", (eid,))
        assert "append-only" in str(ue.value).lower()
```

### 探針（**未寫入 repo**，置於 scratchpad）

以 `audit_events` 現有 109 列（其中 109 列有 `entry_hash`）實測 TC 的兩個步驟：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  <scratchpad>/test_settle07_probe.py -q -p winloop_plugin -s

SAMPLE_ROW_ID= fdb70e74-8087-4bfb-86e2-77d39e65751e
UPDATE_RESULT= audit_events is append-only (NFR-Aud-001/CR-0164); use session_replication_role=replica for privileged purge
DELETE_RESULT= audit_events is append-only (NFR-Aud-001/CR-0164); use session_replication_role=replica for privileged purge
VERIFY_100= {'checked': 100, 'valid': True, 'broken_at': None}
BREAKS_N= 0
1 passed
```

探針內容：對最新一列先後嘗試 `UPDATE ... SET action='tampered'` 與 `DELETE`，各自捕捉例外訊息並 `ROLLBACK`；再呼叫 `verify_audit_chain(limit=100, use_checkpoint=False)`。

---

## 事實結論

1. `audit_events` 具 `BEFORE UPDATE OR DELETE` 的 append-only trigger，函式體無條件 `RAISE EXCEPTION`（`SQL/migrations/100-audit-events-append-only.sql:18-27`）；本機測試庫 `pg_trigger` 查得 `trg_audit_events_append_only`。
2. 探針實測：`UPDATE` 與 `DELETE` 皆被拒，訊息為「audit_events is append-only (NFR-Aud-001/CR-0164); use session_replication_role=replica for privileged purge」。
3. 探針實測：`verify_audit_chain(limit=100, use_checkpoint=False)` 回 `checked=100`、`valid=True`、`broken_at=None`、`breaks` 為空。
4. TC 指名的欄位名 `hash_self` / `hash_prev` 在 `audit_events` 上不存在；該表用 `entry_hash` / `prev_hash`（`SQL/migrations/067-audit-hash-chain.sql:8-9`）。`hash_self` / `hash_prev` 為 `saas.voucher` 的欄位（`SQL/migrations/010-vouchers-void.sql:33-34`）。此處僅並陳，不裁定。
5. `audit_events` 的雜湊組成為 `sha256(prev_hash + "|" + 正規化內容)`（`api/services/audit_log_service.py:61`），與 TC 描述的前綴形式相同。
6. `saas.voucher` 的雜湊組成為 `sha256(voucher_no|amount|debit|credit|reverses_voucher_id|hash_prev)`，`hash_prev` 位於末位（`api/services/voucher_void_service.py:78`、`:83-89`），與 TC 描述的順序不同。此處僅並陳，不裁定。
7. `saas.voucher` 同樣具 append-only trigger（`SQL/migrations/010-vouchers-void.sql:55-68`），本機測試庫查得 `tg_saas_voucher_block_mutation`；該表目前 0 列，無資料可抽驗。
8. append-only 存在一條刻意保留的特權繞過：`SET session_replication_role='replica'`（`SQL/migrations/100-audit-events-append-only.sql:12-16`），測試以 `api/tests/conftest.py:229-243` 的 `audit_privileged_exec` 使用該路徑。
9. hash chain 驗證有兩種模式：`use_checkpoint=True`（預設，只驗 re-baseline checkpoint 之後）與 `False`（驗全鏈）；驗證回報所有斷點而非只第一個（`api/services/audit_log_service.py:157-161`、`:184-196`）。
10. 驗證端點 `GET /tenants/{tenantId}/audit/verify` 限 `FULL_ACCESS_ROLES`（`api/routers/audit_v2.py:88`），`limit` 上限 10000（`:86`）；`web/` 中無 UI 呼叫端，只有型別產物命中。
11. payload 在 `json.dumps` 與 hash 之前先做 PII 遮蔽（`api/services/audit_log_service.py:79-83`），註解自述「hash 鏈事後不可改」。
12. 既有測試 50 項於本機測試庫全數通過。
