# Feature 層定義（G3）— 業務能力錨點

> 狀態：**2026-08-08 審核通過**，已是拆解樹 L1/L2 的現行定義。
> 機讀來源：`_feature_taxonomy.yaml`；對帳：`uv run python _validate_taxonomy.py`。
> 本檔為生成物，不要手改——改 yaml 再重跑 `--md`。
> 改動 yaml 等於改動四本 xlsx 與 Plane 的拆解樹，改完必須重跑 `_build_workbooks.py`。

## 為什麼是新的一套

| 代 | Feature 的定義 | 為什麼不用 |
|:---|:---|:---|
| G1（2026-07-30）| 32 個 `子系統·模組` 能力群 | 技術切法 |
| G2（2026-08-05）| 19 條 SC 旅程 ＋ 18 個 NFR category 地板 | 情境切法＋品質屬性切法，FR 與 NFR 被拆到樹的兩側 |
| **G3（現行）** | **業務能力（做什麼）** | — |

G3 的主要收益是 **FR 與 NFR 掛同一組**：一個能力的功能面與品質面不分家。附帶效果是 G2 時代那 32 條「判不出主旅程」的 FR 全部有了 parent——衝突的成因（一條 FR 服務多條旅程、樹上 parent 只能有一個）隨錨點更換而消失。

4 個 Epic／18 個 Feature，蓋滿 65 FR + 106 NFR = 171 個 Story。

## 總表

| Epic | Feature | 一句話 | FR | NFR |
|:---|:---|:---|---:|---:|
| E-SERVE 服務交付鏈 | `CAP-CONV` 智慧客服對話 | LINE 進線、對話編排、記憶、知識取用到轉真人的完整對話能力。 | 9 | 11 |
| E-SERVE 服務交付鏈 | `CAP-CASE` 報修建卡 | 從對話收斂成一張確認過的問題卡，含 agent 旁路寫入。 | 2 | 2 |
| E-SERVE 服務交付鏈 | `CAP-QUOTE` 報價與計費 | 報價生命週期、定價規則、保固判定與現場範圍變更後的重新報價。 | 4 | 0 |
| E-SERVE 服務交付鏈 | `CAP-DISP` 派工媒合 | 工單成立、自動與手動派工、媒合演算、接單與 SLA 治理。 | 6 | 6 |
| E-SERVE 服務交付鏈 | `CAP-FIELD` 現場作業與結案 | 技師到府、存證、結案閘門與排班生命週期。 | 4 | 2 |
| E-SERVE 服務交付鏈 | `CAP-MONEY` 收付與結算 | 消費者付款、退款取消、月結七帳本與技師佣金結算。 | 4 | 1 |
| E-SERVE 服務交付鏈 | `CAP-EXCEPT` 例外治理與稽核 | 例外審批 SoD、急件事後補審、稽核軌跡的檢視與匯出。 | 3 | 2 |
| E-SUPPLY 供給側能力 | `CAP-TECHID` 技師身分與准入 | 跨租戶技師身分、KYC 認證准入與撤銷停權。 | 2 | 1 |
| E-SUPPLY 供給側能力 | `CAP-KNWLC` 知識生命週期 | 素材汲取、LLM 提煉、HITL 審核、雙路發佈與 SOP 雙審。 | 5 | 13 |
| E-TENANT 租戶與治理 | `CAP-TENANT` 租戶開通與治理 | 品牌 License 開通、工單積木配置與平台維運 console。 | 3 | 3 |
| E-TENANT 租戶與治理 | `CAP-IAM` 身分與權限 | 統一身分、RBAC enforce、路由授權與服務間認證加密。 | 4 | 10 |
| E-TENANT 租戶與治理 | `CAP-PRIV` 隱私與資料主體權利 | PII 分類保存、GDPR 被遺忘權、跨租戶隔離與金鑰輪替。 | 1 | 11 |
| E-TENANT 租戶與治理 | `CAP-WORKBENCH` 營運與客戶介面 | 多 portal 外殼、派工工作台、報表與消費者追蹤頁。 | 5 | 7 |
| E-CORE 平台基座 | `CAP-MODEL` 模型與 AI 治理 | 供應商路由、工具白名單、AI 紅線與租戶可調的 agent 配置。 | 4 | 12 |
| E-CORE 平台基座 | `CAP-DATA` 資料基座 | Medallion 分層、forward-only migration、三庫隔離與語料唯一事實。 | 5 | 3 |
| E-CORE 平台基座 | `CAP-EVENT` 事件與即時骨幹 | Kafka 事件骨幹、Redis 即時層、WS 推播與背景批次。 | 3 | 5 |
| E-CORE 平台基座 | `CAP-OPS` 可觀測性與交付工程 | OTel、告警、runbook、rollback 與測試／契約治理。 | 1 | 12 |
| E-CORE 平台基座 | `CAP-BASE` 全系統服務基線 | 不屬於任何單一能力的全域可用性、併發與錯誤率門檻。 | 0 | 5 |

