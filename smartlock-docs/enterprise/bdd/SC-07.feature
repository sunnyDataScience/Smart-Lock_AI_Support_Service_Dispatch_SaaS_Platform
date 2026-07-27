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
