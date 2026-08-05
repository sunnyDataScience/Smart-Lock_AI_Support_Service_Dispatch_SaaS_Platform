# TC-SEC-MEM-01 — 記憶讀寫的 default deny 與 kind 限制

> ## 🔄 判定更正（2026-08-05 回程式碼查證）
>
> **原判定「部分實作」→ 更正為「一致」。以下原文保留未改動。**
>
> 判定基準原文是「default deny raise；kind 僅限 profile/preference/fact/issue/dispatch（**對齊 test_memory.py**）」——**那個括號就是仲裁基準**。
> 實查 `agent/tests/test_memory.py`：`test_default_deny_on_missing_scope`（:39-46）用 `pytest.raises(ValueError)` 斷言的是**缺 scope**；`test_cross_user_isolation`（:16-27）與 `test_cross_tenant_isolation`（:30-35）對跨 scope 讀取斷言的是**回空清單**（`assert store.search(...) == []`），**不是 raise**。
> 也就是說「跨 user/tenant 讀取回空清單」正是該基準定義的期望行為，code 與之逐條相符。
> 若業主真要跨 scope 讀取拋例外，那是把身分比對上移到 UserMemoryManager／呼叫端的架構變更（需同時傳入 session 身分與請求 scope 才比得起來），命中 Architecture boundary 須另開 CIA。
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
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 4） |
| 走查時間 | 2026-08-03 15:34（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/agent/user_memory/store.py`、`postgres_store.py`、`escalation.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 「缺 tenant 或 user_id → raise」與「kind 僅限五種」皆有實作；「跨 user/tenant 讀取 → raise」在程式碼中不成立——跨 scope 查詢以 WHERE 條件過濾，結果為空清單而非例外。 |

**TC 原文**｜前置：記憶讀寫｜步驟：缺 tenant+user_id 或跨 user/tenant 讀取｜判定基準：default deny raise；kind 僅限 profile/preference/fact/issue/dispatch（對齊 test_memory.py）｜需求：FR-AGT-06、NFR-Priv-006｜旅程：SC-01、SC-02、SC-19

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 呼叫端 | 缺 tenant 或 user_id 讀寫 | （不應成功）`MemoryRead` | default deny raise | `store.py:31-33`、`postgres_store.py:32-34` | 拋 `ValueError` |
| 呼叫端 | 跨 user/tenant 讀取 | （不應成功）`MemoryRead` | default deny raise | `store.py:110-111`、`postgres_store.py:100-101` | 以 WHERE 過濾，回空清單，**不拋例外** |
| 呼叫端 | 寫入未知 kind | （不應成功）`MemoryWritten` | kind 限五種 | `store.py:92-93` | 拋 `ValueError` |
| 呼叫端 | escalation 讀寫缺 scope | （不應成功） | default deny | `escalation.py:16-18` | 拋 `ValueError` |

---

## 走查紀錄

### 步驟 1 — kind 的合法值

- **動作**：找 kind 的定義處
- **預期**：五種
- **實際**：一致，且為唯一定義處（Postgres 版 import 同一常數）

`agent/lockcore/agent/user_memory/store.py:16`

```python
VALID_KINDS = {"profile", "preference", "fact", "issue", "dispatch"}
```

強制點 `agent/lockcore/agent/user_memory/store.py:92-93`

```python
        if kind not in VALID_KINDS:
            raise ValueError(f"未知 kind: {kind!r}(可用:{sorted(VALID_KINDS)})")
```

### 步驟 2 — 缺 tenant／user_id 的處置

- **動作**：讀 scope 守衛
- **預期**：raise
- **實際**：一致

`agent/lockcore/agent/user_memory/store.py:31-33`

```python
def _require_scope(tenant: str, user_id: str) -> None:
    if not tenant or not user_id:
        raise ValueError("記憶讀寫必須同時帶 tenant 與 user_id(預設拒絕跨 user 查詢)")
```

呼叫點：`add`（:91）、`list_for_user`（:109）、`search`（:128）、`forget`（:164）。Postgres 版同字串守衛在 `postgres_store.py:32-34`，呼叫點 `add`（:81）、`list_for_user`（:99）、`search`（:118）、`forget`（:137）。escalation 版在 `escalation.py:16-18`。

### 步驟 3 — 跨 user/tenant 讀取的處置

- **動作**：檢查是否有「傳入 tenant 與 session tenant 不符」的比對
- **預期**：raise
- **實際**：無此比對；查詢一律把 tenant + user_id 放進 WHERE 條件，跨 scope 讀取的結果是空清單

`agent/lockcore/agent/user_memory/store.py:110-111`（以及 `postgres_store.py:100-101`）為 WHERE 過濾寫法。

TC 判定基準將「缺 tenant+user_id」與「跨 user/tenant 讀取」並列為 raise 條件，程式碼中前者 raise、後者回空清單。此處僅並陳，不裁定。

### 步驟 4 — 執行既有測試

- **動作**：跑 `tests/test_memory.py`
- **預期**：通過
- **實際**：sqlite 版第一輪即通過；Postgres 版第一輪因無 `POSTGRES_URI` 未列入執行批次，接上本機測試庫後補跑，兩檔合計 17 項全過

第一輪（無資料庫）：

```
cd agent && python -m pytest tests/test_memory.py ... -q
1 failed, 170 passed, 3 skipped in 15.86s
```

Postgres 版 `tests/test_memory_postgres.py` 需 `POSTGRES_URI`，第一輪未列入執行批次（該檔 `:24` 有 skipif）。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd agent && python -m pytest -p winloop_plugin tests/test_memory.py tests/test_memory_postgres.py -q -rs
.................                                                        [100%]
17 passed in 3.16s
```

Postgres 版含 `test_pg_default_deny`（`:95-97`，斷言缺 scope 時 `raises(ValueError)`）與 `test_pg_scope_isolation_and_forget`（`:80`），即步驟 2 的守衛在 Postgres backend 下亦有實跑證據；步驟 3 所述「跨 scope 讀取回空清單」的行為，在該檔中以 scope isolation 斷言呈現，非例外斷言。

---

## 觀測到的其他事實

- `PostgresEscalationStore.log`（`postgres_store.py:208`）與 `list_for_user`（`:226`）同樣套用 `_require_scope`。
- 三個 store 的守衛訊息字串各自獨立（memory 版與 escalation 版文字不同），非共用常數。
