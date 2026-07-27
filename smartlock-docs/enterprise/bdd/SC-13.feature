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
