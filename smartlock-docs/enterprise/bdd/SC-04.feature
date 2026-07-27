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
