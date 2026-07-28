---
title: 情境脊椎 (Scenario Spine)
doc_id: "28"
version: v1.0
last_updated: 2026-07-27
status: active
owner: PM / BA
sync-source: doc
---

# 情境脊椎 — Smart Lock AI 客服與派工 SaaS 平台

> **這份文件的角色**：全平台唯一的 `SC-*` 節點正典。所有規格產物（驗收控制表、BOM、
> 整合測試計畫、規格統控規劃書）的縱向脊椎都是這裡的 `SC` ID。
>
> **這份文件不做的事**：不列任何 `FR-*` / `NFR-*` / `TC-*`。
> 「哪條旅程需要哪條需求」是一條 **M:N 的邊**，只能住在
> [`規格統控整理/_relations/sc_requires_rq.yaml`](./規格統控整理/_relations/sc_requires_rq.yaml)。
> 在這裡再列一份，等於製造第二個可寫入的地方，那就等於沒有真相源。

---

## 0. 為什麼需要這一層

在本文件成立之前，平台有四套互相競爭的「情境」編號：

| 來源 | 編號 | 數量 | 視角 | 現在的定位 |
|:---|:---|:---|:---|:---|
| `07_Journey_Map.md` | 旅程 A–E | 5 | 角色旅程（太粗）| 降級為 `SC` 的**分線**（L1）|
| `08_User_Flow.md` | UF-01–UF-10 | 10（+12 例外）| 系統流程（非客戶語言）| 降級為 `SC` 的**流程細節**參照 |
| `19_Test_Plan.md` | TS-01–TS-12 | 12 | QA 事後歸納 | 降級為 `SC` 的**測試投影** |
| `22_UAT_Report.md` | UAT-01–UAT-05 | 5 | UAT 腳本 | 降級為 `SC` 的**驗收腳本** |

同一段旅程被寫了四次、四種粒度、四個 owner。這是「拿到規格不知道從哪下手」的根因——
讀者找不到脊椎。本文件把脊椎定死在 `SC-*`，其餘四套全部成為它的投影或別名。

### 一句話定義

> **Scenario（`SC-*`）＝ 一段有明確觸發事件、有明確完成判定、由單一主要 Actor 感知得到的完整旅程。**

判準：
- 只能問「這個順不順？」→ 是 `SC`。
- 能問「這個做完了沒？」→ 那是 `FR`／`NFR`，不屬於本文件。
- 句子裡有「然後 / 接著 / 如果失敗就」→ `SC`。有「必須 / 不得 / 在 X 之內」→ `RQ`。

---

## 1. 分線與清單

五條分線（沿用 `07_Journey_Map` 的價值鏈主軸），19 條 `SC`：

```
L1-CUS 終端客戶   SC-01 → SC-02 → SC-03 → SC-04 → SC-05 → SC-06 → SC-07 → SC-08 → SC-09
L1-OPS 品牌營運                   SC-10   SC-11
L1-TEC 簽約師傅                   SC-12 → SC-13   SC-14
L1-KNW 知識治理                   SC-15 → SC-16
L1-PLT 平台治理                   SC-17 → SC-18   SC-19
```

| SC | 名稱 | 主要 Actor | 分線 | 優先級 |
|:---|:---|:---|:---|:---|
| SC-01 | 產品疑問自助解決（不建卡）| 終端客戶 | L1-CUS | P0 |
| SC-02 | 故障報修到問題卡成立 | 終端客戶 | L1-CUS | P0 |
| SC-03 | 急件強制轉真人 | 終端客戶 | L1-CUS | P0 |
| SC-04 | 報價確認到工單成立 | 終端客戶 × 派工小編 | L1-CUS | P0 |
| SC-05 | 派工媒合到技師接單 | 派工小編 × 簽約師傅 | L1-CUS | P0 |
| SC-06 | 現場施工到完工結案 | 簽約師傅 × 終端客戶 | L1-CUS | P0 |
| SC-07 | 現場範圍變更與報價修正 | 簽約師傅 × 終端客戶 | L1-CUS | P0 |
| SC-08 | 收款、取消與退款 | 終端客戶 × 派工小編 | L1-CUS | P0 |
| SC-09 | 月結與七帳本對帳 | 租戶 Admin | L1-CUS | P1 |
| SC-10 | 人工接管與對話不蒸發 | 派工小編 | L1-OPS | P0 |
| SC-11 | 例外審批與 SoD 收件匣 | 派工小編 × 租戶 Admin | L1-OPS | P0 |
| SC-12 | 技師註冊、KYC 到品牌授權 | 簽約師傅 × Super Admin | L1-TEC | P0 |
| SC-13 | 技師跨品牌對帳與佣金請領 | 簽約師傅 | L1-TEC | P1 |
| SC-14 | 認證撤銷與停權即時廣播 | Super Admin | L1-TEC | P0 |
| SC-15 | 知識精煉 HITL 到雙路發布 | 客服主管 × Domain Expert | L1-KNW | P0 |
| SC-16 | SOP 雙審與 Family Reviewer 覆核 | Domain Expert × Family Reviewer | L1-KNW | P0 |
| SC-17 | 品牌申請到 License 開通上線 | 加盟品牌 × Super Admin | L1-PLT | P0 |
| SC-18 | 品牌自助配置與治理回滾 | 租戶 Admin | L1-PLT | P1 |
| SC-19 | GDPR 被遺忘權執行 | 終端客戶 × DPO | L1-PLT | P0 |

---

## 2. 橫切需求不逐條掛旅程

有一類需求不屬於任何單一旅程，而是**所有旅程共用的地板**：可用性、稽核鏈完整性、
跨租戶隔離、migration 可重現、可觀測性。

這類需求在 `sc_requires_rq.yaml` 標 `scope: global`，**不逐條偽造 `SC × RQ` 邊**。
為它們硬湊一段「客戶 VOC」是造假——客戶不會說「我希望你們的稽核 hash chain 完整」。

判斷法：**如果拿掉任何一條旅程，這條需求依然必須成立 → `scope: global`。**

---

## 3. 情境卡

每張卡的欄位固定五格。`完成判定`是驗收軸推進的唯一依據；`失敗與例外`是測試設計 `kind: failure|recovery` 的來源。

### L1-CUS 終端客戶線

#### SC-01 產品疑問自助解決（不建卡）

