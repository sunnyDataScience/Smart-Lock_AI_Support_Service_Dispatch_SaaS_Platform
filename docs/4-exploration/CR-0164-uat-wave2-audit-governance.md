# CR-0164 — UAT 第二波稽核/治理層缺口整補（audit 不可篡改・GDPR・家族覆核 gate・技師憑證投影）

- **日期**：2026-07-11
- **狀態**：🟢 approved — 業主 2026-07-11 裁決 §8 完畢，依 §9 順序實作中（見文末「### 裁決記錄」「### 進度」）
- **觸發面向**：DB schema（audit trigger）、API contract（verify/adopt/forget 端點）、Domain model（工單狀態機）、Architecture boundary（技師身分域投影）、Test plan、合規紅線
- **來源**：UAT 第二波自動驗收（F4/F11/F13/F15/F16/F17/F18）+ 六群影響分析（多 agent，已抽驗 CRITICAL/HIGH）
- **關聯**：CR-0112/0114（技師身分域拆分）、ADR-P014、ADR-0067（M18）、ADR-015（工單狀態機）、ADR-026（pricing snapshot append-only 前例）
- **明細**：`.claude/context/quality/uat-wave2-2026-07-11-findings.md`

---

## §0 摘要

第二波驗收確認的真實缺口高度集中在**稽核不可篡改 + 治理 gate 未強制**，多為合約紅線且功能已建但 gate 未接線。分六群：

| # | 缺口群 | 建議嚴重度 | 核心 |
|---|---|---|---|
| A | audit_events 稽核不可篡改 | HIGH（近 CRITICAL 邊界）| 主稽核表無 append-only trigger；verify 死機制；hash-chain 並發競態 |
| B | tech_mirror 技師憑證洩漏 | HIGH | `SELECT *` 把 password_hash/PII 全欄鏡射到品牌庫 |
| C | F17 家族覆核 gate 未強制 | CRITICAL | adopt SOP 進 KB/RAG 全程不查 family_reviews（合約 4.4d）**⚠️ 含 Source-of-Truth 衝突** |
| D | F18 GDPR forget 三缺口 | CRITICAL | 零 audit / legal-hold 未擋 / 刪除失敗假性成功 |
| E | F15 停權技師孤兒工單 | HIGH | suspend/terminate 不處理名下進行中工單 |
| F | 治理死機制 + spec 分歧（8 條）| 混合 | 含 1 個明確 bug（createSopDraftV2 500）+ RMA 2y/3y 衝突 |

**依 change-governance：本 CR 動到 schema/contract/architecture/合規，實作前須裁決 §8。兩個 Source-of-Truth 衝突（§4）我不腦補選邊，升級給業主。**

---

## §1 事實（逐群，附檔案:行號 + 契約 ID）

### A. audit_events 稽核不可篡改
- **無 append-only trigger**：`audit_events`（public，`Schema_v2_extensions.sql:240`）實查 `pg_trigger` = **0 個**。對照 `saas.config_audit`（`004:114`）、`voucher_void_event`（`010:102`）、`pricing_rule_snapshot`（`098:45`）皆有 `tg_block_mutation`。migration `067-audit-hash-chain` 只加 `prev_hash`/`entry_hash` 欄，**append-only 從未在 DB 落地**。
- **verify 是死機制**：`verify_audit_chain()`（`audit_log_service.py:75`）功能完整但**生產路徑零呼叫**（僅單元測試）。`api/openapi.yaml:911` export 回應含 `audit_log_hash_head`「for downstream verify」——契約已承諾可驗證，卻無 verify 端點。
- **hash-chain 並發競態**：`_latest_entry_hash`（`:50`）SELECT prev 後 INSERT，無 rowlock → 並發寫入產生分叉，`verify` 對合法並發誤判 broken（correctness bug）。
- **契約**：`05_NFR.md:160` **NFR-Aud-001（合約下限）**「append-only + hash chain 完整性可驗證」。⚠️ code/067 內自創 ID「TI-AUDIT-03」在 smartlock-docs **查無**，正典為 NFR-Aud-001。

