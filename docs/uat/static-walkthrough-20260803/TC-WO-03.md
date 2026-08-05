# TC-WO-03 — 報價未經客戶確認時開工單

> ## 🔄 判定更正（2026-08-05 回程式碼查證）
>
> **原判定「部分實作」→ 更正為「一致」。以下原文保留未改動。**
>
> 兩條判定基準全數落地且有測試：非急件無「客戶已確認」報價 → 425 `QUOTE_NOT_CUSTOMER_CONFIRMED`、全數失效 → 409 `QUOTE_STATE_INVALID`（`api/services/quote_engine_service.py:162-188`）；急件 `pc.emergency_class` 非空整段跳過（`api/services/work_order_service.py:586-587`）並建 `retrospective_audit_only` 佔位報價＋audit `emergency_bypass`（:695-714）。
> `accepted` 就是「客戶確認」的落地態——transition 表 `"accept": ({"sent"}, "accepted")`（`quote_engine_service.py:35`），客戶側入口為 LIFF / LINE 的 `customer_respond_to_quote`。屬命名差異，非缺口。
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
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 5） |
| 走查時間 | 2026-08-03 17:14（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/work_order_service.py:581-587`、`:695-714`、`api/services/quote_engine_service.py:155-188`、`SQL/migrations/041-quote-engine.sql:15-32`、`api/tests/test_cr_0128_quote_gate.py` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 開單 gate 存在且以「最新報價須為 `accepted`」為條件，急件 `emergency_class` 非空即整段跳過並建 `retrospective_audit_only` 佔位報價；但 TC 寫的欄位 `quote.customer_confirmed` 在 schema 與程式碼中**找不到**，實作以 `quote.state = 'accepted'` 表達。 |

**TC 原文**｜前置：非急件、報價未經客戶確認｜步驟：建工單帶未確認 quote｜判定基準：拒絕（非急件需 quote.customer_confirmed；急件 emergency_class 例外放行）｜例外｜P0｜FR-API-01、FR-API-04｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | convert（非急件、報價進行中） | `ConvertRejected(425)` | 須客戶已確認報價 | `quote_engine_service.py:177-183` | 425 `QUOTE_NOT_CUSTOMER_CONFIRMED` |
| 客服 | convert（非急件、報價全數失效） | `ConvertRejected(409)` | 死報價不可開單 | `quote_engine_service.py:184-188` | 409 `QUOTE_STATE_INVALID` |
| 客服 | convert（非急件、報價 accepted） | `WorkOrderCreated` | gate 放行 | `work_order_service.py:586-587`、`:672-674` | 跳過 raise，開單後 `bind_quotes_to_work_order` |
| 客服 | convert（急件） | `WorkOrderCreated` + `EmergencyBypass` | `emergency_class` 非空即放行 | `work_order_service.py:586`、`:695-714` | 整段 gate 不呼叫；建 `retrospective_audit_only` 報價 + audit `emergency_bypass` |
| 系統 | 標記工單 | `QuoteGateApplied` | 新單一律標記 | `work_order_service.py:618`、`:622` | INSERT 時 `quote_gate_applied` 寫死 `TRUE` |

---

## 走查紀錄

### 步驟 1 — gate 的呼叫點與急件例外

- **動作**：讀 convert 主流程的 gate 段
- **預期**：非急件才檢查報價
- **實際**：一致

`api/services/work_order_service.py:581-587`

```python
    # 2.5 報價先行 gate（CR-0128 / ADR-015① / BR-WO-01「線上報價 → 客人確認 → 才開單派工」）：
    #     標準路徑須有客戶已確認（accepted）報價（無/進行中 → 425；全數失效 → 409）；
    #     急件 carve-out（pc.emergency_class 四類）跳過報價直接開單、事後補審（4h timer＝1.2.2）。
    from services import quote_engine_service as _qe

    if pc_emergency_class is None:
        await _qe.assert_pc_quote_confirmed(tenant_id=tenant_id, problem_card_id=pc_id)
