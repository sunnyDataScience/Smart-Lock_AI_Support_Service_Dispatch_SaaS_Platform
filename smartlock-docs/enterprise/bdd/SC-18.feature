@SC-18 @P1 @L1-PLT
Feature: SC-18 品牌自助配置與治理回滾

  As a 租戶 Admin（品牌管理者）（PER-OPS-02）
  I want 品牌自助配置與治理回滾
  So that 帳號自助開通免平台介入；月結 borrow=lend 對得起；每筆敏感操作留 SoD 稽核

  # 體現 Persona: PER-OPS-02 租戶 Admin（品牌管理者）（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-EXC-02, TC-NFR-PERF-01, TC-PLT-CFG-01, TC-PLT-FLOW-01, TC-SEC-RBAC-03, TC-SETTLE-07

  @happy
  Scenario: 正常路徑 — 品牌自助配置與治理回滾
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 於後台編輯
    And 版本化
    And 評估閘門
    And 分階段推出
    And 觀察
    And 必要時一鍵回滾
    Then 配置變更不需改碼即生效，回滾在約定時間內完成，全程留 who/when/what diff/why

  @failure
  Scenario: 例外 — 嘗試覆寫受保護層（escalation／domain-safety）
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 嘗試覆寫受保護層（escalation／domain-safety）
    Then 阻擋

  @failure
  Scenario: 例外 — 非 owner 角色嘗試修改
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 非 owner 角色嘗試修改
    Then 阻擋

  @failure
  Scenario: 例外 — 高風險流程由 AI 產出
    Given 品牌需調整費率、文案、skill 客製層或流程積木
    When 高風險流程由 AI 產出
    Then 強制人審
