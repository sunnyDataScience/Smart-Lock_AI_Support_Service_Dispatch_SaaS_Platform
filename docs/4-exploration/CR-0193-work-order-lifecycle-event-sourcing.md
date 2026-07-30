# CR-0193 — 工單生命週期事件溯源（TC-WO-01 事件流缺口）

- **狀態**：✅ 實作完成，本機驗證通過（prod 待套 122 + 重佈）。§8 已裁決「照建議」，另有 1 項新發現待裁決（見 §11）
- **觸發面向**：DB schema（新欄位 + CHECK 擴充）、Domain model（事件流不變式）、API contract（events 回傳 additive）、Test plan（TC-WO-01）
- **來源**：UAT 2026-07-29 TC-WO-01 FAIL → UAT-D-007
- **正典依據**：`smartlock-docs/enterprise/20_Test_Cases.md:258`
  > TC-WO-01 | FR-0038 | 問題卡 `confirmed` + 地址齊全 | 客服按「轉為工單」 | 工單 `created`；**寫入 `work_order_events`（事件溯源 seq）**；AI 不可觸發此轉換（HITL 鐵律）| happy | P0
- **業主裁決（2026-07-30）**：事件溯源**屬 V1 範圍**（對 UAT-D-007 選項①）

---

## §1 現況實測（不是推論）

### 1.1 我在 UAT 報告裡把範圍講錯了，先更正

UAT-D-007 原文寫「建單路徑完全沒有寫入事件流」「`work_order_events` 全表 0 筆」，並據此判 P1。實測後兩點都要修正：

| 原判斷 | 實測 | 更正 |
|---|---|---|
| 事件流功能缺席 | 13 條寫入路徑存在，20 支斷言測試全過（scratch 庫） | **寫入機制是好的**，不是沒實作 |
| 全表 0 筆 ⇒ 路徑壞了 | `dispatch_logs` **同時也 0 筆** | 這 4 張工單是 SQL 直接 seed、**從沒走過 API 派工**，空表是資料來源造成 |
| 缺口＝建單少一筆 | 10 個生命週期轉換只有 3 個寫事件 | **缺口比我收窄後的說法更大** |

驗證指令（scratch 庫 `lock_uat_scratch`，未動 5433 `lock_AI_data`）：

```
pytest tests/test_uat_wave1_fixes.py                → 7 passed（含 assign 後 work_order_events 有 'assign' 事件）
pytest tests/test_cr_0053_arrival_doorcheck.py \
       tests/test_cr_0166_tech_reject.py \
       tests/test_schedule_conflict_detection.py \
       tests/test_cr_0180_consent_send_link.py      → 13 passed
UAT 庫複驗：wo=4 events=0 audit=84（全程唯讀）
```

### 1.2 真正的缺口：主生命週期 vs subflow 兩套待遇

事件寫入分成兩類，覆蓋率天差地遠：

**subflow 事件——齊全。** 走共用 recorder `_append_subflow_event`（`work_order_service.py:2560`），`_TAG_TO_EVENT_TYPE` 統一對映：`scope_change` / `material_request` / `delay` / `door_check` / `signature_submitted` / `reschedule_proposed`。另有 `arrival`、`supply_arrived`、`schedule_conflict`、consent（`other` + `payload.kind`）各自寫入。

**生命週期轉換——3/10。** 每個轉換各自手寫 INSERT，沒有共用出口，於是漏了就沒人發現：

| 轉換函式 | 行 | `work_order_events` | `dispatch_logs` |
|---|---|---|---|
| `create_from_problem_card`（建單，**TC-WO-01 直接驗這條**） | 413 | ✗ | ✗ |
| `accept_order`（技師接單） | 996 | ✗ | ✗ |
| `complete_order`（完工） | 1496 | ✗ | ✗ |
| `cancel_order`（取消） | 1661 | ✗ | ✗ |
| `reopen_order`（重開） | 750 | ✗ | ✗ |
| `escalate_order`（升級） | 2203 | ✗ | ✗ |
| `confirm_order`（確認） | 2275 | ✗ | ✗ |
| `reject_order` | 1095 | ✓ | ✓ |
| `assign_order` | 1896 | ✓ | ✓ |
| `reassign_order` | 2072 | ✓ | ✓ |

也就是：**一張工單從建立到完工，timeline 上看不到「建立」「接單」「完工」**，卻看得到「缺料」「延遲」「門檢」。這對「工單 timeline」與「爭議舉證」都是硬傷——`evidence_package_service.py:18` 正是拿 `list_work_order_events` 當舉證包來源。