- **主要 Actor**：終端客戶（住戶）
- **觸發**：客戶加官方帳號後，詢問一般產品操作或知識問題（如換電池、恢復原廠設定）
- **主要步驟**：LINE 進線驗簽 → Turn 編排 → 案例庫／知識檢索命中 → 回答 → AI 主動確認「問題釐清了嗎」→ 客戶確認 → 對話結案
- **完成判定**：客戶問題被解答且**未產生問題卡**；回答內容與知識庫一致，無紅線違反
- **失敗與例外**：連續 3 次未釐清 → 自動升級轉真人（落入 SC-02）；詢價誘導 → 只給範圍價、不給確定金額；影像辨識請求 → 一律拒絕（僅存證）

> 這是進線量最大的一條旅程，卻最容易在規格裡被忽略——因為它「什麼都沒發生」。
> 它的驗收價值在於：**證明系統知道什麼時候不該建卡。**

<!-- BEGIN GENERATED BDD SC-01 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-01 @P0 @L1-CUS
Feature: SC-01 產品疑問自助解決（不建卡）

  As a 終端客戶（PER-CUS-01）
  I want 產品疑問自助解決（不建卡）
  So that 5 秒內看到 AI 回應；急件 5 分鐘內有真人接手；報價金額明確、確認後不被亂加價

  # 體現 Persona: PER-CUS-01 終端客戶（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-AGT-TURN-01, TC-COMPLIANCE-06, TC-CS-AI-03, TC-CS-AI-05, TC-CS-AI-06, TC-CS-AI-07, TC-CS-AI-08, TC-CS-AI-09, TC-CS-AI-11, TC-NFR-PERF-01, TC-PERF-01, TC-SEC-MEM-01, TC-SEC-TOOL-01

  @happy
  Scenario: 正常路徑 — 產品疑問自助解決（不建卡）
    Given 客戶加官方帳號後，詢問一般產品操作或知識問題（如換電池、恢復原廠設定）
    When LINE 進線驗簽
    And Turn 編排
    And 案例庫／知識檢索命中
    And 回答
    And AI 主動確認「問題釐清了嗎」
    And 客戶確認
    And 對話結案
    Then 客戶問題被解答且未產生問題卡
    And 回答內容與知識庫一致，無紅線違反

  @failure
  Scenario: 例外 — 連續 3 次未釐清
    Given 客戶加官方帳號後，詢問一般產品操作或知識問題（如換電池、恢復原廠設定）
    When 連續 3 次未釐清
    Then 自動升級轉真人（落入 SC-02）

  @failure
  Scenario: 例外 — 詢價誘導
    Given 客戶加官方帳號後，詢問一般產品操作或知識問題（如換電池、恢復原廠設定）
    When 詢價誘導
    Then 只給範圍價、不給確定金額

  @failure
  Scenario: 例外 — 影像辨識請求
    Given 客戶加官方帳號後，詢問一般產品操作或知識問題（如換電池、恢復原廠設定）
    When 影像辨識請求
    Then 一律拒絕（僅存證）
```
<!-- END GENERATED BDD SC-01 -->
#### SC-02 故障報修到問題卡成立

- **主要 Actor**：終端客戶
- **觸發**：客戶回報鎖具故障並要求派師傅
- **主要步驟**：AI 追問品牌／型號／地址 → 三層解決嘗試 → 判定需人工 → `transfer_to_human` → AI 草擬問題卡進後台 → 客服補全 → completeness ≥ 0.85 → confirmed
- **完成判定**：問題卡狀態為 `confirmed`，欄位與對話事實一致，badge 標示 AI 草擬來源
- **失敗與例外**：資料連 3 次收不齊 → 自動轉真人；地址缺失 → 不擋建卡，延後到結案硬擋；AI 承諾轉接卻未呼叫工具 → gateway 兜底補一筆 escalation（案子不得蒸發）

<!-- BEGIN GENERATED BDD SC-02 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-02 @P0 @L1-CUS
Feature: SC-02 故障報修到問題卡成立

  As a 終端客戶（PER-CUS-01）
  I want 故障報修到問題卡成立
  So that 5 秒內看到 AI 回應；急件 5 分鐘內有真人接手；報價金額明確、確認後不被亂加價

  # 體現 Persona: PER-CUS-01 終端客戶（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-CS-AI-01, TC-CS-AI-02, TC-CS-AI-09, TC-CS-AI-10, TC-CS-AI-12, TC-DISPATCH-03, TC-EXC-01, TC-NFR-REL-01, TC-PERF-01, TC-SEC-INT-01, TC-SEC-MEM-01, TC-WO-13

  @happy
  Scenario: 正常路徑 — 故障報修到問題卡成立
    Given 客戶回報鎖具故障並要求派師傅
    When AI 追問品牌／型號／地址
    And 三層解決嘗試
    And 判定需人工
    And transfer_to_human
    And AI 草擬問題卡進後台
    And 客服補全
    And completeness ≥ 0.85
    And confirmed
    Then 問題卡狀態為 confirmed，欄位與對話事實一致，badge 標示 AI 草擬來源

  @failure
  Scenario: 例外 — 資料連 3 次收不齊
    Given 客戶回報鎖具故障並要求派師傅
    When 資料連 3 次收不齊
    Then 自動轉真人

  @failure
  Scenario: 例外 — 地址缺失
    Given 客戶回報鎖具故障並要求派師傅
    When 地址缺失
    Then 不擋建卡，延後到結案硬擋

  @failure
  Scenario: 例外 — AI 承諾轉接卻未呼叫工具
    Given 客戶回報鎖具故障並要求派師傅
    When AI 承諾轉接卻未呼叫工具
    Then gateway 兜底補一筆 escalation（案子不得蒸發）
```
<!-- END GENERATED BDD SC-02 -->
#### SC-03 急件強制轉真人

- **主要 Actor**：終端客戶
- **觸發**：進線內容命中急件四類——受困門外 / 受困室內 / 人身安全風險 / 怒客情緒
- **主要步驟**：Intent 階段判定急件 → bypass 三層解決 → 5 分鐘內轉真人 → 跳過報價直接建單 → 4 小時內補稽核報價
- **完成判定**：`urgency_detected_at` 已寫入、TransferEvent 落檔、工單於 SLA 內成立
- **失敗與例外**：補稽核逾 4 小時 → alert 升主管；同品牌連續 3 次逾時 → 自動開 ChangeRequest

