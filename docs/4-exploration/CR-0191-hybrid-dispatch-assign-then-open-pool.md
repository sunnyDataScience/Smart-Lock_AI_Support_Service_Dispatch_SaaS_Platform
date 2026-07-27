# CR-0191 — 混合派工模式：指派為主、搶單為輔

- **日期**：2026-07-28
- **觸發**：業主於 OD-003 裁決過程中確認產品形態——師傅在單一 app 內看到多個品牌／
  經銷商的接案需求（Uber 式聚合），派工採「**指派為主、搶單為輔**」：先指派給選定師傅，
  逾時未接則釋出到公開池由其他師傅承接。
- **觸發面向（CIA gate）**：User flow、Business flow、API contract、Domain model、
  DB schema、Test plan、Architecture boundary
- **決策正典**：[ADR-043](../../smartlock-docs/enterprise/14_ADR/ADR-043_技師即時channel歸屬technician-platform.md)
  （channel 歸屬，已定版）· [ADR-041](../../smartlock-docs/enterprise/14_ADR/ADR-041_跨品牌技師身分單一平台principal加品牌membership.md)
  （技師身分）· ADR-P004（技師共享池）
- **狀態**：🛑 **等待業主填寫 §8，未經裁決不得動 code**

---

## §1 為什麼這是獨立 CR 而不是 ADR-043 的一部分

ADR-043 只決定了「師傅的即時通知由誰持有」。本 CR 要決定的是「**工單怎麼到達師傅**」——
那是派工流程本身，屬產品層變更，爆炸半徑涵蓋 domain model、DB schema 與金流結算歸屬。
ADR-043 §Scope 已明文把它排除。

## §2 AS-BUILT 盤點：現在是純指派制

| 面向 | 現況 | 證據 |
|---|---|---|
| 派工決策 | **品牌／平台決定派給誰**，師傅無選擇權 | `api/services/dispatch_service.py` 只有 `listDispatchCandidates` |
| 候選排序 | 依 brand／district／GIS 距離評分，5→10→20km 漸進擴大候選池，達 `min_pool` 即停 | `dispatch_service.py:86-111`（FR-API-05）|
| 派工模式 | `manual`（人工挑）／`platform_paid`（平台代派，可計費）／`auto_match`（自動媒合） | `dispatch_mode_service.py:21` `VALID_MODES` |
| 師傅端動作 | **完全沒有** accept／reject／decline／搶單 | grep `api/routers/dispatch_v2.py` 零命中 |
| offer 概念 | **不存在**（`offer` 命中的是保固／工單語意，非派工 offer）| grep `api/routers/` |

**結論：搶單這一半是從零開始，不是既有功能的延伸。**

## §3 影響分析

### 3.1 Domain model（新概念）

需要一個現在不存在的實體：**派工 offer**。至少要有

- 狀態機：`assigned`（指派中）→ `expired`（逾時）→ `open`（釋出到公開池）→ `claimed`
  （已承接）／`withdrawn`（品牌撤回）／`unfulfilled`（無人承接）
- 逾時策略：指派後多久釋出？公開池掛多久算無人承接？逾時是否分級（先給第二順位再公開）？
- 與 `work_order` 的關係：offer 是工單的附屬狀態，還是獨立生命週期？**這會決定 schema。**

### 3.2 併發控制（最容易出事的地方）

公開池是**競爭資源**：兩個師傅同時按「接單」，只能有一個成功。

- 需要 DB 層的原子承接（`UPDATE ... WHERE status='open'` 搭配 row lock，或 advisory lock）
- 失敗的那位必須拿到明確的「已被接走」而不是 500，且前端不得顯示假成功
  （對應 ADR-034 的 server-confirmed 分級——**承接絕不可 optimistic**）
- 重送／重試必須冪等：同一師傅重按不得產生第二筆承接

### 3.3 公平性與可稽核性

一旦是搶單，「誰先看到」就有商業價值，必須能解釋：