## 逐條歸屬

### `CAP-CONV` 智慧客服對話

LINE 進線、對話編排、記憶、知識取用到轉真人的完整對話能力。

隸屬 `E-SERVE` 服務交付鏈

**FR（9）**

- `FR-AGT-01` LINE 進線與驗簽
- `FR-AGT-02` Turn 狀態機對話編排
- `FR-AGT-03` 三層解決 + Clarify gate
- `FR-AGT-04` 急件偵測強制轉真人
- `FR-AGT-05` transfer_to_human 唯一出口 + 兜底
- `FR-AGT-06` per-user 記憶 BUILD/SAVE
- `FR-AGT-07` 知識取用（Skill 行為驅動 + RAG 檢索）
- `FR-AGT-09` 人工接管（CS takeover）
- `FR-AGT-10` 進線 debounce / dedup

**NFR（11）**

- `NFR-Perf-001` LINE AI 首回應 latency
- `NFR-Perf-002` 案例庫向量搜尋
- `NFR-Perf-003` RAG pipeline 端到端
- `NFR-Perf-012` LLM 呼叫逾時上限
- `NFR-Avail-003` LINE webhook 成功率
- `NFR-Avail-004` LINE webhook ack latency
- `NFR-Avail-005` Webhook autoscale
- `NFR-Avail-006` Webhook 非同步處理
- `NFR-A11y-001` LINE 端
- `NFR-Sec-010` webhook 驗簽
- `NFR-Comp-001` 合約 4.4(a) 負面情緒識別

### `CAP-CASE` 報修建卡

從對話收斂成一張確認過的問題卡，含 agent 旁路寫入。

隸屬 `E-SERVE` 服務交付鏈

**FR（2）**

- `FR-API-01` 問題卡收斂與確認
- `FR-API-13` internal ingest（agent 旁路）

**NFR（2）**

- `NFR-Rel-003` 案子不蒸發
- `NFR-Scal-004` ProblemCard 累積（3-5 年）

### `CAP-QUOTE` 報價與計費

報價生命週期、定價規則、保固判定與現場範圍變更後的重新報價。

隸屬 `E-SERVE` 服務交付鏈

**FR（4）**

- `FR-API-02` 報價生命週期
- `FR-API-03` 定價引擎（pricing sub-module）
- `FR-API-17` 保固判定
- `FR-TEC-07` 現場報價修正發起（requote command）

**NFR**：無

### `CAP-DISP` 派工媒合

工單成立、自動與手動派工、媒合演算、接單與 SLA 治理。

隸屬 `E-SERVE` 服務交付鏈

**FR（6）**

- `FR-API-04` 工單建立（CS 1-click）
- `FR-API-05` 自動派工
- `FR-API-06` 手動派工 + 覆寫稽核
- `FR-API-07` 接單 SLA 治理
- `FR-TEC-03` OHS 派工媒合
- `FR-TEC-04` 接單 / 拒單 + 即時推播

**NFR（6）**

- `NFR-Perf-007` OHS 派工媒合 POST /technicians:match
- `NFR-Perf-008` 派工推播（指派事件 → 技師收到）
- `NFR-SLA-001` 派工→技師抵達 SLA（soft）
- `NFR-SLA-002` SLA breach 邊界
- `NFR-SLA-003` SLA alert fallback
- `NFR-Scal-008` 大量技師併發上線/接單不卡頓

### `CAP-FIELD` 現場作業與結案

技師到府、存證、結案閘門與排班生命週期。

隸屬 `E-SERVE` 服務交付鏈

**FR（4）**

- `FR-API-08` 到府存證（照片/簽名/材料）
- `FR-API-09` 結案 hard gate
- `FR-TEC-05` 技師視角工單投影（CQRS）
- `FR-TEC-08` 排班與生命週期管理

**NFR（2）**

- `NFR-Aud-003` Evidence retention
- `NFR-Scal-005` Evidence 儲存（3-5 年）

### `CAP-MONEY` 收付與結算

消費者付款、退款取消、月結七帳本與技師佣金結算。

隸屬 `E-SERVE` 服務交付鏈

**FR（4）**

- `FR-API-10` 消費者付款
- `FR-API-11` 退款 / 取消費
- `FR-API-12` 月結與 7 帳本
- `FR-TEC-06` 佣金結算主體（Settlement）

**NFR（1）**