<!-- BEGIN GENERATED BDD SC-03 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-03 @P0 @L1-CUS
Feature: SC-03 急件強制轉真人

  As a 終端客戶（PER-CUS-01）
  I want 急件強制轉真人
  So that 5 秒內看到 AI 回應；急件 5 分鐘內有真人接手；報價金額明確、確認後不被亂加價

  # 體現 Persona: PER-CUS-01 終端客戶（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-COMPLIANCE-07, TC-CS-AI-04, TC-DISPATCH-08, TC-NFR-REL-01, TC-QUOTE-06, TC-WO-01

  @happy
  Scenario: 正常路徑 — 急件強制轉真人
    Given 進線內容命中急件四類——受困門外 / 受困室內 / 人身安全風險 / 怒客情緒
    When Intent 階段判定急件
    And bypass 三層解決
    And 5 分鐘內轉真人
    And 跳過報價直接建單
    And 4 小時內補稽核報價
    Then urgency_detected_at 已寫入、TransferEvent 落檔、工單於 SLA 內成立

  @failure
  Scenario: 例外 — 補稽核逾 4 小時
    Given 進線內容命中急件四類——受困門外 / 受困室內 / 人身安全風險 / 怒客情緒
    When 補稽核逾 4 小時
    Then alert 升主管

  @failure
  Scenario: 例外 — 同品牌連續 3 次逾時
    Given 進線內容命中急件四類——受困門外 / 受困室內 / 人身安全風險 / 怒客情緒
    When 同品牌連續 3 次逾時
    Then 自動開 ChangeRequest
```
<!-- END GENERATED BDD SC-03 -->
#### SC-04 報價確認到工單成立

- **主要 Actor**：終端客戶 × 派工小編
- **觸發**：問題卡 `confirmed`
- **主要步驟**：建報價 draft → 內部核准 → 送客戶 → 客戶於 LIFF 查看明細並勾選同意 → 確認 → 客服 1-click 建立工單
- **完成判定**：工單 `created`，且**無已確認報價不得建單**這條硬綁定成立
- **失敗與例外**：報價過期（一般 14 天／急件 3 天）→ 失效需重報；保固／專案案件由 AI 送出 → 403 阻擋；客戶端視圖出現成本欄 → 視為重大缺陷

<!-- BEGIN GENERATED BDD SC-04 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-04 @P0 @L1-CUS
Feature: SC-04 報價確認到工單成立

  As a 終端客戶（PER-CUS-01）
  I want 報價確認到工單成立
  So that 5 秒內看到 AI 回應；急件 5 分鐘內有真人接手；報價金額明確、確認後不被亂加價

  # 體現 Persona: PER-CUS-01 終端客戶（primary）；PER-OPS-01 品牌營運（派工小編）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-CS-AI-06, TC-QUOTE-01, TC-QUOTE-02, TC-QUOTE-03, TC-QUOTE-04, TC-QUOTE-05, TC-QUOTE-07, TC-QUOTE-08, TC-QUOTE-09, TC-WO-01, TC-WO-02, TC-WO-03

  @happy
  Scenario: 正常路徑 — 報價確認到工單成立
    Given 問題卡 confirmed
    When 建報價 draft
    And 內部核准
    And 送客戶
    And 客戶於 LIFF 查看明細並勾選同意
    And 確認
    And 客服 1-click 建立工單
    Then 工單 created，且無已確認報價不得建單這條硬綁定成立

  @failure
  Scenario: 例外 — 報價過期（一般 14 天／急件 3 天）
    Given 問題卡 confirmed
    When 報價過期（一般 14 天／急件 3 天）
    Then 失效需重報

  @failure
  Scenario: 例外 — 保固／專案案件由 AI 送出
    Given 問題卡 confirmed
    When 保固／專案案件由 AI 送出
    Then 403 阻擋

  @failure
  Scenario: 例外 — 客戶端視圖出現成本欄
    Given 問題卡 confirmed
    When 客戶端視圖出現成本欄
    Then 視為重大缺陷
```
<!-- END GENERATED BDD SC-04 -->
#### SC-05 派工媒合到技師接單

- **主要 Actor**：派工小編 × 簽約師傅
- **觸發**：工單 `created`
- **主要步驟**：候選池 5→10→20km 擴大 → 五因子權重排序 → top-1 通知 → 技師接單
- **完成判定**：技師接單，工單狀態推進至 `assigned`，品牌側與技師側投影一致
- **失敗與例外**：候選池空 → `dispatch_pending` + alert；接單逾時（一般 10min／急件 5min）→ 回佇列擴大候選；技師拒單 → 自動改派；小編手動覆寫 → 必留 who/why 稽核

<!-- BEGIN GENERATED BDD SC-05 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-05 @P0 @L1-CUS
Feature: SC-05 派工媒合到技師接單

  As a 品牌營運（派工小編）（PER-OPS-01）
  I want 派工媒合到技師接單
  So that 客服佇列清空；接手的每一單都有完整問題卡脈絡；取消費 / 退款分層由系統自動算，特殊情境可覆寫並留稽核

  # 體現 Persona: PER-OPS-01 品牌營運（派工小編）（primary）；PER-TEC-01 簽約師傅（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-01, TC-DISPATCH-02, TC-DISPATCH-03, TC-DISPATCH-04, TC-DISPATCH-05, TC-DISPATCH-06, TC-DISPATCH-09, TC-EXC-06, TC-NFR-PERF-01, TC-NFR-SCAL-01, TC-NFR-SLA-01, TC-PERF-03

  @happy
  Scenario: 正常路徑 — 派工媒合到技師接單
    Given 工單 created
    When 候選池 5
    And 10
    And 20km 擴大
    And 五因子權重排序
    And top-1 通知
    And 技師接單
    Then 技師接單，工單狀態推進至 assigned，品牌側與技師側投影一致

  @failure
  Scenario: 例外 — 候選池空
    Given 工單 created
    When 候選池空
    Then dispatch_pending + alert

  @failure
  Scenario: 例外 — 接單逾時（一般 10min／急件 5min）
    Given 工單 created
    When 接單逾時（一般 10min／急件 5min）
    Then 回佇列擴大候選

  @failure
  Scenario: 例外 — 技師拒單
    Given 工單 created
    When 技師拒單
    Then 自動改派

  @failure
  Scenario: 例外 — 小編手動覆寫
    Given 工單 created
    When 小編手動覆寫
    Then 必留 who/why 稽核
