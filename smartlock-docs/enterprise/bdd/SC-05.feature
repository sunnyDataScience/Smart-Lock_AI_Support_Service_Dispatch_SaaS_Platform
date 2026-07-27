@SC-05 @P0 @L1-CUS
Feature: SC-05 派工媒合到技師接單

  As a 品牌營運（派工小編）（PER-OPS-01）
  I want 派工媒合到技師接單
  So that 客服佇列清空；接手的每一單都有完整問題卡脈絡；取消費 / 退款分層由系統自動算，特殊情境可覆寫並留稽核

  # 體現 Persona: PER-OPS-01 品牌營運（派工小編）（primary）；PER-TEC-01 簽約師傅（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-01, TC-DISPATCH-02, TC-DISPATCH-03, TC-DISPATCH-04, TC-DISPATCH-05, TC-DISPATCH-06, TC-DISPATCH-09, TC-EXC-06, TC-NFR-PERF-01, TC-NFR-SCAL-01, TC-NFR-SLA-01, TC-PERF-03

  @happy
  Scenario: 正常路徑 — 派工媒合到技師接單
    Given 工單 created
    When 候選池 5
    And 10
    And 20km 擴大
    And 五因子權重排序
    And top-1 通知
    And 技師接單
    Then 技師接單，工單狀態推進至 assigned，品牌側與技師側投影一致

  @failure
  Scenario: 例外 — 候選池空
    Given 工單 created
    When 候選池空
    Then dispatch_pending + alert

  @failure
  Scenario: 例外 — 接單逾時（一般 10min／急件 5min）
    Given 工單 created
    When 接單逾時（一般 10min／急件 5min）
    Then 回佇列擴大候選

  @failure
  Scenario: 例外 — 技師拒單
    Given 工單 created
    When 技師拒單
    Then 自動改派

  @failure
  Scenario: 例外 — 小編手動覆寫
    Given 工單 created
    When 小編手動覆寫
    Then 必留 who/why 稽核