- `NFR-Aud-002` 7 帳本

### `CAP-EXCEPT` 例外治理與稽核

例外審批 SoD、急件事後補審、稽核軌跡的檢視與匯出。

隸屬 `E-SERVE` 服務交付鏈

**FR（3）**

- `FR-API-18` 例外審批收件匣 + SoD
- `FR-API-19` 急件事後補審引擎
- `FR-WEB-05` 稽核日誌檢視與匯出

**NFR（2）**

- `NFR-Aud-001` 全變更 audit log
- `NFR-Aud-007` Read-side access log

### `CAP-TECHID` 技師身分與准入

跨租戶技師身分、KYC 認證准入與撤銷停權。

隸屬 `E-SUPPLY` 供給側能力

**FR（2）**

- `FR-TEC-01` 技師註冊（跨租戶身分）
- `FR-TEC-02` KYC / 認證准入

**NFR（1）**

- `NFR-Avail-007` 技師平台 HA

### `CAP-KNWLC` 知識生命週期

素材汲取、LLM 提煉、HITL 審核、雙路發佈與 SOP 雙審。

隸屬 `E-SUPPLY` 供給側能力

**FR（5）**

- `FR-REF-01` 診斷對話 + 素材汲取
- `FR-REF-02` LLM 提煉分流
- `FR-REF-03` HITL 審核硬 gate
- `FR-REF-04` Publisher 雙路落地
- `FR-REF-05` SOP 雙審 + Family Reviewer

**NFR（13）**

- `NFR-DQ-001` 知識來源可信度
- `NFR-DQ-002` Provenance 正確性
- `NFR-DQ-003` Pipeline 冪等
- `NFR-DQ-004` 審核品質
- `NFR-PUB-001` 未核可零落地
- `NFR-PUB-002` append-only 落地
- `NFR-PUB-003` references ↔ pgvector 同源
- `NFR-PUB-004` 語料租戶隔離
- `NFR-Rep-001` Pipeline 可重現
- `NFR-Rep-002` raw → bronze 可重建
- `NFR-Comp-002` 合約 4.4(d) 家族覆核
- `NFR-Aud-004` Family Reviewer 紀錄
- `NFR-Maint-007` 知識可攜性

### `CAP-TENANT` 租戶開通與治理

品牌 License 開通、工單積木配置與平台維運 console。

隸屬 `E-TENANT` 租戶與治理

**FR（3）**

- `FR-PLT-03` License 開通與 provisioning
- `FR-PLT-07` 工單積木引擎（平台核心）
- `FR-PLT-09` 平台維運 console

**NFR（3）**

- `NFR-Scal-006` Tenant（品牌）數
- `NFR-Scal-007` 多品牌線性擴展
- `NFR-Perf-004` 品牌後台頁面（Admin）

### `CAP-IAM` 身分與權限

統一身分、RBAC enforce、路由授權與服務間認證加密。

隸屬 `E-TENANT` 租戶與治理

**FR（4）**

- `FR-PLT-01` 統一身分（Casdoor）
- `FR-PLT-02` RBAC enforce
- `FR-WEB-02` 認證與路由授權
- `FR-DAT-06` 統一身分與稽核基座

**NFR（10）**

- `NFR-Sec-001` 傳輸加密
- `NFR-Sec-002` 認證
- `NFR-Sec-003` 授權
- `NFR-Sec-004` At-rest 加密
- `NFR-Sec-011` 服務間認證
- `NFR-Sec-013` Secrets 管理
- `NFR-Sec-014` CVE 回應
- `NFR-Avail-008` Casdoor HA
- `NFR-Avail-010` 認證降級
- `NFR-Scal-003` 註冊用戶容量（3-5 年）

### `CAP-PRIV` 隱私與資料主體權利

PII 分類保存、GDPR 被遺忘權、跨租戶隔離與金鑰輪替。

隸屬 `E-TENANT` 租戶與治理

**FR（1）**

- `FR-API-16` GDPR forget 流程

**NFR（11）**

- `NFR-Priv-001` PII 分類
- `NFR-Priv-002` PII retention default
- `NFR-Priv-003` RMA / 客訴 retention
- `NFR-Priv-004` 法律相關 retention
- `NFR-Priv-005` GDPR forget
- `NFR-Priv-006` 跨租戶隔離
- `NFR-Priv-007` DEK rotation
- `NFR-Priv-008` Two-phase purge
- `NFR-Priv-009` 觀測資料 PII
- `NFR-Priv-010` 跨系統投影最小化
- `NFR-Comp-004` GDPR / 個資法

### `CAP-WORKBENCH` 營運與客戶介面

多 portal 外殼、派工工作台、報表與消費者追蹤頁。

