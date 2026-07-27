@SC-17 @P0 @L1-PLT
Feature: SC-17 品牌申請到 License 開通上線

  As a 潛在加盟品牌（PER-PLT-02）
  I want 品牌申請到 License 開通上線
  So that 申請 → License 開通 → provisioning 一條龍、進度可追蹤

  # 體現 Persona: PER-PLT-02 潛在加盟品牌（primary）；PER-PLT-01 平台管理員（Super Admin）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-CS-AI-01, TC-EXC-05, TC-PLT-PROV-01, TC-PLT-SURFACE-01, TC-SEC-WEB-02, TC-WEB-SURFACE-01

  @happy
  Scenario: 正常路徑 — 品牌申請到 License 開通上線
    Given 潛在品牌於官網送出加盟申請
    When 申請受理
    And Super Admin 審核
    And 建立租戶組織與 License
    And 依 License 決定開通模組
    And per-brand 部署、建庫、綁定 LINE 通道
    And 上線
    Then 品牌可獨立登入並操作已開通模組，且跨租戶零資料可見性

  @failure
  Scenario: 例外 — provisioning 中斷
    Given 潛在品牌於官網送出加盟申請
    When provisioning 中斷
    Then 可重跑且冪等

  @failure
  Scenario: 例外 — License 未涵蓋的模組出現在選單
    Given 潛在品牌於官網送出加盟申請
    When License 未涵蓋的模組出現在選單
    Then 治理缺陷
