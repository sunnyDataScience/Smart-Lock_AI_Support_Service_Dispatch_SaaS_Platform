@SC-14 @P0 @L1-TEC
Feature: SC-14 認證撤銷與停權即時廣播

  As a 平台管理員（Super Admin）（PER-PLT-01）
  I want 認證撤銷與停權即時廣播
  So that 品牌從申請到上線的 provisioning 全自動（🔜 規劃中）；師傅審核佇列不積壓；每一次跨租戶操作可追溯

  # 體現 Persona: PER-PLT-01 平台管理員（Super Admin）（primary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-01, TC-DISPATCH-06, TC-DISPATCH-09, TC-EXC-06, TC-PLT-SURFACE-01, TC-TEC-REVOKE-01

  @happy
  Scenario: 正常路徑 — 認證撤銷與停權即時廣播
    Given 技師違規、認證到期或主動停權
    When 平台發起撤銷
    And 廣播撤銷事件
    And 各品牌訂閱後即時移出候選集
    And 進行中工單改派
    Then 撤銷後各品牌候選集一致且不再派給該技師
    And 進行中工單有承接方

  @failure
  Scenario: 例外 — 事件遺失導致某品牌仍派工
    Given 技師違規、認證到期或主動停權
    When 事件遺失導致某品牌仍派工
    Then P0

  @failure
  Scenario: 例外 — 進行中工單無人承接
    Given 技師違規、認證到期或主動停權
    When 進行中工單無人承接
    Then 升級人工派工