### B. tech_mirror 技師憑證洩漏
- `core/tech_mirror.py:63` `SELECT * FROM {table}` 把技師 users **全 24 欄**（含 `password_hash`/`email`/`phone`/`address`）從權威庫(5434)鏡射到品牌庫(5433)。實查品牌庫 `role='technician'` 6 列 password_hash 為**有效 bcrypt**、email/phone 明文。抵銷 CR-0112「憑證集中權威庫」目的。
- **品牌側實際只讀**這些投影欄：登入驗證（`auth_service:39/165/225`）用 `id/email/password_hash/role/tenant_id/is_active/locked_until`、每請求 A2/A3（`core/auth.py:124`）用 `is_active/password_changed_at`、A1 lockout 用 `failed_login_attempts/locked_until`。**技師顯示名/電話品牌側一律讀 `technicians` 表非 users 投影**。→ 白名單可安全排除 password_hash/email/phone/address，**但前提是技師登入驗證讀路徑先移轉到權威庫**（否則砍欄=技師登入壞掉）。
- **文件 drift**：`13_Security_Architecture.md:184/247` 已宣稱「投影欄位最小化(ADR-P014)」為現行緩解，**實作未做**。

### C. F17 家族覆核 gate 未強制 ⚠️ 見 §4 衝突
- `sop_draft_service.py:361` `adopt_draft`（approved→published+INSERT case_entries）**全函式無 family_reviews 查詢**，只判 status='approved'。`review_draft:303`（pending→approved）本就不該有（初審在前）。
- 兩條 adopt 軌（`sop_drafts.py:129` v1 + `sops_v2.py:388` v2）都呼此函式，**前端 knowledge-base/sop-drafts UI 已接**、:8001 掛載——非隱藏功能。
- 設計本意 family review 應 gate 在 approved→published 之間：`family_review_service.py:171` `create_review` 要求 status='approved'、強制雙審 distinct（覆核者≠初審 admin）、hash-chain ledger；`list_pending:84`「approved 且 NOT EXISTS family_reviews」即待覆核佇列——**架構設計了這一關，adopt 端沒接上**。
- **rejected 不退回 status**（`family_review_service` docstring）→ gate 若只判「存在」而非「action='approved'」，被退件草稿仍可 adopt。

### D. F18 GDPR forget 三缺口
- **零 audit**：`gdpr_forget_service.py` 全檔 355 行 `log_event` 命中 **0**。六個 op 皆不寫稽核。契約 `04_SRS.md:307` FR-API-16「全程 append-only audit」、`TC-COMPLIANCE-02(P0)` 要 `gdpr_forget_blocked` event（全 repo grep 0）。
- **legal-hold 未擋**：`soft_delete:177` 唯一守門 `status=='received'` 即清 PII，不查 `media_files.legal_hold`（欄位存在，`066:7`），無 423 路徑。靠 admin 手動先 deny 且順序相依（違 `TC-COMPLIANCE-02` P0）。
- **假性合規**：`hard_delete:267` `DELETE FROM users` 包 try/except 後仍標 `status='hard_deleted'`。FK（complaints/disputes/refund_requests/warranty_claims/… 對 users NO ACTION）阻擋時，資料還在卻回報已刪。

### E. F15 停權技師孤兒工單
- `technician_lifecycle_service.py:84` `_change_status_and_audit`（suspend/terminate/reject/approve/reactivate 共用）只改 status/is_active/mirror/audit，**從不 query work_orders** → 名下 assigned/accepted/in_progress 工單成孤兒。
- 契約 `08_User_Flow.md:387` UF-10#11「停權→進行中工單改派」；實作只做了「移出新派工候選集」（`dispatch_service.py:129`），**改派沒做**。`21_Traceability:90` FR-0044 標 🟡。
- 改派能力已存在（`reassign_order`），但**強制要 new_technician_id 且新技師須 active**，無「退回派工池/unassign」路徑（ADR-015 狀態機無 assigned→created）。
- 附評：`technician_brand_authorization` 僅 seed（is_mock），**執行期無授/撤 live API**——撤證即時移出候選集無真實產品路徑。

### F. 治理死機制 + spec 分歧（8 條）
1. `webhook_idempotency` 表建了零 runtime 使用（`Schema_cr0001:38`）→ LINE 重送 DB 層未去重，只有 in-process（`inbound_debounce.py:8`），多實例失效。
2. `owner_role_codes` 死欄位（`004:58`）→ per-namespace owner 治理未實作，寫死 admin-only。
3. M18 config **無「受保護層」機制**（`config_m18*` 無 protected 實作）→ 任何 FULL_ACCESS 可改任意 namespace。
4. instant rollout autocommit 部分狀態（`config_m18_service:377`）+ X-Initiator/Approver header 不驗 UUID/不綁 JWT → 審計斷鏈。
5. **createSopDraftV2 500**（`POST /tenants/{t}/sops/drafts` kwargs 與 service 簽章不符）→ 端點 100% 壞。**單函式 bug，change-governance 豁免 CIA，可即修。**
6. RMA retention **2y vs 3y** ⚠️ 見 §4 衝突。
7. F4「3 次收不齊自動轉真人」機制不存在——`locksmith-cs-sop:48` 刻意否決硬規則。spec↔實作分歧。
8. audit/log 無系統性 PII 遮蔽，`llm_usage_log` 存客戶原文明文（現 0 列，設計風險）。

