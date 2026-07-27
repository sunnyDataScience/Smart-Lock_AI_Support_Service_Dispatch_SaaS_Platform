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
