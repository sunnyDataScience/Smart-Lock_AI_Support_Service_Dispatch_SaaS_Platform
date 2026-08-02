---
id: CR-0199
title: 工單／問題卡狀態機是無鎖 check-then-act，並發異型 transition 會 lost update
status: awaiting-decision
created: 2026-08-02
author: Claude（用 defect-patterns §A5 清單掃出）
triggers: [Domain model, Architecture boundary]
related: [CR-0189, CR-0166, UAT-R3-6]
---

# CR-0199 — 狀態機 transition 無鎖、無樂觀條件，並發下狀態機可被繞過

## 1. 一句話

所有工單／問題卡的 transition 都是「SELECT status 檢查 → UPDATE」兩個獨立語句，
**專案為 autocommit、無交易、無列鎖、UPDATE 也不帶 status 條件**，
兩個並發的**異型** transition 會雙雙通過各自的狀態守衛，後寫的覆蓋先寫的。

---

## 2. 發現方式

用本日新建的 `.claude/skills/sunnydata-code-review/references/defect-patterns.md`
§A5（併發）掃 `work_order_service.py` 時，`_fetch_status_for_update` 這個名字
與其實作不符引起注意——**函式名說 for update，SQL 裡沒有 `FOR UPDATE`**。

順著查下去發現這不是單一函式的命名問題，是整個狀態機層的模式。

---

## 3. 根因

### 3.1 命名謊報語意

```python
# services/work_order_service.py:1164
async def _fetch_status_for_update(wo_id: str, tenant_id: str) -> str:
    """Fetch current DB status with tenant guard. Raises NOT_FOUND if missing."""
    cur = await db_module._conn.execute(
        f"SELECT wo.status {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )                                    # ← 沒有 FOR UPDATE
```

`services/problem_card_service.py:264` 有**獨立一份**同名函式，同樣無鎖。

叫 `_for_update` 會讓後續開發者以為有列鎖保護，因而放心做 check-then-act——
而這正是它現在被使用的方式。

### 3.2 就算真的加 FOR UPDATE 也沒用

`work_order_service.py:607` 的既有註解已經記載了這件事：

> UAT R3-6：**autocommit 下步驟 1 的 FOR UPDATE 鎖不跨語句**，步驟 2 的
> get-or-create 在併發下可雙雙 miss → 靠 migration 110 的 partial UNIQUE
> DB 兜底

所以本專案的併發正確性**不能靠列鎖**，只能靠：①顯式交易 ②UPDATE 帶樂觀條件
③DB constraint 兜底。目前狀態機三者皆無。

### 3.3 UPDATE 不帶樂觀條件（實測全檔掃描）

| 檔案 | `UPDATE ... SET` 只靠 `WHERE id` | 帶 status 條件 |
|---|---|---|
| `work_order_service.py` | **18** | 1（`completed` 清理批次） |
| `problem_card_service.py` | **7** | 0 |

唯一那個有條件的是批次清理 job，不是狀態機 transition。

### 3.4 受影響的 transition

`_fetch_status_for_update` 共 21 個呼叫點，其中 **9 個**在檢查後做無鎖 UPDATE：

`accept_order`、`reject_order`、`complete_order`、`cancel_order`、
`escalate_order`、`confirm_order`、`_append_subflow_event`、
`record_arrival`、`confirm_reschedule_by_customer`

---

## 4. 具體失效路徑

### 4.1 同型並發：無害

兩個並發 `accept_order`：都讀到 `assigned`、都通過守衛、都寫 `accepted`。
結果一致，冪等。**不是問題。**

### 4.2 異型並發：狀態機被繞過

