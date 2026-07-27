# CR-0189 — 對帳核准原子性 ＋ 佣金事件 outbox

- **日期**：2026-07-27
- **觸發**：CR-0188 尾聲盤點「事件遺失」時，紅隊審查在同一段程式碼另外挖出兩個**生產金流缺陷**
- **觸發面向（CIA gate）**：Domain model（settlement 唯一性不變式）、DB schema（新表＋唯一索引）、Architecture boundary（新增背景 worker）
- **前置**：CR-0188（消費端 dedup 毒藥丸已修，重播才可能成立）

---

## §1 根因：四個語句、零交易、零列鎖

`api/services/reconciliation_service.py:approve_reconciliation` 原本依序下四個語句，
而共用連線是 `autocommit=True`（`core/db.py`）—— 意即**每個語句各自提交**：

```
SELECT r.status …            ← 無 FOR UPDATE
UPDATE reconciliations …     ← 提交點 1
INSERT INTO settlements …    ← 提交點 2
publish_event(...)           ← 失敗只 logger.exception
```

三個獨立缺陷由此而生：

| # | 缺陷 | 後果 | 嚴重度 |
|---|---|---|---|
| 1 | UPDATE 與 INSERT 分別提交 | 中斷 → 對帳單已 `approved` 但 **settlement 不存在**；重試撞 `_APPROVE_FROM={'pending'}` → **永久 409，API 再也補不回來**（只能改 DB） | CRITICAL |
| 2 | 無 `FOR UPDATE`，且 `settlements.reconciliation_id` **只有 FK、無 unique、連索引都沒有**（實查 `settlements_pkey` 是唯一索引） | 並發核准 → 兩筆 settlement → **重複出款** | CRITICAL |
| 3 | publish 失敗只 log | 事件永久消失。原註解宣稱「settlement 表為保底」—— 但保底只在 settlement 真的寫成功時成立，缺陷 1 正好打掉這個前提 | HIGH |

**這不是理論風險**：前端 `web/brand-portal/src/app/accounting/page.tsx:246` 打的
正是這條 legacy 路徑。

### 曾被我判錯的前提（記錄以免重蹈）

初版設計我判定「autocommit 連線上開不了交易，只能靠補償機制」。紅隊推翻：
psycopg3 的 `conn.transaction()` 在 autocommit 連線上**會送出顯式 BEGIN/COMMIT**，
repo 內 `api/services/` 已有 24–28 處既有用法。**修法因此可以是真交易，而非補償。**

---

## §2 設計

### S1 — DB（`SQL/migrations/119-commission-event-outbox.sql`）

- `commission_event_outbox`：欄位比照既有 `line_push_outbox` 狀態機慣例，但**多存
  `event_id`** —— `core/event_bus.publish_event` 未帶 `event_id` 時**每次新生成 uuid**，
  worker 重送若另生新 id，消費端 `_already_processed` 的去重就完全失效。
- 冪等鍵取 `(tenant_id, reconciliation_id)` 而非 `settlement_id`：併發會產生**兩個不同
  settlement_id**，用它擋不住；一張對帳單只該有一筆佣金事件。
- `uniq_settlements_reconciliation`：堵住缺陷 2 的 DB 層兜底。
  ⚠️ 存量已有重複則索引建立失敗 —— **刻意的**，重複出款屬財務事實，須人工裁定保留哪筆。

### S2 — service 交易化

```
async with db_module._conn.transaction():
    SELECT … FOR UPDATE OF r     ← 狀態檢查移進交易
    UPDATE reconciliations
    INSERT INTO settlements
    INSERT INTO commission_event_outbox   （event_id 由 Python uuid4 產生）
# ← COMMIT 之後才 publish
publish_event(..., event_id=commission_event_id)
  成功 → UPDATE outbox SET status='sent'
  失敗/例外 → 留 pending，交給 worker
```

**publish 必須在 commit 之後**：放進交易內而交易後續 rollback，就會發出一個
對應**不存在 settlement** 的幽靈事件。

### S3 — `api/realtime/commission_outbox_worker.py`

poll `pending AND next_attempt_at <= NOW()` → 帶原 `event_id` 重送 → 成功標 `sent`／
失敗 exponential backoff（30s/2m/8m/30m/2h/6h，max_attempts=8 ≈ 21h）／耗盡標 `dead`。

兩個硬性約束（皆有測試守線）：

