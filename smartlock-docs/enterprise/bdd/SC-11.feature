@SC-11 @P0 @L1-OPS
Feature: SC-11 例外審批與 SoD 收件匣

  As a 品牌營運（派工小編）（PER-OPS-01）
  I want 例外審批與 SoD 收件匣
  So that 客服佇列清空；接手的每一單都有完整問題卡脈絡；取消費 / 退款分層由系統自動算，特殊情境可覆寫並留稽核

  # 體現 Persona: PER-OPS-01 品牌營運（派工小編）（primary）；PER-OPS-02 租戶 Admin（品牌管理者）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-EXC-01, TC-SEC-RBAC-01, TC-SEC-SOD-01, TC-SETTLE-03, TC-SETTLE-07

  @happy
  Scenario: 正常路徑 — 例外審批與 SoD 收件匣
    Given 產生改期 / 例外案件 / 爭議事件
    When 例外集中進收件匣
    And 分派審批者
    And 依敏感度要求發起／核准／執行三方分離
    And 裁決留痕
    Then 所有敏感操作的三方角色互不相同，違反者 100% 被阻擋

  @failure
  Scenario: 例外 — 任二角色相同
    Given 產生改期 / 例外案件 / 爭議事件
    When 任二角色相同
    Then 403

  @failure
  Scenario: 例外 — 審批逾期
    Given 產生改期 / 例外案件 / 爭議事件
    When 審批逾期
    Then 升級主管
