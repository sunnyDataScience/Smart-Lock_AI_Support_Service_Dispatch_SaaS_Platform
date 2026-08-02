---
id: CR-0198
title: 月結批次建 settlement 不發 commission.accrued，導致對帳閘門開了就永久 409
status: awaiting-decision
created: 2026-08-02
author: Claude（SC-13～19 探針執行時發現）
triggers: [Domain model, Architecture boundary, Test plan]
related: [CR-0166, CR-0188, CR-0189, TC-EXC-06, BR-SETTLE-05, ADR-017]
---

# CR-0198 — 月結批次不發佣金事件，對帳閘門無法啟用

## 1. 一句話

`monthly_settlement_service.generate_monthly_batch` 建 `saas.settlement` 時
**不發 `commission.accrued`**，技師平台的佣金投影因此缺這批資料；
一旦啟用 `settlement_policy.reconcile_gate_enforce`，月結會**永久 409**。

---

## 2. 先更正一個過期說法

`docs/uat/sc13-19-probe-execution-20260802.md` §三-A 寫的是
「**只有 legacy `approve_reconciliation` 會發 `commission.accrued`**，
v2 與月結兩條寫入路徑都不發」。

**這句已經過期一半。** 實查現行 code：

| 路徑 | 檔案:行 | 是否發事件 |
|---|---|---|
| legacy 對帳核准 | `reconciliation_service.py:263-280` | ✅ 發（含 outbox） |
| **v2 對帳核准** | `reconciliation_v2_service.py:303-356` | ✅ **發**（同交易寫 `commission_event_outbox` → commit 後 publish → 標 sent） |
| **月結批次** | `monthly_settlement_service.py:200` | ❌ **不發**（全檔 0 處 publish／outbox） |

v2 那半是 **CR-0189** 補的（「對帳核准非原子＋無列鎖＝settlement 遺失與重複出款」），
順帶把事件投遞也做成 outbox at-least-once。

**所以真正的缺口只剩月結批次這一條**，比原記載窄。0727 紅隊審查當時的判斷在
v2 部分已不成立。

---

## 3. 缺口的實際結構

### 3.1 事件面

```
legacy 對帳核准 ──→ public.settlements  ──→ commission.accrued ──→ 技師佣金投影 ✅
v2   對帳核准 ──→ saas.settlement     ──→ commission.accrued ──→ 技師佣金投影 ✅
月結批次      ──→ saas.settlement     ──✗ （無事件）        ──→ 投影缺這批   ❌
```

消費端 `event_consumer.handle_commission_accrued` 寫
`technician_commission_projection`（技師權威庫 `lock_tech`）。月結產生的 settlement
永遠不會進投影 → 技師端「我這個月被結了多少」看不到月結那部分。

### 3.2 對帳閘門面（更嚴重）

`event_reconcile_service.reconcile_commission` 的資料源是
**`FROM settlements s`**（`event_reconcile_service.py:58`，即 legacy `public.settlements`），
而月結寫的是 **`saas.settlement`**（`monthly_settlement_service.py:200/281`）。

閘門的邏輯是「品牌側 settlements ↔ 技師側佣金投影 對平」。兩邊都對不上：

- 品牌側只查得到 legacy 表 → 月結那批不在比對範圍
- 技師側投影缺月結那批 → 就算把品牌側改查 `saas.settlement`，投影仍是空的

**後果**：`settlement_policy.reconcile_gate_enforce` 一旦打開，
`_assert_reconcile_gate` 會因 mismatch/missing > 0 而丟 409 `RECONCILE_GATE_UNMET`，
**每次月結都擋，且無法自行恢復**。

> 這正是 migration 118 檔頭那段警語的來源：
> 「貿然開啟＝每次月結永久 409。修正屬另一個 CR」——**本 CR 就是那個 CR**。

### 3.3 現況為什麼還沒爆

`reconcile_gate_enforce` **預設 off**（migration 118 寫入 `false`，prod 至今未開），
所以閘門根本沒跑。BR-SETTLE-05 的期末對帳把關目前**形同不存在**。

另外 2026-08-02 已修：閘門在 Kafka 未啟用時原本回 `gate_pass=true`（真空通過），
現已改為 `false` + `RECONCILE_GATE_UNAVAILABLE`（commit `49de54d3`）。
所以現在的狀態是「閘門誠實地說自己跑不起來」，而不是「假裝通過」。