1. **絕不開 `transaction()`** —— worker 跑在 lifespan 背景任務、不經
   `DBPoolScopeMiddleware`，用的是共用連線；顯式 BEGIN 會把同時間其他請求在同一條
   連線上的語句一併捲進本交易。只下單語句。
2. **必須 `ensure_leader()`** —— 多實例否則同一 row 重複 publish。

刻意**不**複製 `line_push_outbox_worker._poll_once` 的 `FOR UPDATE SKIP LOCKED`：
autocommit 下列鎖在語句結束即釋放，那行實質是 no-op，寫了誤導。

### S4 — `main.py` 接線

`_RUN_BACKGROUND_WORKERS` 閘內 start（與 `line_push_worker` 同層）、lifespan 逆序 stop。
tech/platform surface 不啟動。

---

## §3 驗證

- 新測試 `api/tests/test_cr_0189_commission_outbox.py` **13 passed**。
- **反向驗證**（防假綠）：把 service 還原成修復前 → **8 failed / 5 passed**；
  還原修復 → 13 passed。三個缺陷各有對應紅燈。
- migration 對 scratch 庫**二次套用** idempotent（`outbox 表 ✅ / settlements 唯一索引 ✅`），
  套用前重複列預檢 0 列。
- api 全套回歸見 §10。

---

## §8 Human Decisions Required

- 🛑 **v2 `co_sign_reconciliation` 是否也要走 outbox ＋ 發事件？**
  現況：**只有 legacy `approve_reconciliation` 會發 `commission.accrued`**；v2 共簽
  與月結 `generate_monthly_batch` 兩條寫入路徑都不發事件。
  此題觸發 **API contract / Domain model / Architecture boundary** 三面向，屬 CIA gate，
  **不由我裁決**。本 CR 刻意只修 legacy 路徑的既有缺陷、不擴張範圍。
  ⚠️ 但需明說代價：**不裁決就實作＝把 legacy/v2 分裂固化**，且這正是 CR-0188 記載
  「BR-SETTLE-05 對帳閘門設計上無法通過」的根源之一（閘門查 legacy `public.settlements`，
  月結讀寫 v2 `saas.*`）。
  選項：(a) v2 補發事件（治標，兩表仍分裂）；(b) 先收斂 v2/legacy 表分裂（治本，工程量大）；
  (c) 維持現狀並在閘門文件標記已知限制。

- ✅ **存量重複 settlement 盤點（2026-07-27 已跑，全綠）**：重複組數 **0**、approved 卻無 settlement **0**（無存量受害者）、`settlements` 索引現況原本**只有 `settlements_pkey`** —— 缺陷②在生產是實錘而非推論。套用後索引為 `settlements_pkey, uniq_settlements_reconciliation`。查詢：
  ```sql
  SELECT reconciliation_id, count(*), array_agg(id)
    FROM settlements GROUP BY 1 HAVING count(*) > 1;
  ```
  有列則**先人工裁定**再套（不可自動刪）。

- ⬜ **`dead` 事件的 OPS 重放程序**：目前只 `logger.error`。是否要接告警／後台頁面？

---

## §9 Implementation Order

1. ✅ migration 119（scratch 二套驗證）
2. ✅ service 交易化 ＋ outbox 同交易 ＋ publish 移到 commit 後
3. ✅ `commission_outbox_worker.py`
4. ✅ `main.py` 接線（`_RUN_BACKGROUND_WORKERS` 閘內）
5. ✅ 回歸測試 ＋ **反向驗證**
6. ✅ MIGRATION_REGISTRY 登錄
7. ✅ prod 套 migration 119（2026-07-27）＋ ⏳ 重佈 api
8. ⬜ §8 三項待業主裁決

---

## §10 進度

- ✅ S1–S6 done（merge `44ff7b76`）：13 新測試綠、反向驗證 8 紅→13 綠、api 全套 2119 passed / 13 failed（既有 seed 依賴，清單不變＝零回歸）、migration 二套 idempotent、registry 已登錄
- ✅ S7a done（2026-07-27）：prod 品牌庫套用 migration 119。前置盤點全綠（重複 0／孤兒 approved 0）、on-demand 備份先建、schema_migrations 已記帳；驗收五項全 OK。
- ⏳ S7b：重佈 `smart-lock-api`（worker 只在 `_RUN_BACKGROUND_WORKERS` 為真的品牌面啟動，tech/platform 面不受影響）
- 🛑 S8：§8 三項待業主裁決（v2 共簽範圍為 CIA gate 題）