### 1.3 `seq` 欄不存在——但理由要說對

`SQL/Schema_work_order_events.sql` 從未有 `seq`；`list_work_order_events`（`:3184`）以 `ORDER BY created_at DESC` 排序。實測 `information_schema` 確認 7 欄無 seq。

我原本設想的問題是「同交易多筆事件 `NOW()` 相同 → 排序不定」。**這個理由不成立**：`core/db.py:56` 是 `AsyncConnection.connect(uri, autocommit=True)`，每個 execute 各自交易，`NOW()` 逐句不同。

`seq` 真正的價值是**可證明沒有缺漏**——正典寫的是「事件**溯源** seq」。只有 `created_at` 時，一筆被刪掉的事件在事後查核上不留痕跡；有 per-工單連號才能靠缺號發現。這跟 `audit_events` 的 hash chain 是同一種需求，只是 `work_order_events` 目前沒有這層。

> 對比參考：`audit_chain_checkpoint` 給 `audit_events` 提供了竄改可證性。`work_order_events` 是獨立的 timeline 表，不在那條鏈上。

---

## §2 設計（三段，S1 必要、S2 必要、S3 依 §8-D5 決定）

### S1 — DB migration `SQL/migrations/122-wo-events-seq-and-lifecycle.sql`

1. 加 `seq INTEGER`（先 nullable，見 §8-D4 backfill 決策）
2. `UNIQUE (work_order_id, seq)`——連號的強制點，也是併發正確性的靠山
3. `event_type` CHECK 補生命週期值（同 050/059/102/104 老套路，**第 5 次同類 migration**，見 §8-D3）
4. 索引 `(work_order_id, seq DESC)` 取代／並存於現有 `(work_order_id, created_at DESC)`

> ⚠️ **idempotency 鐵律**：CHECK 一律 `DROP CONSTRAINT IF EXISTS` 再 `ADD`；`ADD COLUMN IF NOT EXISTS`。
> 016 的教訓（本輪已修）：帶內容比對的守衛（`NOT LIKE '%sop%'`）套用一次後就再也匹配不到，第二次 run 會炸。**不要用內容比對當守衛。**

### S2 — service：生命週期事件走單一出口

現況 7 個轉換漏寫的根因是**沒有共用出口**。所以不是補 7 個 INSERT，而是仿 `_append_subflow_event` 建 `_append_lifecycle_event(...)`，7 個轉換各呼叫一次。這樣下次再加轉換，漏寫會在 review 時看得出來。

`seq` 取號在 autocommit 下有 race（兩個並發事件同時算出同一個 `MAX(seq)+1`）。兩個可行做法：

```sql
-- 方案 a：單語句取號，靠 UNIQUE 擋碰撞 + 應用層重試
INSERT INTO work_order_events (work_order_id, tenant_id, actor_user_id, event_type, payload, seq)
SELECT %s::uuid, %s::uuid, %s, %s, %s::jsonb,
       COALESCE(MAX(seq), 0) + 1 FROM work_order_events WHERE work_order_id = %s::uuid
```
碰撞時 UNIQUE violation → 重試 1 次即可（同一工單併發寫事件極少）。

```sql
-- 方案 b：per-工單 advisory lock，零碰撞但多一次 round-trip
SELECT pg_advisory_xact_lock(hashtext(%s));   -- autocommit 下 xact lock 立刻釋放，需改用 session lock
```
方案 b 在 `autocommit=True` 下要用 session lock 並手動釋放，漏釋放會卡住整條連線（**共用單一連線**，風險高）。**建議方案 a。**

### S3 — API：`list_work_order_events` 回傳加 `seq`、排序改 `seq DESC`

additive 欄位，不破壞既有 consumer（`evidence_package_service`、v1 `work_orders.py:540`、v2 `work_orders_ops_v2.py:301`）。排序改 `seq DESC NULLS LAST` 才不會讓未 backfill 的舊列跑到最前面。

---

## §3 驗證計畫

