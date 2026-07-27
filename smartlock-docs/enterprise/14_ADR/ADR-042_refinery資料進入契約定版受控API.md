---
title: "ADR-042: knowledge-refinery 資料進入契約定版為受控 API"
version: 1.0
status: active
owner: Data Owner / Knowledge Refinery Owner
last-updated: 2026-07-28
relates:
  - ./ADR-018_知識精煉獨立服務.md
  - ./ADR-036_機器身分與可撤銷服務憑證.md
  - ./ADR-040_OHS服務間憑證定版受控opaque credential.md
  - ./OPEN_DECISIONS.md
---

# ADR-042: knowledge-refinery 資料進入契約定版為受控 API

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（2026-07-28 業主裁決）／intake 端點與直讀退場為待實作 |
| 層級 | 平台級（data boundary / product） |
| 關聯 ADR | [ADR-036](./ADR-036_機器身分與可撤銷服務憑證.md) · [ADR-040](./ADR-040_OHS服務間憑證定版受控opaque credential.md) · [ADR-018](./ADR-018_知識精煉獨立服務.md)／019／029／030 |
| 承接決策 | [OD-002](./OPEN_DECISIONS.md#od-002--knowledge-refinery-的資料進入契約)（本 ADR 使其 `decided`） |
| WBS | M3.1（事件骨幹）· 3.3.1／3.5.1（開站自動化）|

## Context（背景與問題）

OD-002 原本的技術建議是「M2 用最小權限唯讀／批次入口，M3 Kafka 成熟後切為事件主路徑」。
該建議成立的前提是 **refinery 為內部工具**。

2026-07-28 業主確認了一項改變前提的商業事實：**refinery 是要賣給品牌的收費附加服務，
已列入 product roadmap**。OD-002 的 decision gate 本身就寫明「在把 Refinery 標為 License
可售附加服務前，必須選定一條主入口」——條件觸發了。

AS-BUILT 盤點出一個關鍵不對稱：

| 方向 | 現況 |
|---|---|
| refinery **寫回**品牌 | 已走受控 API + `X-Service-Credential`（`refinery/apply_behavior.py`）|
| refinery **讀取**品牌 | 直連資料庫（`REFINERY_POSTGRES_URI`，讀 `messages`／`problem_cards`／`knowledge_drafts`／`tenant`，`REFINERY_TENANT_ID` default-deny）|

寫的半邊已經完成 API 化，只有讀的半邊還掛著裸 DB 連線。

## Decision（決策）

**定版受控 API 為 refinery 取得品牌資料的唯一主入口。**

1. **refinery 以自己的 service principal 呼叫品牌 API 的 intake 端點**，依 ADR-036／040
   的憑證生命週期：per-workload principal、audience／scope／tenant、expiry、rotation、
   revoke、逐次 audit。
2. **intake 端點須提供**：明確 DTO（資料最小化，不是 `SELECT *` 的轉寫）、cursor 分頁、
   增量水位（只取上次之後）、逐筆 provenance、刪除語義，以及**逐租戶用量計量**。
3. **直讀 DB 標為 interim**，處置方式比照 `X-Internal-Token`：加使用量計數，production
   使用量歸零後移除 `REFINERY_POSTGRES_URI` 路徑。
4. **Kafka／outbox 是日後的量能與延遲優化，不是契約載體**。在 `KAFKA_BOOTSTRAP` 取得
   production 證據前，不得讓事件路徑承載這條資料流；導入後 API 仍為契約面，事件為傳輸
   優化，**不允許兩條入口同時無規則並存**。

## Rationale（為什麼推翻原建議）

**收費產品的資料汲取必須是契約，不能是一條資料庫連線。** 四個具體理由：

1. **開站會被拖垮**。每品牌物理分庫，而 `REFINERY_TENANT_ID` 是一個 process 綁一個租戶。
   賣給 N 個品牌 ＝ N 條連線字串 ＋ N 個 process ＋ N 條網路路徑，直接撞上 WBS 3.3.1
   （License → provisioning 自動化）與 3.5.1（第 2 品牌開站演練）。
2. **收費需要計量**。DB 連線沒有天然計費點；API 呼叫有。「這個月為某品牌汲取了多少」
   在直讀模式下無法回答。
3. **賣出後 schema 即成契約**。品牌端一次 migration 就可能靜默打壞一個付費產品，而且
   沒有契約測試守著這條線。
4. **DPA 義務**。銷售意味資料處理責任：來源可稽核、逐筆 provenance、「汲取了哪些、能否
   刪除」。API intake 有 audit trail，直讀沒有。

而選 API 的成本比想像低——寫回路徑已經走完同一條路，本決策是把讀取路徑收尾，不是新工程。

## Alternatives（考量的選項）

- **A：唯讀帳號／批次匯出正規化** — 若 refinery 是內部工具，這是最省的選擇（也是 OD-002
  的原建議）。收費前提下 4 項理由全部不成立，不採。
- **B：Kafka／outbox 為主入口** — 耦合最低，但基建未取證，且把付費產品建立在休眠的
  opt-in 上是把風險前置。不採為契約載體。
- **C：受控 API 為主入口（採用）** — 契約明確、可授權、可稽核、可計量；批次效能以 cursor
  ＋增量水位補足。

## Consequences（後果）

- ＋refinery 成為受治理的 API consumer，逐租戶授權與計量都有落點。
- ＋品牌開站不需要再為 refinery 額外配 DB 憑證與網路路徑。
- ＋intake DTO 強制資料最小化，PII 面比直讀四張表小。
- －**批次讀取會比直連 DB 慢**，需 cursor 分頁與增量水位；refinery 是批次煉製非即時查詢，
  此延遲可接受，但需納入效能驗收。
- －需新增並維護一組 intake 端點與 DTO；屬 API contract 變更，走 CIA。
- －過渡期間直讀與 API 並存，必須以 usage metric 防止直讀常態化。

**完成門檻**：refinery 全部讀取走 API；每次 intake 可辨識 principal 與 tenant 並留 audit；
逐租戶用量可計量；`REFINERY_POSTGRES_URI` 使用量連續一個 release window 為零後移除。

## 重評觸發

- intake 量成長到 API 分頁成為瓶頸（此時導入 Kafka 作為傳輸優化，契約面不變）。
- refinery 需要近即時汲取（目前為批次假設）。
- 出現非本平台部署的 refinery 實例（會使憑證與網路邊界重新成為問題）。