```
<!-- END GENERATED BDD SC-05 -->
#### SC-06 現場施工到完工結案

- **主要 Actor**：簽約師傅 × 終端客戶
- **觸發**：技師抵達現場並簽到
- **主要步驟**：到場存證 → 施工 → 施工照上傳 → 材料登錄（主鎖與高價零件強制 serial）→ 客戶簽名 → 結案
- **完成判定**：通過結案硬閘（地址齊備 + 報價已確認 + 證據齊備），狀態 `completed`
- **失敗與例外**：照片不足／無簽名／缺 serial → 422 阻擋；客戶不在場 → 手機簽章頁 → QR 跨裝置 → 紙本 fallback + audit；客戶不在／無法施工 → 改期並依階段計算取消費

<!-- BEGIN GENERATED BDD SC-06 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-06 @P0 @L1-CUS
Feature: SC-06 現場施工到完工結案

  As a 簽約師傅（PER-TEC-01）
  I want 現場施工到完工結案
  So that 一個帳號服務所有簽約品牌；派工推播 2 秒內到手；完工回報 5 分鐘內完成；跨品牌單一對帳單（statement）月結對得起來

  # 體現 Persona: PER-TEC-01 簽約師傅（primary）；PER-CUS-01 終端客戶（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-COMPLIANCE-06, TC-CS-AI-06, TC-DISPATCH-03, TC-DISPATCH-05, TC-NFR-SLA-01, TC-ONSITE-01, TC-ONSITE-05, TC-ONSITE-06, TC-SETTLE-02, TC-WO-04, TC-WO-05, TC-WO-06, TC-WO-07, TC-WO-08, TC-WO-14

  @happy
  Scenario: 正常路徑 — 現場施工到完工結案
    Given 技師抵達現場並簽到
    When 到場存證
    And 施工
    And 施工照上傳
    And 材料登錄（主鎖與高價零件強制 serial）
    And 客戶簽名
    And 結案
    Then 通過結案硬閘（地址齊備 + 報價已確認 + 證據齊備），狀態 completed

  @failure
  Scenario: 例外 — 照片不足／無簽名／缺 serial
    Given 技師抵達現場並簽到
    When 照片不足／無簽名／缺 serial
    Then 422 阻擋

  @failure
  Scenario: 例外 — 客戶不在場
    Given 技師抵達現場並簽到
    When 客戶不在場
    Then 手機簽章頁 → QR 跨裝置 → 紙本 fallback + audit

  @failure
  Scenario: 例外 — 客戶不在／無法施工
    Given 技師抵達現場並簽到
    When 客戶不在／無法施工
    Then 改期並依階段計算取消費
```
<!-- END GENERATED BDD SC-06 -->
#### SC-07 現場範圍變更與報價修正

- **主要 Actor**：簽約師傅 × 終端客戶
- **觸發**：技師到場後發現實際故障與報修內容不符
- **主要步驟**：師傅發起 requote（事由分類 + 項目 diff，**不含金額**）→ 平台驗身分與工單狀態 → 品牌定價引擎產生 quote v+1 → 依金額三段分層取得同意 → 施工
- **完成判定**：新版報價取得對應層級同意後才施工，且全程留痕
- **失敗與例外**：非工單 assignee 發起 → 403；師傅單獨收款 → 系統攔截；未走分層直接施工 → 視為合約違反

> 這條旅程是「技師端零定價權」這條治理紅線的唯一驗證場所。

<!-- BEGIN GENERATED BDD SC-07 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-07 @P0 @L1-CUS
Feature: SC-07 現場範圍變更與報價修正

  As a 簽約師傅（PER-TEC-01）
  I want 現場範圍變更與報價修正
  So that 一個帳號服務所有簽約品牌；派工推播 2 秒內到手；完工回報 5 分鐘內完成；跨品牌單一對帳單（statement）月結對得起來

  # 體現 Persona: PER-TEC-01 簽約師傅（primary）；PER-CUS-01 終端客戶（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-07, TC-ONSITE-02, TC-ONSITE-03, TC-ONSITE-04, TC-ONSITE-06, TC-ONSITE-07, TC-QUOTE-04

  @happy
  Scenario: 正常路徑 — 現場範圍變更與報價修正
    Given 技師到場後發現實際故障與報修內容不符
    When 師傅發起 requote（事由分類 + 項目 diff，不含金額）
    And 平台驗身分與工單狀態
    And 品牌定價引擎產生 quote v+1
    And 依金額三段分層取得同意
    And 施工
    Then 新版報價取得對應層級同意後才施工，且全程留痕

  @failure
  Scenario: 例外 — 非工單 assignee 發起
    Given 技師到場後發現實際故障與報修內容不符
    When 非工單 assignee 發起
    Then 403

  @failure
  Scenario: 例外 — 師傅單獨收款
    Given 技師到場後發現實際故障與報修內容不符
    When 師傅單獨收款
    Then 系統攔截

  @failure
  Scenario: 例外 — 未走分層直接施工
    Given 技師到場後發現實際故障與報修內容不符
    When 未走分層直接施工
    Then 視為合約違反
```
<!-- END GENERATED BDD SC-07 -->
#### SC-08 收款、取消與退款

- **主要 Actor**：終端客戶 × 派工小編
- **觸發**：工單完工待收款，或任一階段發生取消／退款申請
- **主要步驟**：三軌支付（現金／Apple Pay／LINE Pay）→ webhook 冪等對帳 → 憑證開立；取消依 5+1 階段自動計費；退款依責任分層並執行職責分離雙簽
- **完成判定**：金額與費率表逐檔一致，帳務為 append-only reversal，零錯帳
- **失敗與例外**：派工後 0 元取消 → 阻擋；同人同時發起與核准 → 409 SoD 違反；現金爭議 → 進 disputes 流程

<!-- BEGIN GENERATED BDD SC-08 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-08 @P0 @L1-CUS
Feature: SC-08 收款、取消與退款

  As a 終端客戶（PER-CUS-01）
  I want 收款、取消與退款
  So that 5 秒內看到 AI 回應；急件 5 分鐘內有真人接手；報價金額明確、確認後不被亂加價

  # 體現 Persona: PER-CUS-01 終端客戶（primary）；PER-OPS-01 品牌營運（派工小編）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-PAYMENT-01, TC-QUOTE-04, TC-SEC-IDEM-01, TC-SEC-SOD-01, TC-SETTLE-02, TC-SETTLE-03, TC-SETTLE-04, TC-SETTLE-05, TC-SETTLE-06, TC-WEB-REPORT-01, TC-WO-12

  @happy
  Scenario: 正常路徑 — 收款、取消與退款
    Given 工單完工待收款，或任一階段發生取消／退款申請
    When 三軌支付（現金／Apple Pay／LINE Pay）
    And webhook 冪等對帳
    And 憑證開立；取消依 5+1 階段自動計費；退款依責任分層並執行職責分離雙簽
    Then 金額與費率表逐檔一致，帳務為 append-only reversal，零錯帳

  @failure
  Scenario: 例外 — 派工後 0 元取消
    Given 工單完工待收款，或任一階段發生取消／退款申請
    When 派工後 0 元取消
    Then 阻擋

  @failure
  Scenario: 例外 — 同人同時發起與核准
    Given 工單完工待收款，或任一階段發生取消／退款申請
    When 同人同時發起與核准
    Then 409 SoD 違反

  @failure
  Scenario: 例外 — 現金爭議
    Given 工單完工待收款，或任一階段發生取消／退款申請
    When 現金爭議
    Then 進 disputes 流程
```
<!-- END GENERATED BDD SC-08 -->
#### SC-09 月結與七帳本對帳