1. `pytest tests/test_uat_wave1_fixes.py tests/test_cr_0053_arrival_doorcheck.py tests/test_cr_0166_tech_reject.py tests/test_schedule_conflict_detection.py tests/test_cr_0180_consent_send_link.py`——**現有 20 支必須全綠**（新增欄位不可打壞既有寫入）
2. 新增 `tests/test_cr_0193_lifecycle_events.py`：7 個轉換各驗一筆事件 + `seq` 連號 + 併發取號無重號
3. TC-WO-01 端到端重跑：建單 → `GET .../events` 應見 `created` 事件、`seq=1`
4. `pytest` 全套跑 **scratch 庫**（`POSTGRES_URI=...lock_uat_scratch`）——不可打 5433 `lock_AI_data`
5. migration 在 scratch 庫**連套兩次**證 idempotent

---

## §8 Human Decisions Required 🛑

> 業主已裁決「事件溯源屬 V1 範圍」。以下是實作前無法由我單方決定的五點。標「建議」的是我的推薦，你只要說「照建議」即可。

**D1 — `seq` 的語意：per-工單連號 還是 全域序列？**

1. **per-工單連號**（1,2,3… 每張工單自己數）——**建議**。理由：正典要的是「溯源」，只有連號才能靠缺號證明沒被刪；全域 `BIGSERIAL` 缺號無法區分「別的工單佔號」與「被刪」，等於沒有溯源價值。代價＝取號要處理併發（§2-S2 方案 a）。
2. 全域 `BIGSERIAL`——零 race、實作最省，但放棄缺漏可證性。
3. 兩者都放（全域當穩定排序、per-工單當溯源）——最完整，但欄位與心智負擔加倍。

**D2 — 補事件的範圍：只補 TC-WO-01 要的建單，還是 7 個轉換全補？**

1. **7 個全補**——**建議**。理由：只補建單能讓 TC-WO-01 過，但 timeline 仍缺「接單／完工／取消」，而 `evidence_package_service` 拿它當爭議舉證來源；下輪 UAT 驗 TC-ONSITE／TC-SETTLE 會再撞同一個洞。工作量差別不大（共用出口寫好後每條是一行呼叫）。
2. 只補 `create_from_problem_card`——最小改動、風險最低，但把缺口留到下輪。

**D3 — 新 `event_type` 用獨立值還是沿用 `other` + `payload.kind`？**

1. **獨立值**（`created` / `accepted` / `completed` / `cancelled` / `reopened` / `escalated` / `confirmed`）——**建議**。可直接 `WHERE event_type='completed'` 查詢與統計；TC-WO-01 斷言不必翻 jsonb。代價＝這是**第 5 次**為了加值改同一條 CHECK（050/059/102/104 之後）。
2. 沿用 `other` + `payload.kind`（consent 現在的做法）——不動 CHECK、永不再有這類 migration，但查詢要翻 jsonb、統計與索引都變難。

> 若選 1，建議順手在 migration 註解寫明「新增 event_type 必須同步改 CHECK」，並考慮下一個 CR 把 CHECK 改成參照表以終結這串 migration（不在本 CR 範圍）。

**D4 — 既有列要不要 backfill `seq`？**

本機 UAT 庫 `work_order_events` = 0 筆，**backfill 無事可做**。但**我沒有查 prod 的筆數**（需 `gcloud auth login` + cloud-sql-proxy，權杖隔夜過期）。

1. **先查 prod 筆數再決定**——**建議**。若 prod 也接近 0 → 直接 `NOT NULL` 不必 backfill；若有量 → 依 `created_at` 排序回填後才加 `NOT NULL`。
2. 一律 nullable、不 backfill、排序用 `NULLS LAST`——最省，但舊列永遠不在溯源保護內。

**D5 — S3（API 回傳 `seq` + 改排序）要不要同 CR 做？**

1. **同 CR 做**——**建議**。不改排序的話 `seq` 只是躺在 DB 裡的裝飾，TC-WO-01 的「溯源」在 API 表面驗不到。additive 欄位風險低。
2. 拆下一個 CR——本 CR 只落 DB 與寫入，API 表面不變。

---

## §9 Implementation Order（待 §8 裁決後執行）

1. S1 migration `122`，scratch 庫連套兩次驗 idempotent
2. `_append_lifecycle_event` 共用出口 + 依 D2 範圍接上轉換函式
3. 現有 20 支測試回歸（必須全綠）
4. 新增 `tests/test_cr_0193_lifecycle_events.py`（含併發取號）
5. 依 D5 決定是否動 API 回傳與排序
6. TC-WO-01 端到端重跑，更新 `docs/uat/uat-results/claude-proxy-*.yaml` 與執行計畫 workbook
7. 同步三處：本檔 §10 進度、`CHANGELOG.md [Unreleased]`、`MIGRATION_REGISTRY.md`
8. 有架構決策 → 開 ADR（`seq` 語意屬 domain invariant，D1 選 1 或 3 時需要）

