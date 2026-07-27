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