- **主要 Actor**：租戶 Admin
- **觸發**：結算期末
- **主要步驟**：七帳本月結批次 → borrow=lend 平衡驗證 → 對帳例外以 reason code 分類處理
- **完成判定**：帳本平衡且例外全數有 reason code
- **失敗與例外**：品牌計費與平台彙總不符 → 期末 reconcile 閘門擋住 payout（銜接 SC-13）

<!-- BEGIN GENERATED BDD SC-09 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-09 @P1 @L1-CUS
Feature: SC-09 月結與七帳本對帳

  As a 租戶 Admin（品牌管理者）（PER-OPS-02）
  I want 月結與七帳本對帳
  So that 帳號自助開通免平台介入；月結 borrow=lend 對得起；每筆敏感操作留 SoD 稽核

  # 體現 Persona: PER-OPS-02 租戶 Admin（品牌管理者）（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-EXC-01, TC-SETTLE-01, TC-SETTLE-02, TC-WEB-REPORT-01

  @happy
  Scenario: 正常路徑 — 月結與七帳本對帳
    Given 結算期末
    When 七帳本月結批次
    And borrow=lend 平衡驗證
    And 對帳例外以 reason code 分類處理
    Then 帳本平衡且例外全數有 reason code

  @failure
  Scenario: 例外 — 品牌計費與平台彙總不符
    Given 結算期末
    When 品牌計費與平台彙總不符
    Then 期末 reconcile 閘門擋住 payout（銜接 SC-13）
```
<!-- END GENERATED BDD SC-09 -->
### L1-OPS 品牌營運線

#### SC-10 人工接管與對話不蒸發

- **主要 Actor**：派工小編
- **觸發**：對話已 escalated，小編決定接手
- **主要步驟**：小編於後台接管 → AI 每 turn 前查接管旗標 → 接管中 AI 靜音 → 小編與客戶訊息持續全量入庫並標記 sender_role
- **完成判定**：接管期間對話**零缺漏**，且 AI 未再自行回覆
- **失敗與例外**：接管旗標查詢失敗（5s timeout）→ fail-soft 不阻斷客人回覆；旗標誤判 → AI 錯誤靜音或錯誤插話，皆為 P0 缺陷

<!-- BEGIN GENERATED BDD SC-10 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-10 @P0 @L1-OPS
Feature: SC-10 人工接管與對話不蒸發

  As a 品牌營運（派工小編）（PER-OPS-01）
  I want 人工接管與對話不蒸發
  So that 客服佇列清空；接手的每一單都有完整問題卡脈絡；取消費 / 退款分層由系統自動算，特殊情境可覆寫並留稽核

  # 體現 Persona: PER-OPS-01 品牌營運（派工小編）（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-AGT-TURN-01, TC-CS-AI-04, TC-CS-AI-10, TC-DISPATCH-03, TC-SEC-INT-01

  @happy
  Scenario: 正常路徑 — 人工接管與對話不蒸發
    Given 對話已 escalated，小編決定接手
    When 小編於後台接管
    And AI 每 turn 前查接管旗標
    And 接管中 AI 靜音
    And 小編與客戶訊息持續全量入庫並標記 sender_role
    Then 接管期間對話零缺漏，且 AI 未再自行回覆

  @failure
  Scenario: 例外 — 接管旗標查詢失敗（5s timeout）
    Given 對話已 escalated，小編決定接手
    When 接管旗標查詢失敗（5s timeout）
    Then fail-soft 不阻斷客人回覆

  @failure
  Scenario: 例外 — 旗標誤判
    Given 對話已 escalated，小編決定接手
    When 旗標誤判
    Then AI 錯誤靜音或錯誤插話，皆為 P0 缺陷
```
<!-- END GENERATED BDD SC-10 -->
#### SC-11 例外審批與 SoD 收件匣

- **主要 Actor**：派工小編 × 租戶 Admin
- **觸發**：產生改期 / 例外案件 / 爭議事件
- **主要步驟**：例外集中進收件匣 → 分派審批者 → 依敏感度要求發起／核准／執行三方分離 → 裁決留痕
- **完成判定**：所有敏感操作的三方角色互不相同，違反者 100% 被阻擋
- **失敗與例外**：任二角色相同 → 403；審批逾期 → 升級主管

<!-- BEGIN GENERATED BDD SC-11 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-11 @P0 @L1-OPS
Feature: SC-11 例外審批與 SoD 收件匣

  As a 品牌營運（派工小編）（PER-OPS-01）
  I want 例外審批與 SoD 收件匣
  So that 客服佇列清空；接手的每一單都有完整問題卡脈絡；取消費 / 退款分層由系統自動算，特殊情境可覆寫並留稽核

  # 體現 Persona: PER-OPS-01 品牌營運（派工小編）（primary）；PER-OPS-02 租戶 Admin（品牌管理者）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-EXC-01, TC-SEC-RBAC-01, TC-SEC-SOD-01, TC-SETTLE-03, TC-SETTLE-07

  @happy
  Scenario: 正常路徑 — 例外審批與 SoD 收件匣
    Given 產生改期 / 例外案件 / 爭議事件
    When 例外集中進收件匣
    And 分派審批者
    And 依敏感度要求發起／核准／執行三方分離
    And 裁決留痕
    Then 所有敏感操作的三方角色互不相同，違反者 100% 被阻擋

  @failure
  Scenario: 例外 — 任二角色相同
    Given 產生改期 / 例外案件 / 爭議事件
    When 任二角色相同
    Then 403

  @failure
  Scenario: 例外 — 審批逾期
    Given 產生改期 / 例外案件 / 爭議事件
    When 審批逾期
    Then 升級主管
