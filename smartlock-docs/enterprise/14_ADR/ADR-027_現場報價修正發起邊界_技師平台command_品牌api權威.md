# ADR-027: 現場報價修正發起邊界——技師平台只發 command、品牌 api 為報價唯一權威

## Status

Accepted（業主裁決 2026-07-07）

## Context

現場報價修正輪(工單 `on_site → quoted → approved`)需要**技師**發起 quote v+1,但相關能力分屬兩個物理隔離的系統:

- **報價 / 定價**是品牌 api 內的獨立 bounded context(BR-PRICING-01):quote 主表、定價引擎、不可變快照(`pricing_rule_snapshot`)、LIFF 客戶確認鏈全在**品牌庫**。
- **技師**是跨租戶共享身分,工作台與帳號在 **technician-platform**(ADR-016 / ADR-P004);技師平台對工單只有唯讀 CQRS 投影,**不跨庫雙寫**(ADR-017 / ADR-P014)。

問題:多租戶品牌方架構下,技師在誰的系統、以什麼身分、寫進哪個庫發起報價修正?且現場情境(客戶在旁等待)要求**同步即時**回饋。

## Decision

**技師平台只發起「修正請求 command」,品牌 api 是報價的唯一寫入權威。**

1. **發起端(technician-platform)**:技師於師傅 web 對「派給自己且處 `on_site` / `in_progress`」的工單發起修正請求,附**事由分類**(估價誤差 / 加價 / 改項)與**項目 / 料件 diff 草稿**——技師**不定價**,只提交異動內容。tech-api 驗 `assignee_ref` = 該技師 + 工單狀態,不符 403。
2. **傳輸通道(OHS 同步反向呼叫)**:tech-api 依 tenant 路由表呼叫對應品牌 api `POST /internal/requote-requests`(service-to-service 認證 + `request_id` 冪等)。現場要即時,**不走事件佇列**;Kafka 事件僅用於後續工單投影同步(🔜 Phase 3)。
3. **執行端(品牌 api)**:報價引擎在品牌庫建 quote v+1(`supersedes_quote_id` 串鏈 + 新 `snapshot_hash`,金額由品牌定價引擎依 diff 計算)→ 分層核可(減價 / 同額直接送;加價 501–2000 小編核可、>2000 主管覆核)→ 客戶 LIFF 確認(fallback QR / 紙本)→ 工單 `on_site → quoted → approved`。保固 / 建案案件禁自動送出(BR-QUOTE-03)由品牌端 enforce。
4. **回饋端**:報價 / 工單狀態變更經工單 CQRS 投影回技師工作台(Phase 1 以 OHS 查詢輪詢;🔜 Phase 3 Kafka `workorder.updated`)。

## Alternatives Considered

- **技師直連品牌 api**:跨租戶技師帳號打進 per-brand bundle,破壞品牌隔離邊界與 Casdoor 身分模型(技師不隸屬品牌租戶);每加一個品牌就要多發一組品牌內憑證。否決。
- **事件佇列非同步發起**:現場客戶等待,秒級回饋是硬需求;且 Phase 1 尚無 Kafka。否決(保留為通道故障時的降級緩衝)。
- **報價複本放技師平台**:跨庫雙寫,直接違反 ADR-017 的 Billing / Settlement 邊界與投影唯讀原則。否決。

## Consequences

- OHS API 新增 requote-request 通道;**tenant 路由表**(technician-platform → 各品牌 api endpoint)成為關鍵配置,納入部署檢查。
- 品牌 api 對技師端金額**零信任**:只收 diff,定價一律引擎計算,防技師端喊價。
- 需冪等(`request_id`)與明確 403 條件(非 assignee / 狀態不符 / 保固建案自動送出)。
- 通道不可用時的降級:技師以電話回報小編,由小編在品牌後台代發 quote v+1(既有能力),audit 標記 `initiated_via=cs_fallback`。
- 重評觸發:第 2 產業 Vertical Pack 上線時,檢視 requote 事由分類是否需 pack 化。

## 追溯

- 上游:ADR-016(技師共享池)、ADR-017(佣金邊界與工單投影)、BR-PRICING-01/BR-QUOTE-03(../02_BRD.md §6.3)、業主裁決 2026-07-07(現場報價修正輪)。
- 下游:../15_SDS.md §4.4、../04_SRS.md FR-TEC-07、../16_API_Spec.yaml `/internal/requote-requests`、../20_Test_Cases.md TC-DISPATCH-07。
