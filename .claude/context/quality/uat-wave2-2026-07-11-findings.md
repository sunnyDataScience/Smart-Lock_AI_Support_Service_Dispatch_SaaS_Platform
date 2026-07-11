# UAT 第二波自動驗收結果（2026-07-11，校正後）

- **方法**：F4/F11/F13/F15/F16/F17/F18 共 7 場景各一 agent 對 live 環境實測（隔離資料、驗後即清、bug 標 confidence）；主 agent 抽驗 CRITICAL/HIGH 去偽。
- **結果**：42 checks / 28 pass；20 bugs。**這波品質高（多 live-confirmed）**，主軸＝稽核/合規/治理層缺口。已抽驗確認 CRITICAL + 2 HIGH 屬實。
- **清理**：全數 e2etest 資料已清（含 F16 config 殘留——config_audit append-only 擋刪，暫停 trigger 清我方測試列後**已復原並實測保護恢復**；namespace 回 20）。**F13 乾淨無 bug**（8/8，M3 開站自動化正確標 not_covered）。

## 已抽驗確認（真實、我親自複驗）
- **[CRITICAL] F17 家族覆核 gate 完全未強制**（api SOP 採納軌）：`review_draft`（pending_review→approved）與 `adopt_draft`（approved→published+case_entry）皆只檢查 status，**全程不查 family_reviews**。migration 074/CR-0079 標家族覆核為合約 4.4d 紅線（違反=合約終止）。端點 `/api/v1/sop-drafts/{id}/adopt`＋`/tenants/{t}/sops/drafts/{id}/adopt` 皆在 :8001 掛載、**前端 knowledge-base/sop-drafts UI 已接**→操作員可透過 UI 把 SOP 發布進 KB/RAG 而繞過覆核。非隱藏功能。已驗端點可達＋UI wired。
- **[HIGH] audit_events 無 append-only trigger**：`pg_trigger` 實查 = 0 個（對照 saas.config_audit 有 2 個 no_update/no_delete）。承載財務/派工/安全事件的主稽核表可被 UPDATE/DELETE 無痕改刪。migration 067 只加 hash 欄未建 trigger。同專案 config_audit(004)/voucher_void_event(010)/pricing_rule_snapshot(098) 皆有保護，唯獨 audit_events 漏。live-confirmed。
- **[HIGH] tech_mirror 投影未最小化**：`core/tech_mirror.py:62` 用 `SELECT *` 把 users 全 24 欄（含 password_hash/email/phone/address）從技師權威庫(5434)鏡射到品牌庫(5433)。抵銷 CR-0112 拆身分域「憑證集中權威庫」的目的——品牌庫外洩即洩全體技師登入憑證。live-confirmed（讀碼＋實查投影列 password_hash 為有效 bcrypt）。

## 真實但待業主排修 / 裁決（confidence 標記可信）
### HIGH（合約/合規紅線）
- **GDPR forget 全程零 audit**（gdpr_forget_service 無任何 log_event）——最敏感的 PII 刪除無稽核軌跡（違 FR-API-16/NFR-Priv-005）。
- **legal-hold 保護未落地**：forget 不查 media_files.legal_hold，無 423 路徑，靠 admin 手動先 deny 且順序相依（違 TC-COMPLIANCE-02 P0）。
- **hard/soft_delete 靜默吞例外**：DELETE FROM users 包 try/except 後仍標 status='hard_deleted'→FK 阻擋時假性合規（資料還在卻回報已刪）。
- **停權/終止技師孤兒工單**：`technician_lifecycle_service:84` suspend/terminate 不檢查名下 in_progress 工單，無改派無告警。

### MEDIUM
- audit_events live 為空表（audit 疑未接進業務流程；log_event best-effort 吞錯）。
- verify_audit_chain() 無呼叫者/端點——hash-chain 竄改偵測是死機制（配合 audit 無 trigger＝兩道防線皆失效）。
- webhook_idempotency 表建了零 runtime 使用——LINE webhook 重送 DB 層未去重（跨實例/重啟無防護）。
- owner_role_codes 死欄位——per-namespace owner 治理未實作，寫死 admin-only。
- M18 config 無「受保護層」機制（S5 保護層 override 擋無實作）。
- instant rollout autocommit 部分狀態＋X-Initiator/Approver header 不驗 UUID（審計斷鏈）。
- createSopDraftV2 kwargs 與簽章不符 → 500（v2 建 SOP 草稿端點壞）。
- 品牌授權撤證無 live 管理 API（technician_brand_authorization 僅 seed，執行期不可授/撤）。
- 家族覆核 reviewer 缺席 >24h 升級未實作（端點對外宣稱 SLA 24h）。
- RMA +3 年 retention 未實作（實作最長 2y——Q027 裁 2y 與 UX doc 3y 分歧）。

### LOW / 設計分歧（需裁決非 bug）
- **F4「3 次收不齊自動轉」機制不存在**——locksmith-cs-sop 刻意否決硬規則，改缺項一次全列。spec↔實作分歧，需對齊驗收措辭。
- audit/log 無系統性 PII 遮蔽，llm_usage_log 存客戶原文明文（現 0 列，設計風險）。
- hash-chain prev_hash 並發競態（suspected，未壓測）。

## 無法自動驗（需業主/其他手段）
- LLM 是否真的呼叫 transfer_to_human（F4，需 eval）
- 月結/24h reviewer 升級等跨日 cron（走 GCP Cloud Scheduler）
- WS 即時推送/斷線重連、跨租戶第二 admin token、金額商業正確性

## 觀察：wave2 主軸
真實缺口高度集中在**稽核不可篡改（audit_events/GDPR/config 審計斷鏈）＋治理 gate 未強制（家族覆核/受保護層/legal-hold）**——多為合約紅線且功能已建但 gate 未 wire。這些偏 M2 後段治理面，不在業主已測的 F1 營運主鏈上，但驗收合約明列。