---

## §2 影響分析（修法會觸及什麼）

| 群 | DB schema | API contract | 既有測試（破壞性）| ADR/文件 | 前端 |
|---|---|---|---|---|---|
| A | 新 migration 掛 trigger（複用 098 pattern）| 加 verify 端點→同步 openapi.yaml | **5 測試檔 DELETE/UPDATE audit_events 會被擋**（test_cr_0068 竄改測試最棘手）；生產碼**零** UPDATE/DELETE | 宜新開 audit append-only ADR | 無 |
| B | users 結構不變；一次性 migration 清空投影列敏感欄 | 無 REST 契約變動（內部雙寫層）| auth 登入測試連動；補「投影不含 password_hash」斷言 | 對齊 ADR-P014（過渡非終態）；13_Security drift 需銷案 | 無（技師名/電話來自 technicians 表）|
| C | Option1 無 migration；Option2 需新狀態欄 | adopt 新失敗模式→改 openapi 兩 operation | TC-COMPLIANCE-05 P0 目前**假綠**（無通過測試）；需補 adopt-gate 測試 | Option3 需 ADR 記載事後履約 | adopt 按鈕需「先完成家族覆核」導流 |
| D | audit event_type 純字串免 migration；FK 方案需改多表 | soft-delete 加 423、hard-delete FK-blocked 改 409（破壞「一定成功」前端假設）| 補 forget audit/legal-hold 測試 | — | GDPR 頁加 423 分支 |
| E | 偵測用現有欄免 migration；退池方案需動狀態機 | 復用 reassignWorkOrderV2 無新端點；阻擋方案 suspend 多 409 | 補孤兒案例 | 退池方案觸及 ADR-015（須新 ADR）| 停權後 admin 看「名下孤兒工單」提示 |
| F | (5) 純 bug 無 schema；(3) 保護層可能加 is_protected 欄 | (5) 修單端點；(2)(4) 動 RBAC/SoD 契約 | (5) 補端點測試 | (2) 牽動 ADR-0067 | (3) M18 頁 |

---

## §4 ⚠️ Source-of-Truth 衝突（依 change-governance 不腦補，升級裁決）

### 衝突①（C 群 F17）— 家族覆核 4.4(d) 履約模型互斥
- **`TC-COMPLIANCE-05`（Test Cases, P0）**：adopt 無 family review **必須失敗**（硬 gate）。
- **`BR-AUDIT-01`（BRD）+ `13_Security`**：4.4(d) 以**事後 event-log 非阻擋**履約。
- 兩者對同一 4.4(d) 互斥。`FR-REF-05`（SRS）偏硬 gate、`BR-AUDIT-02` 偏事件。**須業主裁決履約模型**，我不選邊。

### 衝突②（F 群 #6）— RMA retention 保留年限
- **`Q027`（業主既往裁決）**：RMA 保留 **2 年**（現行實作 `media_service.py:158` 即 2y）。
- **`NFR-Priv-003`/`NFR-Aud-003`（合約下限）+ R-F4（合約紅線）**：RMA **+3 年**。
- Q027 無文件出處、NFR 標合約下限。**須業主確認哪邊是 source of truth**（改 code 到 3y，或改 NFR 文件對齊 2y 並銷 R-F4）。

---

## §8 🛑 Human Decisions Required（請逐項裁決；未裁決不動 code）

### 全域範圍決策
- **D0**：本 CR 屬 M2 後段治理/合規面，**不在已測的 F1 營運主鏈**上，但多為合約紅線明列驗收。整體時程取向＝(a) 本輪盡量補齊合規紅線、(b) 只修低風險高價值、其餘正式排 M3、(c) 全延 M3 僅文件標注避免假綠？

### A. audit 不可篡改
- **A1** 嚴重度：append-only 未於 DB 強制 + tamper-detection 從未接線 → 認定 critical（合約下限未達標）還是 high？
- **A2** 範圍：本輪補 trigger（預防）+ verify 端點（偵測），競態延 M3【推薦選項 B】；或只上 verify 延 trigger（選項 C）；或一次到位含競態（選項 A）？
- **A3** ⚠️ retention 衝突：audit_events 有 `retention_days=90`，NFR-Aud-001 又要 eternal → no-delete trigger 與 purge 衝突。裁決＝(a) audit 全量 eternal 拿掉 purge、(b) trigger 開特權 purge 例外、(c) 依 event_type 分級（financial/admin 7y、conversation 90d）？
- **A4** verify 端點歸屬：audit_events 無 tenant_id → platform-level（platform-console 專用）？授權給哪些角色？