> ⚠️ **2026-08-02 實測更正**：本節原本舉的「拒單 vs 改派」案例**是錯的**。
> `reject_order` 在 UPDATE 前會另查一次 `technician_id` 並比對
> （`work_order_service.py:1324`），改派已換掉 technician_id，
> 所以那條路徑**既有 code 就擋得住**——`test_reject_loses_race_to_reassign`
> 在修正前即為綠燈。
>
> 真正會失效的是「**status 改變但 technician_id 不變**」的組合，已由測試證實三組：
>
> | 組合 | 修正前的實際結果（實測，非推導） |
> |---|---|
> | 拒單 vs 客戶取消 | 🔴 已取消的單被打回 `created`，**重新出現在派工池** |
> | 接單 vs 客戶取消 | 🔴 已取消的單變成 `accepted` |
> | 取消 vs 技師完工 | 🔴 **已完工的單被改成 `cancelled`** |
>
> 第三組最嚴重——完工是計酬依據。
>
> 以下保留原始推導供對照（**機制描述仍然正確**，只是選錯了案例）：

技師 A 被派工單 W（`status=assigned`, `technician_id=A`）：

```
T1  技師 A 按「拒單」            T2  小編按「改派給 B」
────────────────────────────    ────────────────────────────
SELECT status → 'assigned' ✅
                                SELECT status → 'assigned' ✅
                                UPDATE SET technician_id='B'
SELECT technician_id → 'A'
  （讀到的是 T2 寫入前的快照或
    後的值，取決於時序）
UPDATE SET status='created',
           technician_id=NULL
           WHERE id=W          ← 沒有 AND status='assigned'
────────────────────────────────────────────────────────────
最終：W 回到 created 池、technician_id=NULL
      技師 B 的 app 上單子憑空消失
      dispatch_logs 有 reassign + reject 兩筆，work_orders 只反映 reject
```

同型的組合還有：`cancel_order` vs `accept_order`（客戶取消 vs 技師接單）、
`complete_order` vs `escalate_order`。

### 4.3 影響評估

| 面向 | 評估（2026-08-02 實測後修訂） |
|---|---|
| 資料遺失 | ❌ 無——工單本體不會消失 |
| 金流錯誤 | ⚠️ **間接有**——「已完工被改成 cancelled」會影響計酬依據；settlement 本身 CR-0189 已原子化 |
| 狀態不一致 | ✅ **有且已實測證實三組**——狀態機 invariant 可被繞過 |
| 可恢復性 | 中——狀態可人工改回，但已發出的通知與稽核紀錄無法回收 |
| 目前是否已發生 | **無證據**。UAT 階段並發量低，未見相關 finding |

**嚴重度：MEDIUM～HIGH**（原評 MEDIUM，實測後上修）。

上修的理由是「取消 vs 完工」這組：**已完工的單可被取消覆寫**，而完工是計酬依據。
原本評估時我假設後果只是「工單回池、可重派」，實測發現受影響的組合包含完工狀態。

它是**沉默失效**：不會報錯，只會讓狀態悄悄不對。

---

## 5. 為什麼現在還沒爆

1. UAT 階段並發低，異型 transition 撞在一起的窗口是毫秒級
2. 大部分 transition 由不同角色觸發，實務上不會同時按
3. 真正高風險的金流路徑（對帳核准）**已由 CR-0189 單獨修好**——
   那次是四個語句零交易零列鎖，導致 settlement 遺失與重複出款

換句話說：**團隊已經在最痛的那條路徑上踩過並修過，但沒有回頭處理同一個模式的其餘部分。**

---

## 6. 修法選項（未實作）

### 方案 A：UPDATE 帶樂觀條件（最小改動）

```sql
UPDATE work_orders SET status = 'created', technician_id = NULL, ...
WHERE id = %s::uuid AND status = %s          -- ← 加上讀到的那個 status
```
`rowcount == 0` → 拋 409 `STATE_CONFLICT`（狀態已被他人改變，請重試）。

- ✅ 不需交易、不需列鎖，與 autocommit 相容
- ✅ 每處只加一個條件 + 一個 rowcount 檢查，25 處機械式改動
- ✅ 與現有 409 語意一致（呼叫端已會處理 STATE_CONFLICT）
- ⚠️ 25 處都要改，漏一處就留一個洞 → **必須用腳本掃描驗證，不可手列**

