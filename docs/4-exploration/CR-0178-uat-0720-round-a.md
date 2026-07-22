# CR-0178 — UAT-0720 輪次 A：外部測試修復（07/08/09/11/04）

- **日期**：2026-07-22
- **來源**：`meetings/20260720 資料/`（三方會議記錄＋Irene Issue list docx）→ Plane「UAT-0720 批次」母卡 seq 40
- **裁決**：業主 2026-07-22 指示「先做 A」（輪次 A＝不需任何人裁決的純工程修復），並確認 09 為要修項
- **branch**：`fix/uat-0720-round-a`

## §1 觸發面向

| 面向 | 命中 | 說明 |
|---|---|---|
| API contract | ✅ | WorkOrder response 新增 `accepted_at`（additive nullable，08） |
| User flow | ✅ | 叫料/通知延遲按鈕 gate（07）、開單預填（09）、SOP 複誦防護（04） |
| DB schema | ❌ | 無 migration（`accepted_at` 欄位既存，僅上 envelope） |
| External integration | ❌ | — |

## §4 變更內容（五張卡）

### UAT-0720-07 叫料/通知延遲按鈕狀態 gate（FE）
後端 `_SUBFLOW_FROM={assigned,accepted,in_progress}` 本來就正確；前端補 gate 讓按鈕在不合法狀態下**灰化＋title 提示**，不再點了才吃 409。
- `web/brand-portal/src/app/work-orders/[id]/page.tsx`：新增 `SUBFLOW_FROM` 常數＋`canSubflow` 派生布林，兩鈕 `disabled`/`title`
- i18n 兩檔：`pages.workOrderDetail.actions.subflowDisabledHint`

### UAT-0720-08 accepted_at 上 envelope＋時間軸（BE+契約+FE）
- `api/services/work_order_service.py`：`_WO_SELECT` append `wo.accepted_at`（index 39，append-only）＋`_wo_row_to_dict` 映射
- `api/models/generated.py`：`WorkOrder.accepted_at`（漏加會被 pydantic 靜默剝除）
- `api/openapi.yaml`：WorkOrder schema 補欄（設計期契約；型別 SoT 仍為 runtime export，CR-0126）
- 型別再生：`./scripts/ci/generate-api-types.sh`（四站 api.generated.ts 同步，並追平 CR-0177 先前未再生的 docstring）
- 前端：SLA 時間軸「接受」節點掛 `timeField: accepted_at`；WorkTimeline 新增「技師接單」事件（含技師 shortId，沿用 scheduledWithTech pattern）；i18n `acceptedTitle`/`acceptedByTech`

### UAT-0720-09 開單表單預填（FE）
後端 `create_from_problem_card` 三層 fallback（caller > pc > profile）既存；補前端 UI 帶入：
- `web/brand-portal/src/app/problem-cards/[id]/page.tsx`：ConvertModal 新增 `initialPhone`（帶 `card.contact_phone`）；姓名/電話 placeholder 註明「留空沿用問題卡／客戶資料」（姓名 `extracted_fields.customer_name` 不在 ProblemCard response，UI 預填需另開 API contract 變更，不混入本輪）

### UAT-0720-11 技師註冊鏡射 R1 加固（BE）
- `api/services/auth_service.py` `register_technician`：三段 `mirror_rows` 包 try/except **fail-soft**（註冊成功＋`logger.error` 大聲留痕指路 `split-tech-db.sh --verify`）。原本未捕捉 → 雙庫部署下鏡射失敗=註冊 500 但權威庫已寫入，重試撞 EMAIL_TAKEN 409（0720 外測「系統發生問題」的活路徑）。語意選 fail-soft 而非 lifecycle 式補償回滾：核准前投影無剛性消費者（審核讀權威庫；派工前 `ensure_technician_projection` 自癒；核准時 lifecycle mirror upsert 補建）
- 配套：`technician_lifecycle_service.py` 鏡射順序 technicians→users 對調為 **users→technicians**（投影側 FK `technicians.user_id→users.id`；否則註冊 fail-soft 後兩列全缺時核准必撞 FK、無法自癒）
- 測試：`test_cr_0115_technician_kyc_register.py::test_register_survives_mirror_failure`（monkeypatch 注入鏡射炸裂）
- **OPS 查核（另行）**：確認雲端 DB 已套 migration 089/081——若未套，UAT 的 500 另有此環境層根因

### UAT-0720-04 SOP 複誦例句防護＋紅燈分流（agent prompt 層）
- `locksmith-cs-sop/SKILL.md` v1.4.0→**1.5.0**：Step 1 新增「複誦例句判別」blockquote（整段原文複誦不視為多重症狀/金錢意圖，請客戶用自己的話描述單一主要症狀；限定整段原文，防過寬誤放行）；第 3 點補「紅燈閃幾次不明先走第 6 點排查」；第 6 點補「常見症狀先自答」（指向 troubleshoot.md 電話可解決清單）——同時涵蓋 UAT-0720-02 的行為面修正方向
- `references/handoff-and-dispatch.md`：例外段補第三條（複誦例句含金錢字眼≠主動詢價）
- 測試：新增 `agent/tests/test_sop_parroting_guard.py`（結構守線 5 案；行為守線需 live LLM，誠實聲明同 test_cr_0074_redline pattern）

## §8 Human Decisions Required

業主 2026-07-22 已裁決：「先做 A」。無其他待決。

### 進度
- ✅ 輪次 A 實作完成（本檔）：agent pytest 18 passed（含新守線 5 案）、brand-portal tsc 乾淨、i18n JSON 合法、api 語法檢查通過。api 新增 component 測試（需真 DB）待安全窗執行——UAT 期間不對 5433 跑（pytest 污染 UAT 庫既有雷）。

## §9 遺留與後續

1. **A-04 發佈路徑（CR-0167 SkillSync）**：SkillSync 啟用且租戶已 publish 過 cs-sop 的環境，builtin 改動被 workspace overlay 遮蔽——需經品牌後台「知識庫>AI 技能」存 draft→admin publish（≤60s 生效）同步 DB 版；未配置/離線環境 builtin 即生效。**收 UAT-0720-04 卡前必查**。
2. **A-11 雲端查核**：migration 089/081 是否已套雲端技師庫。
3. UAT-0720-02 行為重驗：SOP v1.5.0 部署/發佈後，重測「Sherlock H80 紅燈閃爍」情境應先自答排查而非一輪轉真人。
4. 姓名預填（09 殘項）：需把 `extracted_fields->>'customer_name'` 補進 ProblemCard response（API contract 變更），另卡處理。