### B. tech_mirror 憑證投影
- **B1** 確認 HIGH 且本輪修【推薦選項 B：移轉技師 auth 讀路徑→權威庫 + 品牌投影最小化 + 回填清空】？或接受風險延 M3 隨 ADR-P014 Kafka CQRS（選項 C，需你風險接受簽章）？
- **B2** 白名單：品牌投影技師 users 保留 `{id, tenant_id, role, is_active, failed_login_attempts, locked_until, password_changed_at}`，排除 password_hash/email/phone/address——確認清單？
- **B3** 是否核准一次性 migration **清空**品牌庫既有技師投影列的 password_hash/email/phone/address（排在讀路徑移轉之後）？
- **B4** `13_Security_Architecture.md` 文件↔實作 drift：本輪補實作對齊，還是先標注？

### C. F17 家族覆核 ⚠️
- **C1（衝突①）**：4.4(d) 履約模型＝**硬 gate**（adopt 無覆核即失敗）還是**事後 event-log 非阻擋**？（推薦硬 gate，符 TC-COMPLIANCE-05 P0）
- **C2**（若硬 gate）gate 判定：只判「family_review 存在」不夠（rejected 不退 status）→ 應判「action='approved' 的 family_review 存在」，確認？
- **C3** gate 錯誤碼：409 / 425 TOO_EARLY（與 sops_v2 一致）/ 403 擇一？
- **C4** 範圍是否含第二軌 refinery publisher（knowledge-pipeline 直落 RAG、無 family review 概念）？
- **C5** 既有透過無 gate adopt 發布的 case_entries（source='sop_approved'）→ 回溯標記/隔離/重審，還是既往不咎？
- **C6** reviewer 缺席 >24h 暫停+escalate（FR-REF-05）本輪或延 M3？

### D. GDPR forget
- **D1** 語意：GDPR Art.17「匿名化等同抹除」可否接受為終態？即 soft_delete 已 redact PII 後，hard_delete 遇 FK 阻擋採「匿名化即完成」【推薦方案 A】，還是必須實體 DELETE（方案 B，改多表 FK）？
- **D2** legal-hold 前置該擋什麼：(a) 只擋名下 legal_hold=true 的 media_files；(b) 連未結 disputes/complaints 也擋？
- **D3** 範圍：三缺口本輪全修（方案 A）還是僅 audit 本輪、legal-hold+FK 延 M3（方案 C）？
- **D4** 嚴重度：gap3「對未刪資料回報已刪」認定 critical（合規誠信、硬擋 release）？

### E. F15 孤兒工單
- **E1** 語意：停權/終止孤兒工單處理＝**阻擋（先改派）**【推薦：suspend 軟阻擋可 force、terminate 硬阻擋】/ 告警+人工 / 自動改派退池（動 ADR-015）？
- **E2** 範圍：處理哪些狀態？assigned/accepted（未動工）vs in_progress（現場施工中，換人牽涉簽名/報價）是否分流？
- **E3** 品牌授權撤證無 live API（附評）：本輪補整個管理面（CRUD+撤證事件）還是延 M3？

### F. 治理死機制 + 分歧
- **F1** #5 createSopDraftV2 500：**change-governance 豁免（單函式 bug），確認本輪即修**（對齊 v1 簽章）？
- **F2（衝突②）** RMA 2y vs 3y：哪邊 source of truth？改 code 到 3y，還是改 NFR 文件對齊 2y+銷 R-F4？
- **F3** #7 F4「3 次自動轉」：確認 SOP 刻意否決為正典設計，據以文件銷案該 spec？
- **F4** #1 webhook_idempotency / #2 owner_role_codes / #3 保護層 / #4 header 綁 JWT / #8 PII 遮蔽：逐項＝本輪修 / 延 M3 / 確認為刻意設計銷案？（多屬 RBAC/契約語意變更，建議延 M3 走各自 CR，本輪僅文件標注避免假綠）

---

## §9 建議實作順序（**待 §8 裁決後才適用；此處為預排**）

假設業主採各群「推薦選項」+ 合規紅線本輪修，建議順序（每步一 branch、獨立可驗）：