### 方案 B：把 transition 包進顯式交易 + `SELECT FOR UPDATE`

- ✅ 語意最正確
- ❌ 要改 `db_module` 的連線管理（目前 autocommit），影響面大
- ❌ 與既有 UAT R3-6 的結論衝突（該註解明示不走這條）

### 方案 C：只修高風險組合

只對 `reject`／`cancel`／`accept`／`assign` 這幾個會動 `technician_id` 的加樂觀條件。

- ✅ 改動最小
- ❌ 留下判斷「哪些算高風險」的長期負擔；下一個開發者不會知道邊界在哪

### 方案 D：先只修命名 + 留註解

把 `_fetch_status_for_update` 改名為 `_fetch_status_or_404`，
並在 docstring 明示「**本專案 autocommit，此處無列鎖；呼叫端若要寫入，
UPDATE 必須帶樂觀條件**」。

- ✅ 零風險，立刻消除認知陷阱
- ❌ 不修正實際併發問題
- 💡 **無論選哪案都應該做**——名字現在是在誤導人

---

## 7. 🛑 Human Decisions Required

### D1：修不修？修到什麼程度？

- **(a) 方案 A 全做**（25 處加樂觀條件）—— 推薦。機械式改動、可腳本驗證、
  與現有 409 語意相容
- **(b) 方案 C 只修高風險**
- **(c) 暫不修，記錄為已知限制** —— 若判斷 V1 並發量不足以觸發

### D2：命名（方案 D）要不要現在就做？

改名動 21 + 3 處呼叫點，但純機械、零行為變更。**建議無論 D1 選什麼都先做。**

### D3：要不要補併發測試？

目前無任何 transition 的並發測試。若做方案 A，測試要能證明
「舊 code 在並發下確實會 lost update」——這需要可控的並發夾具。

---

## 8. Suggested Implementation Order（待 §7 裁決後）

1. 先寫失敗測試：模擬 reject vs reassign 並發，證明現行 code 會把已改派的單打回池
2. 依 D1 決定範圍
3. 若做方案 A：**用腳本列出所有 `UPDATE work_orders/problem_cards SET` 並逐一確認**，
   完成後重跑同一腳本驗證「無樂觀鎖」計數歸零——不可手列（見
   `reference_programmatic_gap_audit` 的教訓）
4. 反向驗證：stash 掉修正，確認恰好那幾支測試變紅
5. 更新 `_fetch_status_for_update` 命名與 docstring（方案 D）

---

## 附錄：查證方式

- 21 個呼叫點以 AST 級掃描列出（不是手列），並逐一判斷其後是否有
  `UPDATE work_orders`
- 樂觀鎖統計以 regex 抽出所有 `UPDATE ... SET ... WHERE` 的 SQL 字串（含跨行拼接）
  後逐一檢查 WHERE 子句是否含 `status`
- autocommit 的事實依據為 `work_order_service.py:607` 的既有註解（UAT R3-6），
  非推測
- ~~未執行任何寫入、未改動任何 code~~ —— 業主 2026-08-02 裁決方案 A，已進入實作
- ~~併發失效路徑為推導，尚未證實~~ → **已證實**。
  `api/tests/test_state_machine_optimistic_lock.py` 用「精確競態窗口注入」
  （monkeypatch `_fetch_status_for_update`，在回傳過期 status 之前先改 DB）
  取代真並發，每次必然重現、不依賴時序運氣。修正前 3 紅 3 綠：
  - 🔴 reject vs cancel、accept vs cancel、cancel vs complete —— 缺陷確認
  - ✅ 兩個 happy path —— 釘住正常路徑
  - ✅ reject vs reassign —— **既有 code 已擋**，據此更正 §4.2 的主案例
