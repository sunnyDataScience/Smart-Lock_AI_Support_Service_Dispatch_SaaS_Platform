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
