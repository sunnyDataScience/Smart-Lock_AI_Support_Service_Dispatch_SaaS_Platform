@SC-15 @P0 @L1-KNW
Feature: SC-15 知識精煉 HITL 到雙路發布

  As a 客服主管（PER-KNW-01）
  I want 知識精煉 HITL 到雙路發布
  So that 知識精煉走 HITL 有據可查；高風險 SOP 未經雙審不得發布

  # 體現 Persona: PER-KNW-01 客服主管（primary）；PER-KNW-02 Domain Expert（領域專家）（secondary）
  # 驗收腳本案例（sc_verified_by_tc）: TC-AGT-RAG-01, TC-COMPLIANCE-08, TC-CS-AI-03, TC-NFR-PUB-01, TC-REF-PUBLISH-01, TC-REF-SPLIT-01

  @happy
  Scenario: 正常路徑 — 知識精煉 HITL 到雙路發布
    Given 診斷對話或產品素材進入精煉佇列
    When 素材汲取進 bronze
    And 提煉分流為事實／行為
    And Draft Queue
    And 審核 UI 呈現 diff
    And 核可／拒絕／退回重煉
    And 雙路發布（事實進向量語料、行為進 skill 檔）
    Then 未核可零落地
    And 發布後 agent 行為與檢索結果同步更新

  @failure
  Scenario: 例外 — 素材來源不屬 bronze 白名單
    Given 診斷對話或產品素材進入精煉佇列
    When 素材來源不屬 bronze 白名單
    Then 發布前校驗擋下

  @failure
  Scenario: 例外 — 繞過審核直接發布
    Given 診斷對話或產品素材進入精煉佇列
    When 繞過審核直接發布
    Then 必須失敗
