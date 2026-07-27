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