隸屬 `E-TENANT` 租戶與治理

**FR（5）**

- `FR-WEB-01` APP_MODE 多 portal
- `FR-WEB-03` 派工工作台
- `FR-WEB-04` 儀表板與報表
- `FR-WEB-06` 消費者追蹤頁（LIFF）
- `FR-WEB-07` 錯誤 / 離線頁

**NFR（7）**

- `NFR-A11y-002` 全部 Web portal（dispatch / tech / platform / landing / LIFF）
- `NFR-A11y-003` 對比
- `NFR-A11y-004` 鍵盤導覽
- `NFR-A11y-005` Screen reader
- `NFR-Perf-005` 讀取類 API 回應
- `NFR-Perf-011` web 首次內容繪製 FCP
- `NFR-Maint-005` 前端型別安全

### `CAP-MODEL` 模型與 AI 治理

供應商路由、工具白名單、AI 紅線與租戶可調的 agent 配置。

隸屬 `E-CORE` 平台基座

**FR（4）**

- `FR-AGT-08` 工具白名單治理
- `FR-AGT-11` AI 邊界（金額/影像）
- `FR-PLT-05` Model Orchestration Layer
- `FR-PLT-08` Agent Configuration Studio

**NFR（12）**

- `NFR-Sec-005` Prompt injection 攔截率
- `NFR-Sec-006` 內容過濾誤攔率
- `NFR-Sec-007` Output Guardrail
- `NFR-Sec-008` AI Forbidden Eval
- `NFR-Sec-009` 影像辨識禁用（SOW 2.1(4)）
- `NFR-Sec-012` 工具沙箱
- `NFR-Comp-003` SOW 2.1(4) 影像辨識禁用
- `NFR-Aud-005` AI 決策可追溯
- `NFR-Aud-006` Config change audit
- `NFR-Maint-002` 供應商解耦
- `NFR-Perf-010` Agent Config Studio config read（cache hit）
- `NFR-Obs-005` Staged rollout（config）

### `CAP-DATA` 資料基座

Medallion 分層、forward-only migration、三庫隔離與語料唯一事實。

隸屬 `E-CORE` 平台基座

**FR（5）**

- `FR-DAT-01` Medallion 分層
- `FR-DAT-02` 純 SQL forward-only migration
- `FR-DAT-03` 三庫物理隔離
- `FR-DAT-04` pgvector 唯一事實語料
- `FR-DAT-05` 跨系統同步鏈

**NFR（3）**

- `NFR-Sch-001` Migration 可重套
- `NFR-Sch-002` 套用真相可查
- `NFR-Sch-003` 演進策略

### `CAP-EVENT` 事件與即時骨幹

Kafka 事件骨幹、Redis 即時層、WS 推播與背景批次。

隸屬 `E-CORE` 平台基座

**FR（3）**

- `FR-PLT-04` 事件骨幹（Kafka）+ 即時層（Redis）
- `FR-API-14` 即時推播（WS）
- `FR-API-15` 背景批次（11 cron worker）

**NFR（5）**

- `NFR-Avail-009` Kafka 事件最終一致
- `NFR-Avail-011` 即時通道降級
- `NFR-Perf-006` WS 推播延遲（事件 → 訂閱者）
- `NFR-Perf-009` Outbox → 事件骨幹 lag
- `NFR-Rel-002` DLQ 處理

### `CAP-OPS` 可觀測性與交付工程

OTel、告警、runbook、rollback 與測試／契約治理。

隸屬 `E-CORE` 平台基座

**FR（1）**

- `FR-PLT-06` 可觀測性分層

**NFR（12）**

- `NFR-Obs-001` OTel 接入覆蓋
- `NFR-Obs-002` Alert MTTA
- `NFR-Obs-003` Runbook 覆蓋
- `NFR-Obs-004` Rollback 時間
- `NFR-DORA-001` Lead time
- `NFR-DORA-002` Change Failure Rate
- `NFR-DORA-003` MTTR
- `NFR-Maint-001` 後端測試覆蓋率
- `NFR-Maint-003` OpenAPI additive-only
- `NFR-Maint-004` ADR coverage
- `NFR-Maint-006` 跨系統契約測試
- `NFR-Maint-008` E2E 覆蓋

### `CAP-BASE` 全系統服務基線

不屬於任何單一能力的全域可用性、併發與錯誤率門檻。

隸屬 `E-CORE` 平台基座

**FR**：無

**NFR（5）**

- `NFR-Avail-001` 系統 Uptime
- `NFR-Avail-002` 系統 Uptime
- `NFR-Scal-001` V1 併發
- `NFR-Scal-002` V2 併發
- `NFR-Rel-001` Error rate