```
<!-- END GENERATED BDD SC-11 -->
### L1-TEC 簽約師傅線

#### SC-12 技師註冊、KYC 到品牌授權

- **主要 Actor**：簽約師傅 × Super Admin
- **觸發**：師傅於獨立技師站台申請註冊
- **主要步驟**：OIDC 建立跨租戶技師身分 → 填 profile／技能／欲服務品牌 → 上傳 KYC 與認證文件（敏感欄加密）→ 人工審核 → 認證生效 → 品牌授權
- **完成判定**：技師身分獨立於任何品牌租戶，且**未過准入閘門者不得進入派工候選集**
- **失敗與例外**：文件不齊 → 退件；審核未過卻出現在候選集 → P0 治理缺陷

<!-- BEGIN GENERATED BDD SC-12 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-12 @P0 @L1-TEC
Feature: SC-12 技師註冊、KYC 到品牌授權

  As a 簽約師傅（PER-TEC-01）
  I want 技師註冊、KYC 到品牌授權
  So that 一個帳號服務所有簽約品牌；派工推播 2 秒內到手；完工回報 5 分鐘內完成；跨品牌單一對帳單（statement）月結對得起來

  # 體現 Persona: PER-TEC-01 簽約師傅（primary）；PER-PLT-01 平台管理員（Super Admin）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-01, TC-DISPATCH-06, TC-PLT-SURFACE-01, TC-SEC-WEB-02, TC-TEC-LIFE-01, TC-WEB-SURFACE-01

  @happy
  Scenario: 正常路徑 — 技師註冊、KYC 到品牌授權
    Given 師傅於獨立技師站台申請註冊
    When OIDC 建立跨租戶技師身分
    And 填 profile／技能／欲服務品牌
    And 上傳 KYC 與認證文件（敏感欄加密）
    And 人工審核
    And 認證生效
    And 品牌授權
    Then 技師身分獨立於任何品牌租戶，且未過准入閘門者不得進入派工候選集

  @failure
  Scenario: 例外 — 文件不齊
    Given 師傅於獨立技師站台申請註冊
    When 文件不齊
    Then 退件

  @failure
  Scenario: 例外 — 審核未過卻出現在候選集
    Given 師傅於獨立技師站台申請註冊
    When 審核未過卻出現在候選集
    Then P0 治理缺陷
```
<!-- END GENERATED BDD SC-12 -->
#### SC-13 技師跨品牌對帳與佣金請領

- **主要 Actor**：簽約師傅
- **觸發**：佣金產生事件累積至結算期
- **主要步驟**：各品牌 per-job 計費發事件 → 技師平台跨品牌彙總 statement → 技師對帳 → payout
- **完成判定**：statement 與各品牌計費逐筆對得起來，reconcile 閘門通過
- **失敗與例外**：對帳差異 → 閘門擋住 payout 並開例外案件（銜接 SC-09）

<!-- BEGIN GENERATED BDD SC-13 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-13 @P1 @L1-TEC
Feature: SC-13 技師跨品牌對帳與佣金請領

  As a 簽約師傅（PER-TEC-01）
  I want 技師跨品牌對帳與佣金請領
  So that 一個帳號服務所有簽約品牌；派工推播 2 秒內到手；完工回報 5 分鐘內完成；跨品牌單一對帳單（statement）月結對得起來

  # 體現 Persona: PER-TEC-01 簽約師傅（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-05, TC-EXC-06, TC-SETTLE-08

  @happy
  Scenario: 正常路徑 — 技師跨品牌對帳與佣金請領
    Given 佣金產生事件累積至結算期
    When 各品牌 per-job 計費發事件
    And 技師平台跨品牌彙總 statement
    And 技師對帳
    And payout
    Then statement 與各品牌計費逐筆對得起來，reconcile 閘門通過

  @failure
  Scenario: 例外 — 對帳差異
    Given 佣金產生事件累積至結算期
    When 對帳差異
    Then 閘門擋住 payout 並開例外案件（銜接 SC-09）
```
<!-- END GENERATED BDD SC-13 -->
#### SC-14 認證撤銷與停權即時廣播

- **主要 Actor**：Super Admin
- **觸發**：技師違規、認證到期或主動停權
- **主要步驟**：平台發起撤銷 → 廣播撤銷事件 → 各品牌訂閱後即時移出候選集 → 進行中工單改派
- **完成判定**：撤銷後各品牌候選集一致且不再派給該技師；進行中工單有承接方
- **失敗與例外**：事件遺失導致某品牌仍派工 → P0；進行中工單無人承接 → 升級人工派工

<!-- BEGIN GENERATED BDD SC-14 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-14 @P0 @L1-TEC
Feature: SC-14 認證撤銷與停權即時廣播

  As a 平台管理員（Super Admin）（PER-PLT-01）
  I want 認證撤銷與停權即時廣播
  So that 品牌從申請到上線的 provisioning 全自動（🔜 規劃中）；師傅審核佇列不積壓；每一次跨租戶操作可追溯

  # 體現 Persona: PER-PLT-01 平台管理員（Super Admin）（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-01, TC-DISPATCH-06, TC-DISPATCH-09, TC-EXC-06, TC-PLT-SURFACE-01, TC-TEC-REVOKE-01

  @happy
  Scenario: 正常路徑 — 認證撤銷與停權即時廣播
    Given 技師違規、認證到期或主動停權
    When 平台發起撤銷
    And 廣播撤銷事件
    And 各品牌訂閱後即時移出候選集
    And 進行中工單改派
    Then 撤銷後各品牌候選集一致且不再派給該技師
    And 進行中工單有承接方

  @failure
  Scenario: 例外 — 事件遺失導致某品牌仍派工
    Given 技師違規、認證到期或主動停權
    When 事件遺失導致某品牌仍派工
    Then P0

  @failure
  Scenario: 例外 — 進行中工單無人承接
    Given 技師違規、認證到期或主動停權
    When 進行中工單無人承接
    Then 升級人工派工
```
<!-- END GENERATED BDD SC-14 -->
### L1-KNW 知識治理線

#### SC-15 知識精煉 HITL 到雙路發布

- **主要 Actor**：客服主管 × Domain Expert
- **觸發**：診斷對話或產品素材進入精煉佇列
- **主要步驟**：素材汲取進 bronze → 提煉分流為事實／行為 → Draft Queue → 審核 UI 呈現 diff → 核可／拒絕／退回重煉 → 雙路發布（事實進向量語料、行為進 skill 檔）
- **完成判定**：**未核可零落地**；發布後 agent 行為與檢索結果同步更新
- **失敗與例外**：素材來源不屬 bronze 白名單 → 發布前校驗擋下；繞過審核直接發布 → 必須失敗