- 公開池對所有具備資格的師傅同時可見，還是分批釋出？
- 是否要輪替／權重（避免同一批師傅長期吃到所有單）？
- 品牌能否指定「只釋出給我的授權師傅」？（與 ADR-041 的 brand membership 直接相關）
- 每次釋出與承接都要留 audit，否則爭議時無法還原

### 3.4 API contract

新增至少：釋出 offer、師傅查詢可承接 offer、承接、放棄、品牌撤回。承接端點需要
版本／precondition 語意，衝突回 `409` 並帶當前狀態（沿用 CR-0190 的 conflict contract）。

### 3.5 跨系統邊界

依 ADR-043，offer 要投影到 technician-platform 才能出現在師傅 app 的聚合清單。這使
**投影延遲成為產品 SLA**——offer 有時效，延遲直接影響師傅搶不搶得到。與 3.1.1 Kafka
事件骨幹的取證進度綁定。

### 3.6 金流與結算

`platform_paid` 模式是可計費事件。搶單成交的佣金歸屬、平台抽成、以及「指派未接被別人
搶走」時原指派師傅是否有任何補償——這些是 BR 層問題，會牽動 settlement。

### 3.7 測試

- 併發承接（N 個師傅同時搶同一單，恰好一個成功）
- 逾時釋出的邊界（剛好逾時瞬間指派師傅按下接受）
- 跨品牌資格過濾（非授權品牌的師傅看不到該 offer——ADR-041 隔離假設不得破）
- 無人承接的兜底路徑

## §4 風險

| 風險 | 說明 |
|---|---|
| 併發承接做錯 | 一單兩人接 → 現場衝突、重複結算。**最高風險** |
| 隔離假設被破壞 | offer 若帶品牌資訊給非授權師傅，直接違反 ADR-041 的競爭隔離前提 |
| 投影延遲 | 師傅看到的 offer 已被搶走，體驗劣化且客訴難解釋 |
| 雙模式狀態機互撞 | 指派與搶單兩套流程共用 work_order 狀態，容易產生無法回復的中間態 |
| 公平性爭議 | 沒有可稽核的釋出規則，師傅會質疑派單不公 |

## §8 Human Decisions Required 🛑

> **以下未填寫前不得動 code。**

1. 🛑 **逾時門檻**：指派後多久釋出到公開池？是否分級（第二順位 → 公開）？
2. 🛑 **公開池可見範圍**：所有具資格師傅同時可見，還是分批／依評分順序釋出？
3. 🛑 **品牌是否可限定**「只釋出給我的授權師傅」，或允許釋出給平台全池？
4. 🛑 **無人承接的兜底**：退回品牌人工處理、升級平台代派，還是自動放寬條件重試？
5. 🛑 **佣金歸屬**：搶單成交的抽成是否與指派成交相同？原指派師傅逾時未接是否有記錄／影響其後續排序？
6. 🛑 **上線範圍**：先在單一品牌試行，還是全平台同時開？

## §9 Suggested Implementation Order（待 §8 裁決後才啟動）

1. ⬜ S0：本 CIA §8 裁決 → offer domain model 與狀態機定版（新 ADR）
2. ⬜ S1：schema + 原子承接（併發測試先行，TDD）
3. ⬜ S2：API contract（釋出／查詢／承接／放棄／撤回）＋ 409 conflict
4. ⬜ S3：資格過濾與公平性規則 ＋ 負向契約測試（跨品牌不可見）
5. ⬜ S4：投影到 technician-platform（依 ADR-043）＋ 延遲 SLI
6. ⬜ S5：師傅端 UI（承接為 server-confirmed，禁 optimistic）
7. ⬜ S6：結算與佣金歸屬
8. ⬜ S7：單品牌試行 → 觀察 → 全平台

## §10 進度

- 2026-07-28：CIA 建檔。**未動任何 code。** 等待 §8 六項裁決。
