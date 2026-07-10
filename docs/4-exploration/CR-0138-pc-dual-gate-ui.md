# CR-0138: 問題卡雙 gate 前端 UI（WBS 1.2.3 前端補完）

- **日期**: 2026-07-10
- **狀態**: done
- **觸發面向**: User flow（問題卡診斷/知識填寫）、前端頁面新增
- **上游**: CR-0132（雙 gate schema/引擎/端點；前端 UI 明列遺留）

## §1 落地（純前端，零後端變更——PATCH/GET 端點 CR-0132 已就緒）

1. **問題卡詳情頁「診斷雙 gate」區塊**（`problem-cards/[id]/page.tsx`）：
   `GateBar` ×2 顯示 intake/resolution 完整度（未起算/百分比/顏色分級）＋知識就緒
   徽章＋已填分流/管道/處置摘要。
2. **`DiagnosisModal`**：分流欄（Gate①：triage_tier/contact_phone/failure_mode/
   resolution_channel）＋RMA spine（Gate②：root_cause/root_cause_category/
   corrective_action/verification checkbox/disposition），triage_tier=L3 時展開
   韌體/序號條件欄；dirty-diff 只送異動欄，儲存後重載 card（後端重算）。
3. **新頁 `/admin/knowledge-queue`**：待補知識佇列（GET knowledge-queue），列
   resolved 且 knowledge_ready=false 的卡，剩餘完整度＋深連結問題卡補 spine。
4. **接線**：Sidebar insight 群加項（i18n `sidebar.nav.knowledgeQueue`）＋四站
   rolePolicy `/admin/knowledge-queue`（admin/ops/cs）＋ui-sweep e2e 路由。

## §2 效果

**Gate① enforce config 開關現可由業主開啟**——CR-0132 預設 off 的唯一理由
（無分流欄填寫 UI）已消除。

## §9 驗收

- 四站 tsc 0；brand-portal `next build` 綠（`/admin/knowledge-queue` 入建，61 頁）；
  i18n zh-TW/en 平衡（3112 鍵）；ui-sweep 路由納入。
- 未動後端/型別（`generate-api-types --check` 冪等）。