```

`pc_emergency_class` 來自 PC 的 SELECT（`work_order_service.py:535`、解構於 `:550-552`）。

### 步驟 2 — gate 的判定條件與錯誤碼

- **動作**：讀 `assert_pc_quote_confirmed`
- **預期**：`quote.customer_confirmed` 為真才放行
- **實際**：以 `state == 'accepted'` 判定；**找不到** `customer_confirmed` 欄位

`api/services/quote_engine_service.py:162-188`

```python
async def assert_pc_quote_confirmed(*, tenant_id: str, problem_card_id: str) -> str:
    """開單 gate：問題卡須有客戶已確認（accepted）的報價，回傳該 quote id。

    - 無任何報價、或最新報價仍在進行中 → 425 QUOTE_NOT_CUSTOMER_CONFIRMED
    - 有報價但全數已死（rejected/expired/superseded）→ 409 QUOTE_STATE_INVALID
    """
    conn = await _conn()
    rows = await (await conn.execute(
        "SELECT id, state FROM quote WHERE problem_card_id = %s::uuid AND tenant_id = %s::uuid "
        "ORDER BY version DESC",
        (problem_card_id, tenant_id),
    )).fetchall()
    for r in rows:
        if r[1] == "accepted":
            return str(r[0])
    if not rows or any(r[1] in _GATE_PENDING_STATES for r in rows):
        raise ApiError(
            "QUOTE_NOT_CUSTOMER_CONFIRMED",
            "報價尚未經客戶確認——先開單派工前須完成線上報價與客戶確認（BR-WO-01）；"
            "急件請於問題卡標記 emergency_class 走事後補審",
            425,
        )
    raise ApiError(
        "QUOTE_STATE_INVALID",
        "問題卡的報價已失效（拒絕/過期/被取代）——請開新版本報價並取得客戶確認",
        409,
    )
```

「進行中」狀態集合：

`api/services/quote_engine_service.py:157-159`

```python
_GATE_PENDING_STATES = frozenset({"draft", "pending_approval", "approved", "sent",
                                  "retrospective_audit_only"})
```

- TC 判定基準寫「非急件需 `quote.customer_confirmed`」
- schema `SQL/migrations/041-quote-engine.sql:15-32` 的 `quote` 表欄位為 `state / total_amount / deposit_required / expiry_at / snapshot_hash / supersedes_quote_id / is_mock / tenant_id / created_by`，**無 `customer_confirmed` 欄位**
- 全 repo 搜 `customer_confirmed` 作為 quote 欄位：**找不到**

此處僅並陳，不裁定。

### 步驟 3 — 「拒絕」的具體回應碼

- **動作**：確認 TC 所稱「拒絕」對應的 HTTP 狀態
- **預期**：TC 未指定碼
- **實際**：依報價狀態分兩碼——425（進行中／無報價）與 409（全數失效）

上引 `quote_engine_service.py:177-188`。425 非 `core/errors.py:_CODE_MAP` 的預設對照碼（`api/core/errors.py:46-55` 僅列 400/401/403/404/409/422/429/500），由 `ApiError` 直接帶 status。

### 步驟 4 — 急件放行後的補償路徑

- **動作**：讀急件分支
- **預期**：例外放行
- **實際**：一致，且另建佔位報價與稽核事件

`api/services/work_order_service.py:695-714`

```python
    else:
        await _qe.create_quote(
            tenant_id=tenant_id, work_order_id=new_wo_id, created_by=created_by,
            urgent=True, initial_state="retrospective_audit_only")
        # 15_SDS §4.5 步驟1：急件跳過事前報價開單，audit 記 emergency_bypass（fail-soft）
        from services.audit_log_service import log_event
        await log_event(
            event_type="work_order",
            actor_id=created_by,
            actor_role="customer_service",
            action="emergency_bypass",
            target_type="work_order",
            target_id=new_wo_id,
```

### 步驟 5 — 執行既有測試

- **動作**：跑 gate 測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，三檔 22 項全數通過

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0152_ai_quote_gate.py tests/test_cr_0128_quote_gate.py tests/test_cr_0032_quote_engine.py -q -rs --tb=no
FFFFFFFFFFFF..FFFFFFFF                                                   [100%]
20 failed, 2 passed in 2.82s
```

錯誤原文 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定`。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0152_ai_quote_gate.py -q -p winloop_plugin --tb=no
3 passed in 2.94s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0128_quote_gate.py -q -p winloop_plugin --tb=no
11 passed in 1.09s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0032_quote_engine.py -q -p winloop_plugin --tb=no
8 passed in 3.64s
```

既有測試對本 TC 三條分支皆有斷言，第二輪皆執行通過：

`api/tests/test_cr_0128_quote_gate.py:69`、`:101`、`:126-127`

```python
        assert ei.value.error_code == "QUOTE_NOT_CUSTOMER_CONFIRMED"
...
        assert ei.value.error_code == "QUOTE_STATE_INVALID"
...
    """急件（emergency_class 非空）跳過報價開單；系統建 retrospective_audit_only 佔位。"""
    pid, uid = await _seed_confirmed_pc(emergency_class="locked_out")
```

---

## 觀測到的其他事實

- gate 排在地址檢查之前（`work_order_service.py:586` vs `:594`），因此「非急件 + 缺地址 + 報價未確認」的請求先收 425 而非 422。
- gate 排在既有工單冪等查詢之後（`work_order_service.py:569-579`），已存在工單的 PC 重送不會再過 gate。
- `quote_gate_applied` 欄位在 INSERT 中硬編為 `TRUE`（`work_order_service.py:618`、`:622`），含急件路徑；註解說明存量單為 `FALSE` 以豁免結案硬閘。