1. **F1 createSopDraftV2 500**（豁免 CIA，立即可修，止血壞端點）
2. **A：audit trigger + verify 端點**（先裁 A3 retention）——合規基石，其他 audit 依賴它
3. **D：GDPR forget audit + legal-hold + 移除靜默吞例外**（方案 A）——依賴 A 的 audit 已強制
4. **C：F17 家族覆核硬 gate**（先裁 C1 衝突）——合約紅線 CRITICAL
5. **B：tech_mirror 讀路徑移轉 + 投影最小化 + 回填**——需仔細測技師登入
6. **E：孤兒工單偵測+阻擋**（復用 reassign）
7. **F 其餘**：依 F4 裁決分別排 M3 或本輪文件標注

> 實作完成後：更新本 §8「### 進度」、CHANGELOG、TM traceability、必要 ADR（append-only audit / 4.4d 履約模型 / ADR-015 若動狀態機）。

---

## 裁決記錄（業主 2026-07-11）

- **D0 = A**：本輪補齊合約紅線（A audit / D GDPR / C 家族覆核 gate / B tech_mirror）；F 群治理死機制（webhook/owner_role_codes/保護層/header-JWT/PII 遮蔽）延 M3、文件標注避免假綠。
- **A**（audit）：採選項 B — trigger（含 session_replication_role='replica' 特權繞過）+ verify 端點（platform-level，admin/ops）；競態延 M3。A3 retention＝以特權繞過供未來 purge、目前 audit 實質 eternal（無 purge job）；嚴重度 high。
- **B**（tech_mirror）：採選項 B — 移轉技師 auth 讀路徑至權威庫 + 品牌投影最小化（白名單 `{id,tenant_id,role,is_active,failed_login_attempts,locked_until,password_changed_at}`）+ 一次性 migration 清空既有投影列 password_hash/email/phone/address；補實作對齊 13_Security。
- **C**（家族覆核）：**硬 gate**（衝突①裁定）。gate 判「action='approved' 的 family_review 存在」；錯誤碼 425 TOO_EARLY（與 sops_v2 一致）；本輪 gate api adopt 軌（reachable+UI wired），refinery publisher 軌俟其啟用另處理；既有無 gate 發布的 case_entry 若存量則標記待重審。
- **D**（GDPR）：採方案 A — 匿名化即終態（FK 阻擋不視為失敗）+ legal-hold 前置擋（名下 media_files.legal_hold=true → 423）+ 移除靜默吞例外 + 全流程補 audit；三缺口本輪全修；gap3 認定 critical。
- **E**（孤兒工單）：偵測+阻擋，suspend 軟阻擋（可 force 旗標）、terminate 硬阻擋，復用 reassignWorkOrderV2；不動 ADR-015 狀態機。品牌授權撤證 live API 延 M3。
- **F**（雜項）：#5 createSopDraftV2 **本輪即修**（豁免 CIA）；#6 RMA **改 code 至 3 年**（衝突②裁定：NFR 為正典，推翻 Q027 的 2y）；#7 F4 3-strike 確認 SOP 刻意設計、文件銷案；#1/#2/#3/#4/#8 延 M3 文件標注。

## 進度

（依 §9 順序，每步一 branch，完成補一行 ✅ Sx done（merge <sha>）：<成果>）

- ✅ S1 done（`50b7bfa7` branch fix/create-sop-draft-500）：F#5 createSopDraftV2 500 修復（對齊 v1 契約、typed body）；新測 2＋v1 迴歸 5。
- ✅ S2 done（`8b1b26cb` branch fix/cr0164-audit-immutable）：A audit_events append-only trigger（migration 100）+ verify 端點接線 + 5 測試檔特權繞過；audit 87 tests 全綠。競態延 M3。
- ✅ S3 done（branch fix/cr0164-gdpr-forget）：D GDPR forget 三修（全流程 audit + legal-hold 423 + 匿名化即終態不假性成功）；GDPR+audit 28 tests 全綠。
- ✅ S4 done（branch fix/cr0164-family-gate）：C 家族覆核硬 gate（adopt 無 action='approved' 覆核 → 425；衝突①裁定硬 gate）；新測 3＋sop/family 迴歸綠。
- ✅ S5 done（branch fix/cr0164-tech-mirror-pii）：B tech_mirror users 投影白名單（不含憑證/PII）+ 技師登入 lookup 改讀權威庫 + 防呆回填腳本（非 migration，防單庫誤清）；217 auth/mirror 迴歸綠 + live 拆庫技師登入 200。
- ✅ S6 done（branch fix/cr0164-orphan-wo）：E 停權/終止孤兒工單偵測+阻擋（suspend 軟阻擋可 force、terminate 硬阻擋，復用 reassign）；新測 4＋lifecycle 迴歸 21 綠。