---

## 4. 影響評估

| 面向 | 現況（閘門 off） | 若直接開閘門 | 修好後 |
|---|---|---|---|
| 月結能否執行 | ✅ 正常 | ❌ **永久 409** | ✅ 正常且受檢 |
| 技師看得到月結佣金 | ❌ 投影缺 | ❌ 同左 | ✅ |
| BR-SETTLE-05 把關 | ❌ 不存在 | —— | ✅ |
| 跨品牌對帳（ADR-017） | 只涵蓋對帳核准那半 | —— | 完整 |

**目前沒有出款風險**——月結的 `saas.settlement` 本身是正確的，缺的是
「技師端看得到」與「有東西可對帳」。

---

## 5. 可能的修法（供裁決，未實作）

### 方案 A：月結補發事件（對稱既有兩條路徑）

在 `generate_monthly_batch` 建 settlement 的同交易寫 `commission_event_outbox`，
commit 後 publish，比照 `reconciliation_v2_service.py:303-356` 的既有寫法。

- ✅ 與現有兩條路徑對稱，消費端零改動（handler 已是 `ON CONFLICT DO UPDATE` 冪等）
- ✅ outbox 保證 at-least-once，不會因網路抖動永久遺失
- ⚠️ 月結是批次，一次可能產生大量事件 → 需確認 outbox worker 的吞吐與 backoff
- ⚠️ 存量的月結 settlement 需**補發**（backfill），否則投影仍缺歷史

### 方案 B：閘門改查 `saas.settlement`（收斂表分裂）

把 `event_reconcile_service` 的資料源從 legacy `settlements` 換成 `saas.settlement`。

- ✅ 一行改動
- ❌ **單獨做無效**——投影端仍缺月結資料，比對只會從「兩邊都缺」變成「一邊有一邊缺」
- 必須與 A 同時做

### 方案 C：A + B + backfill（完整）

1. 月結補發事件（A）
2. 閘門資料源收斂到 `saas.settlement`（B）
3. 存量 settlement 補發事件或直接回填投影
4. 驗證投影對得平之後，才打開 `reconcile_gate_enforce`

---

## 6. 🛑 Human Decisions Required

### D1：修法選哪個？

- **(a) 方案 C 完整做** —— 對帳閘門真的能用，但工作量最大（含 backfill）
- **(b) 只做 A** —— 技師看得到月結佣金；閘門仍不能開（表分裂未解）
- **(c) 暫不修，明確標注** —— 在正典標注「BR-SETTLE-05 期末對帳閘門 v1 不啟用」，
  並在 `monthly_settlement_service` 加註解說明它目前不具把關效力

### D2：legacy `public.settlements` 與 v2 `saas.settlement` 要不要收斂？

這兩張表並存本身是更大的技術債（本 CR 只是它的一個症狀）。

- **(a) 本 CR 只處理事件，表分裂另開 CR**
- **(b) 一併收斂** —— 範圍大，需盤點所有讀寫兩表的路徑

### D3：存量 settlement 要不要 backfill 投影？

- **(a) 要** —— 技師看得到完整歷史，閘門才對得平
- **(b) 不要** —— 只保證未來正確，投影從啟用日起算

---

## 7. Suggested Implementation Order（待 §6 裁決後）

1. 依 D1 決定範圍
2. 若做 A：先補測試（月結建 settlement 必發事件、outbox 落地、重送冪等），
   再改實作——**反向驗證要能證明舊 code 恰好紅在該條**
3. 若做 B：同時確認沒有其他讀 legacy `settlements` 的路徑被打壞
4. 依 D3 決定 backfill
5. 投影對平驗證通過後，才動 `reconcile_gate_enforce`
6. 更新 `docs/uat/sc13-19-probe-execution-20260802.md` §三-A 的過期記載

---

## 附錄：查證方式

- 三條路徑的事件發佈以 `grep publish_event / commission_event_outbox` 全檔比對，
  非依賴先前文件記載——原記載「v2 不發事件」實查已不成立。
- 表分裂以 `event_reconcile_service.py:58`（`FROM settlements`）對
  `monthly_settlement_service.py:200/281`（`saas.settlement`）直接比對。
- 未執行任何寫入；未啟用任何開關。