<!-- BEGIN GENERATED BDD SC-15 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-15 @P0 @L1-KNW
Feature: SC-15 知識精煉 HITL 到雙路發布

  As a 客服主管（PER-KNW-01）
  I want 知識精煉 HITL 到雙路發布
  So that 知識精煉走 HITL 有據可查；高風險 SOP 未經雙審不得發布

  # 體現 Persona: PER-KNW-01 客服主管（primary）；PER-KNW-02 Domain Expert（領域專家）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-AGT-RAG-01, TC-COMPLIANCE-08, TC-CS-AI-03, TC-NFR-PUB-01, TC-REF-PUBLISH-01, TC-REF-SPLIT-01

  @happy
  Scenario: 正常路徑 — 知識精煉 HITL 到雙路發布
    Given 診斷對話或產品素材進入精煉佇列
    When 素材汲取進 bronze
    And 提煉分流為事實／行為
    And Draft Queue
    And 審核 UI 呈現 diff
    And 核可／拒絕／退回重煉
    And 雙路發布（事實進向量語料、行為進 skill 檔）
    Then 未核可零落地
    And 發布後 agent 行為與檢索結果同步更新

  @failure
  Scenario: 例外 — 素材來源不屬 bronze 白名單
    Given 診斷對話或產品素材進入精煉佇列
    When 素材來源不屬 bronze 白名單
    Then 發布前校驗擋下

  @failure
  Scenario: 例外 — 繞過審核直接發布
    Given 診斷對話或產品素材進入精煉佇列
    When 繞過審核直接發布
    Then 必須失敗
```
<!-- END GENERATED BDD SC-15 -->
#### SC-16 SOP 雙審與 Family Reviewer 覆核

- **主要 Actor**：Domain Expert × Family Reviewer
- **觸發**：高風險 SOP draft 產生
- **主要步驟**：客服主管與 Domain Expert 雙簽 → Family Reviewer 覆核（SLA 24h）→ 核可後短時間內向量化發布
- **完成判定**：覆核率 100%，且未經覆核的發布嘗試一律失敗
- **失敗與例外**：覆核者缺席逾 24h → 暫停發布並升級；ledger 遭竄改 → 稽核鏈驗證失敗

<!-- BEGIN GENERATED BDD SC-16 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-16 @P0 @L1-KNW
Feature: SC-16 SOP 雙審與 Family Reviewer 覆核

  As a Domain Expert（領域專家）（PER-KNW-02）
  I want SOP 雙審與 Family Reviewer 覆核
  So that 僅經來源標註（provenance）且通過審核的知識可發布

  # 體現 Persona: PER-KNW-02 Domain Expert（領域專家）（primary）；PER-KNW-03 Family Reviewer（安全覆核者）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-COMPLIANCE-05, TC-REF-PUBLISH-01, TC-SEC-RBAC-01

  @happy
  Scenario: 正常路徑 — SOP 雙審與 Family Reviewer 覆核
    Given 高風險 SOP draft 產生
    When 客服主管與 Domain Expert 雙簽
    And Family Reviewer 覆核（SLA 24h）
    And 核可後短時間內向量化發布
    Then 覆核率 100%，且未經覆核的發布嘗試一律失敗

  @failure
  Scenario: 例外 — 覆核者缺席逾 24h
    Given 高風險 SOP draft 產生
    When 覆核者缺席逾 24h
    Then 暫停發布並升級

  @failure
  Scenario: 例外 — ledger 遭竄改
    Given 高風險 SOP draft 產生
    When ledger 遭竄改
    Then 稽核鏈驗證失敗
```
<!-- END GENERATED BDD SC-16 -->
### L1-PLT 平台治理線

#### SC-17 品牌申請到 License 開通上線

- **主要 Actor**：加盟品牌 × Super Admin
- **觸發**：潛在品牌於官網送出加盟申請
- **主要步驟**：申請受理 → Super Admin 審核 → 建立租戶組織與 License → 依 License 決定開通模組 → per-brand 部署、建庫、綁定 LINE 通道 → 上線
- **完成判定**：品牌可獨立登入並操作已開通模組，且跨租戶零資料可見性
- **失敗與例外**：provisioning 中斷 → 可重跑且冪等；License 未涵蓋的模組出現在選單 → 治理缺陷

<!-- BEGIN GENERATED BDD SC-17 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-17 @P0 @L1-PLT
Feature: SC-17 品牌申請到 License 開通上線

  As a 潛在加盟品牌（PER-PLT-02）
  I want 品牌申請到 License 開通上線
  So that 申請 → License 開通 → provisioning 一條龍、進度可追蹤

  # 體現 Persona: PER-PLT-02 潛在加盟品牌（primary）；PER-PLT-01 平台管理員（Super Admin）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-CS-AI-01, TC-EXC-05, TC-PLT-PROV-01, TC-PLT-SURFACE-01, TC-SEC-WEB-02, TC-WEB-SURFACE-01

  @happy
  Scenario: 正常路徑 — 品牌申請到 License 開通上線
    Given 潛在品牌於官網送出加盟申請
    When 申請受理
    And Super Admin 審核
    And 建立租戶組織與 License
    And 依 License 決定開通模組
    And per-brand 部署、建庫、綁定 LINE 通道
    And 上線
    Then 品牌可獨立登入並操作已開通模組，且跨租戶零資料可見性

  @failure
  Scenario: 例外 — provisioning 中斷
    Given 潛在品牌於官網送出加盟申請
    When provisioning 中斷
    Then 可重跑且冪等

  @failure
  Scenario: 例外 — License 未涵蓋的模組出現在選單
    Given 潛在品牌於官網送出加盟申請
    When License 未涵蓋的模組出現在選單
    Then 治理缺陷
```
<!-- END GENERATED BDD SC-17 -->
#### SC-18 品牌自助配置與治理回滾

- **主要 Actor**：租戶 Admin
- **觸發**：品牌需調整費率、文案、skill 客製層或流程積木
- **主要步驟**：於後台編輯 → 版本化 → 評估閘門 → 分階段推出 → 觀察 → 必要時一鍵回滾
- **完成判定**：配置變更**不需改碼**即生效，回滾在約定時間內完成，全程留 who/when/what diff/why
- **失敗與例外**：嘗試覆寫受保護層（escalation／domain-safety）→ 阻擋；非 owner 角色嘗試修改 → 阻擋；高風險流程由 AI 產出 → 強制人審

<!-- BEGIN GENERATED BDD SC-18 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-18 @P1 @L1-PLT
Feature: SC-18 品牌自助配置與治理回滾

  As a 租戶 Admin（品牌管理者）（PER-OPS-02）
  I want 品牌自助配置與治理回滾
  So that 帳號自助開通免平台介入；月結 borrow=lend 對得起；每筆敏感操作留 SoD 稽核

  # 體現 Persona: PER-OPS-02 租戶 Admin（品牌管理者）（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-EXC-02, TC-NFR-PERF-01, TC-PLT-CFG-01, TC-PLT-FLOW-01, TC-SEC-RBAC-03, TC-SETTLE-07

  @happy
  Scenario: 正常路徑 — 品牌自助配置與治理回滾
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 於後台編輯
    And 版本化
    And 評估閘門
    And 分階段推出
    And 觀察
    And 必要時一鍵回滾
    Then 配置變更不需改碼即生效，回滾在約定時間內完成，全程留 who/when/what diff/why

  @failure
  Scenario: 例外 — 嘗試覆寫受保護層（escalation／domain-safety）
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 嘗試覆寫受保護層（escalation／domain-safety）
    Then 阻擋

  @failure
  Scenario: 例外 — 非 owner 角色嘗試修改
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 非 owner 角色嘗試修改
    Then 阻擋

  @failure
  Scenario: 例外 — 高風險流程由 AI 產出
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 高風險流程由 AI 產出
    Then 強制人審
```
<!-- END GENERATED BDD SC-18 -->
#### SC-19 GDPR 被遺忘權執行

