@SC-12 @P0 @L1-TEC
Feature: SC-12 技師註冊、KYC 到品牌授權

  As a 簽約師傅（PER-TEC-01）
  I want 技師註冊、KYC 到品牌授權
  So that 一個帳號服務所有簽約品牌；派工推播 2 秒內到手；完工回報 5 分鐘內完成；跨品牌單一對帳單（statement）月結對得起來

  # 體現 Persona: PER-TEC-01 簽約師傅（primary）；PER-PLT-01 平台管理員（Super Admin）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-DISPATCH-01, TC-DISPATCH-06, TC-PLT-SURFACE-01, TC-SEC-WEB-02, TC-TEC-LIFE-01, TC-WEB-SURFACE-01

  @happy
  Scenario: 正常路徑 — 技師註冊、KYC 到品牌授權
    Given 師傅於獨立技師站台申請註冊
    When OIDC 建立跨租戶技師身分
    And 填 profile／技能／欲服務品牌
    And 上傳 KYC 與認證文件（敏感欄加密）
    And 人工審核
    And 認證生效
    And 品牌授權
    Then 技師身分獨立於任何品牌租戶，且未過准入閘門者不得進入派工候選集

  @failure
  Scenario: 例外 — 文件不齊
    Given 師傅於獨立技師站台申請註冊
    When 文件不齊
    Then 退件

  @failure
  Scenario: 例外 — 審核未過卻出現在候選集
    Given 師傅於獨立技師站台申請註冊
    When 審核未過卻出現在候選集
    Then P0 治理缺陷
