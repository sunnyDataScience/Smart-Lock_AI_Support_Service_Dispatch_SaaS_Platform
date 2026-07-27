@SC-09 @P1 @L1-CUS
Feature: SC-09 月結與七帳本對帳

  As a 租戶 Admin（品牌管理者）（PER-OPS-02）
  I want 月結與七帳本對帳
  So that 帳號自助開通免平台介入；月結 borrow=lend 對得起；每筆敏感操作留 SoD 稽核

  # 體現 Persona: PER-OPS-02 租戶 Admin（品牌管理者）（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-EXC-01, TC-SETTLE-01, TC-SETTLE-02, TC-WEB-REPORT-01

  @happy
  Scenario: 正常路徑 — 月結與七帳本對帳
    Given 結算期末
    When 七帳本月結批次
    And borrow=lend 平衡驗證
    And 對帳例外以 reason code 分類處理
    Then 帳本平衡且例外全數有 reason code

  @failure
  Scenario: 例外 — 品牌計費與平台彙總不符
    Given 結算期末
    When 品牌計費與平台彙總不符
    Then 期末 reconcile 閘門擋住 payout（銜接 SC-13）
