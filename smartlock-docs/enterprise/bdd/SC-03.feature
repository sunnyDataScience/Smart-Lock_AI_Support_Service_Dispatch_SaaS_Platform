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
