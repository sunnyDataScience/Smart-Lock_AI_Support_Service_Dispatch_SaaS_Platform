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
