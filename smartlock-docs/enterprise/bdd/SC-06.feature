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
