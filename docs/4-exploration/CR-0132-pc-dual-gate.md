# CR-0132: 問題卡雙 gate schema（WBS 1.2.3 / 15_SDS §4.6 / 18_DB §4.3）

- **日期**: 2026-07-09
- **狀態**: done
- **觸發面向**: DB schema（problem_cards 15 新欄＋5 死欄清理）、Domain model（雙 gate 生命週期）
- **上游正典**: 15_SDS §4.6（漸進式生命週期＋雙 gate，Accepted）、18_DB §4.3 目標欄位表——設計已凍結，本 CR 為執行落地

## §1 落地內容

1. **migration 093**：`intake_completeness`/`resolution_completeness`（拆
   `completeness_score`，舊欄標 DEPRECATED 保留相容）；分流欄 `triage_tier`
   （L1/L2/L3）/`resolution_channel`（ai_auto/line_text_cs/phone_callback/onsite）/
   `resolved_by`；Gate① 欄 `contact_phone`/`failure_mode`；RMA spine
   `root_cause`/`root_cause_category`/`corrective_action`/`verification`/
   `disposition`（6 值 enum）/`firmware_version`/`serial`；`knowledge_ready`；
   `tenant_id`（直欄＋存量 backfill）＋佇列 partial index；死欄 5 個 DROP IF EXISTS。
2. **雙完整度引擎**：`_dual_scores`＋`_recompute_gates`——建卡/PATCH/confirm/resolve
   後自動重算；L3 條件必填（Gate①＋location、Gate②＋firmware/serial）；Gate② 滿分
   → `knowledge_ready=TRUE`（單向，精煉汲取條件；不擋 operational 結案）。
3. **分流落點**：resolve 落 `triage_tier`（空時以 layer 補）/`resolution_channel`
   （layer 預設映射）/`resolved_by`（操作者）；PATCH 白名單開放全部雙 gate 欄
   （enum 驗證）。
4. **Gate① enforce 開關**：M18 config `problemcard_policy.gate1_enforce`（預設 off
   ——沿用 CR-0042 convert 閘與現行 UAT 流程；前端分流欄 UI 上線後由業主開啟；
   on 時 confirm 缺欄 → `422 INTAKE_GATE_UNMET` 附結構化缺漏）。
5. **待補知識佇列**：`GET /tenants/{t}/problem-cards/knowledge-queue`
   （resolved 且未 ready；宣告先於 `/{id}` 防路徑吃掉；BACKOFFICE 讀）。
6. tenant_id 於人工建卡與 AI 起草（escalation ingest）兩路寫入。

## §8 決策備註

上游決策已凍結於 15_SDS §4.6／18_DB §4.3；本輪唯一自由裁量＝**Gate① enforce
預設 off**（硬開會鎖死現行無分流欄 UI 的 confirm 流程——與 CR-0128 D1a「沒 UI 的
gate 是假的」同判準，開關留業主）。`knowledge_ready` 單向不回退（防精煉已汲取後
旗標翻覆）。

## §9 驗收

- 新測試 6 項：tenant 直欄寫入／漸進補寫雙分數／L3 條件必填／佇列入列出列／
  gate1 開關（off 不擋、on 422→補齊過）／enum 驗證。
- migration 於 scratch @5451 驗證（5 關鍵欄到位）；component **900 passed**
  （4 既有環境失敗無關）、unit 331、四站 tsc 0、types 重生同步。

## 遺留

- ✅ **前端 UI 已補齊**（CR-0138，2026-07-10）：問題卡詳情頁「診斷雙 gate」區塊
  （intake/resolution 完整度進度條＋knowledge_ready 徽章）＋「編輯診斷/知識」modal
  （分流 Gate①＋RMA spine Gate②，L3 條件欄）；新頁 `/admin/knowledge-queue`
  待補知識佇列；Sidebar/rolePolicy/i18n 接線。**Gate① enforce 開關現可由業主開啟**
  （分流欄填寫 UI 已就緒）。
- 精煉服務（2.3.1，M2）接 `knowledge_ready=true` 汲取；`completeness_score`
  正式退場隨舊消費者清完另議。