- **主要 Actor**：終端客戶 × DPO
- **觸發**：資料當事人提出刪除請求
- **主要步驟**：受理 → legal-hold 衝突檢查 → T0 銷毀金鑰並軟刪 → T+30 日排程硬刪 → 全程寫入 append-only 稽核帳本
- **完成判定**：於法定期限內執行，或在期限內完成客戶告知
- **失敗與例外**：與 legal hold 衝突 → 拒絕並於 7 日內通知客戶；硬刪排程未執行 → 合規事故

---

<!-- BEGIN GENERATED BDD SC-19 · 由 _render_bdd.py 生成，改上游 SC 卡後重跑，勿手改 -->
```gherkin
@SC-19 @P0 @L1-PLT
Feature: SC-19 GDPR 被遺忘權執行

  As a 終端客戶（PER-CUS-01）
  I want GDPR 被遺忘權執行
  So that 5 秒內看到 AI 回應；急件 5 分鐘內有真人接手；報價金額明確、確認後不被亂加價

  # 體現 Persona: PER-CUS-01 終端客戶（primary）；PER-PLT-03 DPO（資料保護官）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-COMPLIANCE-01, TC-COMPLIANCE-02, TC-COMPLIANCE-03, TC-COMPLIANCE-04, TC-EXC-01, TC-SEC-MEM-01, TC-SETTLE-07

  @happy
  Scenario: 正常路徑 — GDPR 被遺忘權執行
    Given 資料當事人提出刪除請求
    When 受理
    And legal-hold 衝突檢查
    And T0 銷毀金鑰並軟刪
    And T+30 日排程硬刪
    And 全程寫入 append-only 稽核帳本
    Then 於法定期限內執行，或在期限內完成客戶告知

  @failure
  Scenario: 例外 — 與 legal hold 衝突
    Given 資料當事人提出刪除請求
    When 與 legal hold 衝突
    Then 拒絕並於 7 日內通知客戶

  @failure
  Scenario: 例外 — 硬刪排程未執行
    Given 資料當事人提出刪除請求
    When 硬刪排程未執行
    Then 合規事故
```
<!-- END GENERATED BDD SC-19 -->
## 4. 遷移對照表（過渡用，脊椎穩定後刪除）

> ⚠️ **這張表是一次性遷移工具，不是 join key。** 任何生成器都不得用這張表連邊。
> 它存在的唯一目的，是讓四套 legacy 編號的既有內容能被人工搬到正確的 `SC` 底下。
> 搬遷完成後本節整段刪除。

| SC | 旅程 | UF | TS | UAT S |
|:---|:---|:---|:---|:---|
| SC-01 | A | UF-02 | TS-01 | UAT-01 |
| SC-02 | A | UF-02 | TS-01 | UAT-01 |
| SC-03 | A | UF-02 / UF-10 #1 | TS-01 | UAT-01 |
| SC-04 | A / B | UF-03 | TS-02 | UAT-02 |
| SC-05 | B / C | UF-04 | TS-03 | UAT-02 |
| SC-06 | C / A | UF-05 / UF-06 | TS-04 | UAT-02 |
| SC-07 | C / A | UF-05 §8.3 | TS-04 | UAT-02 |
| SC-08 | A / B | UF-07 | TS-05 | UAT-04 |
| SC-09 | B | UF-07 | TS-05 | — |
| SC-10 | B | UF-02 | TS-01 | UAT-01 |
| SC-11 | B | UF-07 / UF-08 | TS-05 | UAT-04 |
| SC-12 | C / D | UF-08 §9.2 | TS-06 | — |
| SC-13 | C | — | TS-05 | — |
| SC-14 | D | UF-09 | TS-06 | — |
| SC-15 | — | — | TS-07 | UAT-03 |
| SC-16 | — | — | TS-07 | UAT-03 |
| SC-17 | E / D | UF-08 §9.1 | TS-08 | — |
| SC-18 | B / D | UF-08 §9.3 | TS-12 | UAT-05 |
| SC-19 | A / D | — | TS-10 | UAT-04 |

未被任何 `SC` 認領的 legacy 內容：

- `19_Test_Plan` **TS-09**（migration 與 audit 可重現）、**TS-10**（安全與隱私矩陣，部分）、
  **TS-11**（效能、降級與可觀測）→ 這三個沒有對應旅程，因為它們驗證的是 §2 的
  `scope: global` 需求。它們留在測試計畫，但**不掛 SC**。
- `08_User_Flow` **UF-01**（登入與路由 gate）→ 同上，是所有旅程的前置條件而非旅程本身。

---

## 5. 維護規則

| 想改的內容 | 改這裡 | 不要做的事 |
|:---|:---|:---|
| 旅程的觸發、步驟、完成判定、例外 | 本檔 §3 情境卡 | 在 Excel 或 UAT 報告改敘述 |
| 哪條旅程需要哪條需求 | `_relations/sc_requires_rq.yaml` | 在本檔列 FR 清單 |
| 哪條需求由哪些案例驗證 | `_relations/rq_verified_by_tc.yaml` | 用命名慣例推 |
| 新增旅程 | 本檔 §1 + §3，配新 `SC` 號（**永不重用**）| 沿用退役的號碼 |
| 旅程驗收狀態 | 驗收控制表（人工簽核欄）| 在本檔記狀態 |

`SC` 編號全域唯一、永不重用。刪除的旅程，編號跟著陪葬。

---

*本檔為 tier-2 contract。上游為 `03_PRD.md` 的產品意圖與 `07_Journey_Map.md` 的角色旅程；
下游為 `04_SRS.md` 的 FR／NFR 與 `20_Test_Cases.md` 的案例。*