---

## §10 進度

- 2026-07-30：CIA 產出，等 §8 裁決。UAT-D-007 的範圍與嚴重度已在 §1.1 更正。
- 2026-07-30：**§8 業主裁決「照建議」** → D1 per-工單連號 / D2 全補 / D3 獨立值 / D4 先查 prod / D5 同 CR 做。實作完成：
  - **S1** `SQL/migrations/122-wo-events-seq-and-lifecycle.sql`：拋棄式 `lock_mig122` **連套三次**退出碼 0（第二次 `UPDATE 0` 證守衛有效）；backfill 實測 per-工單各自從 1、依 `created_at` 排序正確；六項約束實測會咬（NOT NULL 擋無 seq、UNIQUE 擋重號、CHECK 放行 `created` 擋亂值、取號語句得 100、空集合得 1）。已套 scratch 與本機 UAT 庫。
  - **S2** 全部 **12 條**既有寫入點改道共用出口 `_insert_wo_event`（含 `consent_service`）＋補 7 個生命週期事件。**D1 的必然後果**：per-工單連號要有意義就必須每筆都編號，所以不是新增一個 lifecycle helper，而是把全部寫入收斂到單一取號出口——留 NULL 的事件會在連號開洞、缺號就無法區分「被刪」與「沒編號」。
  - **S3** `list_work_order_events` 回傳加 `seq`、排序改 `ORDER BY seq DESC`。
  - **D4 backfill**：改用「migration 內直接 backfill」，不再依賴先查 prod 筆數——`WHERE seq IS NULL` 對 0 列或大量列都正確且可重套，故 D4 的前置查詢不再是阻塞項。惟 **prod 套用前仍應確認筆數**以評估鎖表時間（需業主 `gcloud auth login`）。
  - **稽核發現並修補（超出原 7 個）**：寫了程式化稽核掃全 `services/`、`realtime/` 的 `UPDATE work_orders SET status=`，抓到 3 處原本不在清單內：
    - `cancellation_service.cancel_work_order_6stage`（**v2 tenant-scoped 取消實際走這條**，不經 `cancel_order`——只補 `cancel_order` 的話實際在用的取消路徑仍不落事件）→ 已補
    - `work_order_service.auto_confirm_stale_completed`（cron 自動結案）→ 已補（同 `confirmed` 型別、不需新 CHECK 值）
    - `scope_change_service.respond_public` / `admin_override`（→ `in_progress`）→ **未補**，見 §11
  - **驗證**：既有 20 支事件斷言測試全綠；新增 `tests/test_cr_0193_lifecycle_events.py` 16 測；全套 `2210 passed / 13 failed`，那 13 支已於**乾淨基線**（stash 全部變更 ＋ pre-122 的 `lock_base` 庫）重跑確認同樣失敗＝既有問題。`test_migration_drift_check_passes` 曾因 122 未登記而失敗（drift check 正確作用），補 `MIGRATION_REGISTRY.md` 後通過。
  - **端到端（TC-WO-01 閘門項）**：全程走真實 HTTP API＋scratch 庫。補卡欄位→confirm→標急件→轉工單`201`→`GET events` 得 **`seq=1 type=created actor=c782bcfe…`**，payload 含 `origin/problem_card_id/urgency/emergency_class/quote_gate_applied`。再 escalate `200` → `seq=2 type=escalated actor` 有值、DESC 排序、連號無缺口 → **router 的 `actor_user_id` 傳遞已實證接上**。UAT 庫複驗 `4/19/0/84/16/0` 零污染。

## §11 新發現待裁決 🛑

**scope_change 的復工轉換要不要也落事件？**

`scope_change_service.respond_public`（客戶用公開連結核可範圍變更）與 `admin_override`（後台強制核可）都會把工單推回 `status='in_progress'`，目前**不落事件**。

這超出你裁決的 7 個，且需要**新增一個 event_type**（例如 `resumed`），所以我沒有擅自擴充 CHECK。

1. 也補（migration 122 追加 `resumed`，或另開 123）——timeline 才完整；範圍變更後復工是爭議舉證常查的節點
2. 不補——現況 `scope_change` 事件已記「有提出範圍變更」，只是看不到「何時核可復工」

> 註：現有 `scope_change` 事件記的是**申請**，不是核可復工，語意不同，不建議用它兼代。
