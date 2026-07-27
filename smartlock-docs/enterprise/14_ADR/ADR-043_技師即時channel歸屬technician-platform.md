---
title: "ADR-043: 技師即時 channel 歸屬 technician-platform"
version: 1.0
status: active
owner: Technician Platform Owner / API Owner
last-updated: 2026-07-28
relates:
  - ./ADR-041_跨品牌技師身分單一平台principal加品牌membership.md
  - ./ADR-037_背景工作Runtime從API生命週期拆分.md
  - ./OPEN_DECISIONS.md
---

# ADR-043: 技師即時 channel 歸屬 technician-platform

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（2026-07-28 業主裁決）／遷移受 Redis／Kafka production 證據約束 |
| 層級 | 平台級（realtime / bounded context） |
| 關聯 ADR | [ADR-041](./ADR-041_跨品牌技師身分單一平台principal加品牌membership.md) · [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) · ADR-016／017／022 |
| 承接決策 | [OD-003](./OPEN_DECISIONS.md#od-003--技師即時-websocket-的權威歸屬)（本 ADR 使其 `decided`） |
| WBS | 3.1.2 · 3.6.6 |

## Context（背景與問題）

現況：tech portal 連的是**品牌 API** 的 WebSocket。程式有 Redis bridge 與 technician
event consumer，但 `REDIS_URL`／`KAFKA_BOOTSTRAP` 都沒有 production 證據，SDS 已標註
不把 interim 當 target。

2026-07-28 業主確認產品形態：**師傅在單一 app 內看到多個品牌／經銷商的接案需求**
（Uber 式的聚合視圖）。這個形態直接否定了「各品牌 API 各自持有師傅 channel」——師傅
的 app 會被迫同時連 N 條線，而且沒有任何一方有能力組出那份統一清單。

## Decision（決策）

1. **technician-platform 持有師傅專屬 channel**（`/realtime/pool/{tech_id}` 類），
   包含跨品牌的接案需求、指派通知與技師自身狀態變更。
2. **brand API 只保留品牌營運 channel**（品牌後台自己看的即時看板、工單狀態流）。
3. **禁止同一事件長期雙播而無 owner**。遷移期間若必須雙送，須有明確 owner 標記與
   收斂期限，並以 metric 監控雙送重複率。
4. **channel 授權依 ADR-041**：師傅為單一平台 principal，channel 授權以 principal ＋
   已授權 brand scope 判定，不以品牌前端的 tenant fallback 決定。
5. **遷移順序**：先定 event schema 與 replay 語義並驗證，再遷 portal 連線；不先改前端。

## Scope（本 ADR 不涵蓋什麼）

**本裁決只涵蓋 channel 歸屬，不涵蓋派工模式本身。**

業主同日另確認派工要採「**指派為主、搶單為輔**」——先指派給選定師傅，逾時未接則釋出
到公開池由其他師傅承接。該混合模式**在現行 code 完全不存在**：`dispatch_service` 只有
候選師傅的 GIS／評分排序（`listDispatchCandidates`），派工模式僅
`manual`／`platform_paid`／`auto_match` 三種，**師傅端沒有 accept／reject／搶單任何動作**。

該模式屬產品層變更，需要 offer 生命週期、搶單併發控制、公平性規則與無人承接的兜底，
**須另開 CR 走 CIA，不得以本 ADR 代替**。本 ADR 只保證：當該模式實作時，承載它的即時
通道已經有明確 owner。

## Alternatives（考量的選項）

- **A：brand API 持有師傅 channel（現況）** — 貼近工單 command 真相，但在多品牌聚合視圖
  下會逼師傅 app 跨面連 N 條線，且與 ADR-041「技師身分只有一份」不一致。不採。
- **B：technician-platform 持有（採用）** — 貼近技師 identity 與投影，需保證投影延遲、
  replay 與品牌事件契約。
- **C：中間 gateway 聚合層** — 可統一通道授權，但新增部署與故障域；在只有兩個來源時
  不成比例，且有成為「未受監控的第四份投影」的風險。不採。

## Consequences（後果）

- ＋師傅 app 只連一條線，與單一平台身分一致。
- ＋跨品牌聚合清單有唯一 owner，不需要前端拼裝。
- ＋WBS 3.1.2（技師工作台改吃 CQRS 投影）有了明確的歸屬前提。
- －**投影延遲成為產品 SLA**：品牌工單事件要及時到達技師平台，否則師傅看到的是舊資料。
- －**硬前置未解除**：Redis（跨實例 WS fan-out）與 Kafka（品牌事件投影）目前皆為休眠
  opt-in，兩者沒有 production 證據前，API 不得提高 max instances，也不得宣稱跨 instance
  的技師即時派工 SLA（此為 OD-003 原 decision gate，本 ADR 不解除）。
- －遷移期前後端都要能 rollback，需 feature flag 與雙送觀察期。

**完成門檻**：兩實例與斷線復原 SIT 通過；channel 授權矩陣有負向測試；事件延遲預算可量測；
無同一事件長期雙播。

## 重評觸發

- 品牌營運 channel 與師傅 channel 出現大量重複事件（暗示 owner 切錯）。
- 搶單模式落地後，offer 的即時性需求超出目前投影延遲預算。
- 出現第三類即時消費者（例如經銷商端），使雙 channel 模型不足。
