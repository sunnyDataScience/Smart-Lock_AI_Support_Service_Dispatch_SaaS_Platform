@SC-16 @P0 @L1-KNW
Feature: SC-16 SOP 雙審與 Family Reviewer 覆核

  As a Domain Expert（領域專家）（PER-KNW-02）
  I want SOP 雙審與 Family Reviewer 覆核
  So that 僅經來源標註（provenance）且通過審核的知識可發布

  # 體現 Persona: PER-KNW-02 Domain Expert（領域專家）（primary）；PER-KNW-03 Family Reviewer（安全覆核者）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-COMPLIANCE-05, TC-REF-PUBLISH-01, TC-SEC-RBAC-01

  @happy
  Scenario: 正常路徑 — SOP 雙審與 Family Reviewer 覆核
    Given 高風險 SOP draft 產生
    When 客服主管與 Domain Expert 雙簽
    And Family Reviewer 覆核（SLA 24h）
    And 核可後短時間內向量化發布
    Then 覆核率 100%，且未經覆核的發布嘗試一律失敗

  @failure
  Scenario: 例外 — 覆核者缺席逾 24h
    Given 高風險 SOP draft 產生
    When 覆核者缺席逾 24h
    Then 暫停發布並升級

  @failure
  Scenario: 例外 — ledger 遭竄改
    Given 高風險 SOP draft 產生
    When ledger 遭竄改
    Then 稽核鏈驗證失敗
