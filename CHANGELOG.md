# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-Q2 Tactical Refactor

### Decisions

- **WBS 1.2.7.3.2 / 3 / 4 取證 audit — 校正全 ⬜ 真實 ~52%**（branch `docs/wbs-1.2.7.3-audit-remaining`，2026-06-05）：續推 1.2.7.3 整合測試段剩 3 項。**取證**：(1) **1.2.7.3.2 V1/V2 資料流驗證 → ~30%**：grep parity/dual_write 全空無 automated test，但 v1/v2 共用 service+DB 隱含一致 + Deprecation header middleware + cross-tenant guard 對齊 = code-level 一致性已保證；無 black-box parity test。**不立即補**：P3.5 cutover 完成 + 剩 41 個 v1 caller P4 階段廢除 → 寫 parity test 在「即將廢棄」雙軌期反向消耗。/ (2) **1.2.7.3.3 100 人併發壓測 → 0%**：find k6/locust/artillery 配置全空，無工具/scenario/SLA baseline。**建議開 CR-0019** 工具選型 + SLA 目標 CIA。**不立即做**：需業主裁決 SLA + 工具引入觸發 Architecture boundary CIA。/ (3) **1.2.7.3.4 行動裝置相容 → ~50%**：playwright.config.ts tech project Pixel 7 viewport ✅ + PWA manifest + responsive Tailwind ✅；但 iOS Safari 實機 / BrowserStack 帳號 / 多機型矩陣 ❌。**不立即補**：需業主提供 cloud testing 帳號（採購決策）+ 屬上線前 manual QA 性質。**1.2.7.3 整合測試段真實平均 ~52%**（校正前報告標全 ⬜ 0%）：1.2.7.3.1 ✅ 80%+ / 1.2.7.3.2 ⚠️ 30% / 1.2.7.3.3 ❌ 0% / 1.2.7.3.4 ⚠️ 50% / 1.2.7.3.5 ✅ 100%。**P0 段（E2E + 會計）達 UAT 前置要求**；P1 段（V1/V2 parity + load + 跨裝置）需業主資源解凍。詳見 [`docs/_audit/wbs-1.2.7.3-2-3-4-audit.md`](docs/_audit/wbs-1.2.7.3-2-3-4-audit.md)。

- **Agent 核心架構重寫 → LockCore + Agent Skills 標準**（branch `feat/agent-update`，2026-06-04）⭐⭐⭐ **重大架構決策**：捨棄舊架構（ReAct + LangGraph、自製 skill loader、product_info mega-doc、Belief-Augmented ReAct (Turn Cycle)、quality_check LLM-as-Judge），改為：
  * **核心引擎**：`agent/lockcore/`（fork 自上游 `HKUDS/nanobot` 的最小核心套件，VENDOR.md 記載 fork 來源）
  * **知識 & SOP**：`lockcore/skills/{locksmith-product-knowledge,locksmith-cs-sop}/SKILL.md + references/`（**Agent Skills 標準** agentskills.io / Claude Skills，frontmatter 不綁框架專屬欄位，可攜性：可複製到 Claude Code / Cursor / nanobot / hermes 直接使用）
  * **LLM 供應商**：單一 `LiteLLMProvider`，多家用 model 字串路由（`gemini/` / `vertex_ai/` / `ollama_chat/` / `claude-*` / `gpt-4o`）
  * **Per-user 記憶**：`lockcore/agent/user_memory/`（移植自 Hermes，`tenant + user_id` 為 key，BUILD/SAVE 接 turn 狀態機；SQLite memory.db 為預設）
  * **工具白名單**：`lockcore/app_config.py:CS_TOOL_ALLOWLIST` = `{read_file, list_dir, find_files, grep, web_search, transfer_to_human}`（客服 only，砍 write/exec/shell/spawn/cron/message/web_fetch/image 等危險或無用工具）
  * **測試**：改 `pytest` in `agent/tests/`（13 個 unit/integration，含 `test_e2e_mock_turn.py` / `test_skills_loaded.py` / `test_tool_allowlist.py` / `test_litellm_provider.py` / `test_line_gateway.py`）；**舊 quality_check / belief_action_judge / replay_check / hypothesis_quality_baseline 全刪**
  * **影響檔案**：200+ 刪除（`app.py` / `agent.py` / `harness/` 26 檔 / `evals/` / `quality/` / `prompts/` / `notifications/` / `skills/tools.py` / `storage/` / `profiles/` / `llms/` / `embeddings/` / `memory/` / `integrations/` / `policy.py` / `calibrate.py` / `hypothesize.py` / `turn_cycle.py` / `belief*.py` / 45 個 product_info `.md` mega-doc）；178 新增（`lockcore/` 全結構）
  * **CLAUDE.md 同步重寫**：§🔒 Architecture Lock 整段重寫（product_info canonical → lockcore + Agent Skills），§🧪 Experimental Lock 刪除（Turn Cycle 全失效），最常用指令改 `pytest` / `real_turn_demo.py` / `line_gateway.py`，非預期工具鏈補 `pip install -e ".[dev|vertex|line]"` optional dependencies pattern
  * **`.gitignore` 補 `agent/memory.db`**（per-user SQLite runtime DB，重啟可重建，不入版控）
  * **後續 ADR 工作**：ADR-0008 (product-info-architecture-canonical) / ADR-0010 (belief-augmented-react) / ADR-0101 (product-info-extension-final-spec) 待補 `status: superseded_by: <新 ADR>` 標記（**OOSCope of 本 commit**，另開 ADR 化 governance CR）
  * **CIA 後補（gate bypass acknowledgment）**：本變更觸發 Architecture boundary（最高觸發面向），但 code 已由業主完成，屬 post-hoc documentation update；後續若有人質疑變更合法性可引用本 CHANGELOG entry + agent/README.md + lockcore/VENDOR.md
  * 詳見 [`agent/README.md`](agent/README.md) + [`agent/lockcore/VENDOR.md`](agent/lockcore/VENDOR.md)。

- **CR-0012 opened — FR-0012 技師月結撥款 CIA**（branch `docs/cr-0012-fr-0012-monthly-settlement-cia`，2026-06-04）：CR-0010 HD-03=a batch 第 2 件。FR-0012 為 V1.0 金流閉環另一半（CR-0011 客戶付平台 + CR-0012 平台付技師）。取證確認：`settlements_v2.trigger_monthly_settlement` 為 **501 stub**（Phase II 標記）、`settlement_service` 無 monthly trigger / compute_payouts / payout_via_bank、BR-M12-NN 5 條未編號、ADR-0041 (travel fee 80/20) accepted 但 split 邏輯未進計算公式。CIA 列 **6 HD** 待業主裁決：(1) Bank payout provider（台銀 / 第三方 AP / manual CSV / 階段化）、(2) Cron 排程實作（APScheduler / Cloud Scheduler / pg_cron / GitHub Actions）、(3) Bank 3-retry 策略、(4) manual_payout 完結機制、(5) Dispute 排除實作（即時查 / flag-driven / 雙保險）、(6) Escrow 模型（**鏡像 CR-0011 HD-08，須同步裁決避免金流方向矛盾**）。建議 HD-01=(c) manual CSV 階段化 → 解 vendor 契約 review 拖延風險。status: `open-awaiting-decisions`。詳見 [`docs/_audit/CR-0012-fr-0012-monthly-settlement-cia.md`](docs/_audit/CR-0012-fr-0012-monthly-settlement-cia.md)。
- **CR-0011 opened — FR-0011 消費者付款 CIA**（branch `docs/cr-0011-fr-0011-consumer-payment-cia`，2026-06-04）：執行 CR-0010 HD-03=a「同步開 CR-0011~0014 審查其他 4 draft FR」首件。FR-0011 為 4 剩餘 draft FR 中**最大金流風險**（V1.0 主流 spec、blocked_by Q7=B provider 選型、payments 表/endpoint 0 實作）。CIA 列 **8 HD** 待業主裁決：(1) provider 選型範圍 Line Pay only vs 雙軌/三軌、(2) ≥50000 強制簽章機制、(3) Line Pay fallback 觸發時機、(4) 現金 dispute 介面、(5) 7y voucher retention 實作、(6) webhook idempotency_key 設計、(7) provider 簽章驗證、(8) M11 即時付款 vs M12 月結金流關係。CIA 結構含 §1~12 + §A 取證附錄；implementation 切到後續 CR-0011-BUILD 不在本 CR scope。status: `open-awaiting-decisions`。詳見 [`docs/_audit/CR-0011-fr-0011-consumer-payment-cia.md`](docs/_audit/CR-0011-fr-0011-consumer-payment-cia.md)。
- **CR-0005 step 3/3 — KB :export caller 遷 v2 + :search caller flat-path 修正**（branch `feat/cr-0005-export-caller-v2`，2026-06-04）：
  * **:export caller**：`web/src/app/knowledge-base/cases/page.tsx` :export 從 v1 async-job（POST → KbExportJob → fetch download_url → JSONL blob）改為 v2 同步 CSV stream（`POST /kb/documents:export?doc_type=case&format=csv[&brand=X]` → blob → `kb-cases-{YYYY-MM-DD}.csv`）；UI scope dropdown 簡化為單一 button（HD-06=a MVP scope=case-only，manuals export 待 HD-04 ClamAV upload + manual_service search 補完另開）。
  * **:search caller flat-path 修正**：commit `87c6aa5d` 寫成 `tenantPath("/kb/documents:search")` → 解析為 `/tenants/{tid}/kb/documents:search`，但 kb_v2 router 全部 endpoint 為 flat（取證：`uv run python -c "from routers import kb_v2; [print(r.methods,r.path) for r in kb_v2.router.routes]"` 全部 `/kb/documents...`），且 main.py 無 tenant strip middleware → 該 caller 線上應為 404。本 commit 改回 flat `"/kb/documents:search"`，與 `tenantPath` docstring 對齊；順手移除已無用的 `tenantPath` import。
  * 同步清理失效 i18n keys（scopeAll / scopeAllHint / scopeManuals / scopeManualsHint / scopeCasesHint / exportLimitedToBrand / exportNoUrl）。
  * **真實 v1 caller 42 → 41**（:export 推進）。
- **CR-0013 opened — FR-0022 消費者端工單追蹤 CIA**（branch `docs/cr-0013-fr-0022-consumer-tracking-cia`，2026-06-04）：CR-0010 HD-03=a batch 第 3 件。**FR-0022 為「準完工 status flip 候選」**（類似 FR-0019 經 CR-0010 promote 模式）：取證確認 Web token 路徑已 100% 實作（`consumer_v2.py:80 GET /consumer/work-orders/{trackingToken}` + `web/track/[token]/page.tsx`）+ ADR-0015 (PM-Q3) accepted → `blocked_by: Q3=C` 為 stale；LINE rich menu 路徑 0%（grep richmenu / LINE_RICHMENU 全空，agent webhook 只有 F2 改期 postback 無「查進度」handler）。**取證捕獲 1 個 spec/code 衝突**：FR-0022 §1.2 A1「Web token mismatch → 401」vs `consumer_v2.py:63` 註解「失敗一律 404，不洩露原因」— **HD-05 強制裁決** 401（明確）vs 404（防 enumeration）vs 400（中庸），不允許腦補。CIA 列 **5 HD**：(1) LINE 入口策略（rich menu / ReAct 自然語言 / 雙路 / 純 Web）、(2) 多單顯示策略、(3) LINE binding 機制（自動 / 主動 / 雙路；HD-03=auto 涉 PDPA 同意）、(4) Web token TTL（24h / 7day / 30day / infinite）、(5) 401 vs 404 spec/code 衝突解。status: `open-awaiting-decisions`。詳見 [`docs/_audit/CR-0013-fr-0022-consumer-tracking-cia.md`](docs/_audit/CR-0013-fr-0022-consumer-tracking-cia.md)。
- **CR-0014 opened — FR-0034 AI Employee Charter / PRD 治理 CIA**（branch `docs/cr-0014-fr-0034-ai-employee-charter-cia`，2026-06-04）：CR-0010 HD-03=a「同步開 CR-0011~0014 審查其他 4 draft FR」**收尾件**。**性質與其他 3 件不同**：FR-0034 屬 Phase II 骨架 + Q2=C 延後正當狀態，**本 CR 結論可能為「維持 draft」而非推進**。取證確認：(1) ADR-0028 (AI Employee Charter) accepted，Charter rule body 95% 已存在；(2) BR-A12-01/02 active；BR-A12-NN placeholder；(3) Forbidden 清單 prompt-level 已落地（`agent/harness/safety_gate.py` + `agent/config.toml [output_validator] forbidden_phrases`）；(4) AI 永禁核准退款 ADR-0040 與 ADR-0028 對齊（CR-0009 refunds:agent-initiate single-actor 已落地）；(5) **Off-board Triggers (KPI<70% 連 2 週 → 48h hand-off) + Promotion 條件 (KPI 4 週全綠) 為 ADR-0028 implementation gap，純 ops 流程無 code 落地**；(6) M20 mapped_to 重疊 **8 FR**（FR-0017/0028/0029/0030/0034/0048/0050/0051）職責切分待 governance 統合。CIA 列 **4 HD**：(1) FR-0034 status 處理（推薦 (a) 維持 draft 加 acknowledged，尊重 Q2=C 延後）、(2) BR-A12-NN 編號（推薦 (a) BR-A12-03 引用 ADR-0028 避免雙 source of truth）、(3) ADR-0028 implementation gap 處理（推薦 (a)+(c) Phase II checklist + PROC runbook）、(4) 8 FR M20 重疊釐清（推薦 (a) 另開 governance CR）。**若業主依推薦立場全選，北極星 (1) 4 → 3 不會推進** — FR-0034 維持 draft 但 explicit acknowledged 為 reality-aligned；CR-0011/0012/0013 才是真實推進路徑。status: `open-awaiting-decisions`。詳見 [`docs/_audit/CR-0014-fr-0034-ai-employee-charter-cia.md`](docs/_audit/CR-0014-fr-0034-ai-employee-charter-cia.md)。
- **CR-0010 HD-03=a batch 收尾**（CR-0011/0012/0013/0014 共 4 件 CIA 全 opened，2026-06-04 同日）：共 23 HD 待業主裁（CR-0011: 8 / CR-0012: 6 / CR-0013: 5 / CR-0014: 4）；其中 CR-0011 HD-08 ↔ CR-0012 HD-06 為同步裁決對（escrow 模型）；CR-0013 HD-05 為 critical spec/code 衝突解（401 vs 404）；CR-0014 推薦立場為「維持 draft + acknowledged」不強推 active。北極星 (1) 潛在推進空間：4 → 1（CR-0011/0012/0013 全 promote 成功時）或 4 → 0（含 FR-0034 強推 HD-01=(b)/(c)）。
- **Flow 3 範圍變更取證收尾**（branch `docs/wbs-flow-3-取證`，2026-06-04）：取證確認 Flow 3 backend v2 + 前端 admin/consumer + scope_change_service 全綠，原 WBS「80% — 客戶核准流程簡化」vague 描述精化為兩個具體 gap：(1) **LINE Flex 主動通知客戶 gap**（scope_change_service 無 line_push_service 整合，對比 Flow 11 reschedule 已有 LINE Flex RSVP，客戶須主動開連結）；(2) **WS publish gap**（scope_change_service 無 realtime emit，admin 端工單頁無法即時看到客戶回覆狀態）。WBS Flow 3 行 80% → 90%。取證 grep 證實：3 v2 endpoints (`recordScopeChangeV2` / `getScopeChangeProposalV2` / `respondScopeChangeV2`)、2 web pages 使用 v2 path（`my-orders/[id]/scope-change/page.tsx:72 tenantPath` + `scope-change/[token]/page.tsx:90/159/173 ${API_BASE}/consumer/scope-changes`）、scope_change_service 完整 CRUD + audit + customer_decision 同步、`line_push_service.py` 與 `realtime/` grep `scope.change` 全空（兩 gap 真實）。
- **Flow 3 範圍變更 deep 取證校正 — 推翻同日淺取證 90% 過高估值，下修 65%**（branch `docs/flow-3-deep-取證-correction`，2026-06-04）：本 session 稍早淺取證只看 endpoint + UI 表面（commit `f53ffbdc`）即估 90%，現補深度 grep 確認 **`scope_changes` 表完全沒有 INSERT 路徑**（`grep -rn "INSERT INTO scope_changes" api/ agent/` 全空；`work_order_service.record_scope_change` 只寫 work_order_events 加 SCOPE_CHANGE tag，不寫 scope_changes 表；agent 端 0 整合）；`public_token.py` 支援 `purpose=scope_change` mint 但無 caller。結論：**consumer endpoint 雖 ready 但實質無 proposal row 可回應**，Flow 3 主流斷裂。3 個 critical gap：(1) proposal 建立路徑（admin/技師端 0%）、(2) token mint caller（mint infra 0% 用）、(3) LINE Flex + WS publish。**WBS 90% → 65%**。後續 BUILD 屬 CIA gate 範圍（新 contract POST .../scope-changes:propose + LINE Flex template + WS channel），工時估 2~3 day。本次取證為「**取證自我修正案例**」：警示淺取證易誤判，深度 grep INSERT 鏈路才能確認 service 真實鏈接性。
- **Flow 6 退款雙簽 deep audit — 確認 100% 真實 + 2 個 stale doc 修正**（branch `docs/flow-6-deep-audit`，2026-06-04）：複用 Flow 3 deep 取證方法論 (INSERT 鏈路 + state machine + WS publish 全鏈路 grep)，**確認 Flow 6 真實 100%**：refund_service.submit_decision 完整 dual-sign 狀態機 (pending → csm_approved → approved 兩段 + 同 user 不可雙簽 DUAL_SIGN_SAME_USER 409 + approval_chain JSONB audit) + WS publish /realtime/refunds + admin/refunds/page.tsx v2 tenantPath + agent 自動退款 CR-0009 ADR-0106 已遷 refunds:agent-initiate single-actor v2。**2 個 stale doc 修正**：(1) `refund_service.py:25-28` docstring 「本 phase 不實作多步雙簽流程」與實際 line 296+ code 矛盾，更新為「v1.29.0 已實作」對齊；(2) WBS 後端表 row 58 「agent 自動退款流暫續用 v1」stale，已被 CR-0009 ADR-0106 (2026-06-04) 修正，更新為「已於 CR-0009 遷 v2」。**Deep audit 方法論驗證**：本輪確認 Flow 6 與 Flow 3 不同（後者 90% → 65% 下修，前者 100% 確認），方法論可區分真假完成度。
- **Flow 5 延遲通知 deep audit — 確認 100% 真實，無 stale claim**（branch `docs/flow-5-deep-audit`，2026-06-04）：複用 Flow 3/6 deep 取證方法論，audit Flow 5 全鏈路（INSERT 鏈 + WS publish + LINE push + state machine + role guard）。**結果與 Flow 6 同類**（真實 100%，未發現 inflation），但與 Flow 6 不同的是 Flow 5 連 stale doc 都沒有（refund_service docstring stale 已於前一輪修）。`work_order_service.notify_delay:1553` 全 6 點鏈路驗證：(1) INSERT work_order_events delay event 完整；(2) UPDATE work_orders.updated_at；(3) `_audit_action('work_order.delay_notified')`；(4) `line_push_service.push_to_work_order_customer` 真實打 LINE Messaging API（含 retry+backoff+audit）；(5) `_publish_and_return` WS publish；(6) role guard（technician 限自己單）+ state machine guard（_SUBFLOW_FROM）。WBS Flow 5 row 補 6 點 audit evidence，取代原僅 LINE Push API 一點的淺取證註記。**Deep audit 累積進度**：Flow 3 (90% → 65% 下修) / Flow 5 (100% 確認) / Flow 6 (100% 確認 + 2 stale doc 修)；剩 Flow 7/10/11 待 audit。

- **CR-0009 + ADR-0106** ⭐⭐ — Agent caller migration P4-T1 **全鏈路完工**（2026-06-04 一日內）：4 個 agent v1 caller（app.py 2 + admin_api.py 2）全部遷 v2；新增 2 個 admin reschedule v2 endpoints + 1 個 refunds:agent-initiate single-actor endpoint；ADR-0106 記錄 LangGraph 特例不違背全面 SoD 原則。**agent v1 caller = 0**（解開 P4 cutover 唯一硬 gate per CR-0003 §3）。
- **CR-0005 / 0006 / 0009 §8 全裁完** ⭐⭐⭐（2026-06-04 業主三輪 AskUserQuestion 拍完 9 個剩餘 HD）：
  * CR-0005 HD-06 = (a) CSV 為主，JSON 可選（query format 切換）→ 6/6 HD 全裁
  * CR-0006 HD-02=a 軟刪 / HD-03=a 共用 kb_audit_log（doc_type='sop'）/ HD-04=a 廢棄舊 /sops/family-reviews / HD-05=a 即時查 SLA → 5/5 HD 全裁
  * CR-0009 HD-01=a `/consumer/work-orders/{token}/reschedule:{action}` / HD-03=a CR-0006 先拍板再做 / HD-04=a 無 canary / HD-05=a 任何 v1 404 即 PagerDuty → 5/5 HD 全裁
  * 累計 6 CR §8 = 26/26 HD 全裁完，CIA gate 全清；後續純實作 work
- **CR-0005 + ADR-0103** ⭐ — KB v2 expand 設計（2026-06-04 業主裁 §8 6/6 HD 全完）。Migration 015 落地（case_entries.deleted_at + manuals.deleted_at + saas.kb_audit_log + 4 indexes 含 90d hot partial）。Step 2/3：PUT + DELETE + :search endpoints 落地。Step 3/3：2 個 DELETE web caller 遷完；剩 GET/PUT/POST/search UI shape 改造 + :upload (ClamAV) + :export 待後續 commit。詳見 [`docs/architecture/adr/ADR-0103-kb-v2-expand-design.md`](docs/architecture/adr/ADR-0103-kb-v2-expand-design.md)。
- **CR-0007 + ADR-0105** ⭐⭐ — Door-check + Reschedule v2 contract **全鏈路落地**（schema + service + endpoints + web caller，2026-06-04 一日完工）。業主裁 §8 5 HD 全完，三 step：
  * step 1/3 schema：migration 014 `saas.reschedule_proposal` + ADR-0105
  * step 2/3 backend：`work_order_service.submit_door_check_v2`（arrival 前置 409 guard）+ `propose_reschedule_v2`（INSERT 獨立表）；`work_orders_v2:POST .../door-check` + `work_orders_ops_v2:POST .../reschedule:propose`
  * step 3/3 frontend：`my-orders/[id]/door-check/page.tsx` + `work-orders/[id]/page.tsx` 改 v2 tenantPath
  本 branch 真實 v1 caller 43 → 40（door-check + reschedule + settlements 三筆 -3）。詳見 [`docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md`](docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md)。
- **CR-0008** ⭐ — Settlements GET list v2 落地（2026-06-04 業主裁 HD-01=last_3_months / HD-02=period_end_desc）。`settlement_service.list_settlements` 擴 `period_filter` + `sort_by` 參數，v1 預設不變；`settlements_v2.py` 補 `GET /tenants/{tid}/settlements`；`web/accounting/page.tsx` settlement 列表遷 v2。CR-0008 §8 全裁，status: decided-and-implemented。
- **CR-0010** ⭐ — FR-0019 動態 RBAC 角色管理 `status: draft → active`（2026-06-04 業主裁 HD-01=a）。取證 content-complete + ADR-0042 accepted + code 全部實作（role_service publish + rbac_v2 endpoint + RbacChangedBanner mount）。Draft FR 5 → 4，北極星 (1) 真實推進。詳見 [`docs/_audit/CR-0010-fr-0019-promote-to-active.md`](docs/_audit/CR-0010-fr-0019-promote-to-active.md)。
- **跨 CR 部分裁決**（2026-06-04 同 session）：
  * CR-0005 HD-01 = (a) 保留 meta-wrapping（KB v2 響應 shape，連動 CR-0006 HD-01 = a）
  * CR-0007 HD-01 = (a) door-check 強制 arrival 前置（無 arrived_at → 409）
  * CR-0009 HD-02 = (a) 新增 v2 single-actor `refunds:agent-initiate`（保留 agent 自動退款；待 ADR-0106 記 LangGraph 特例）
  * CR-0010 HD-03 = (a) 同步開 CR-0011~0014 審查其他 4 draft FR
  CR-0005/0006/0007/0009 仍有其他 HD 未裁，實作仍卡。
- **ADR-0025** ⭐ — Harness 採 branching pipeline，PIPELINE list 為 introspection-only。Phase 4' hands-on 後從「linear PIPELINE + apply(ctx)」縮減為「結構化 PIPELINE 常數 + 各 layer module PHASE 常數」，零 runtime 變更不需 staging。詳見 [`docs/1-decisions/ADR-0025-harness-branching-pipeline.md`](docs/1-decisions/ADR-0025-harness-branching-pipeline.md)。
- **ADR-0024** — Tier 1 戰術級重構（2026 Q2）**hands-on 修正版**，supersedes ADR-0023。5 訊號處方修正、3 處事實錯誤修正、工期 2-3 週 → 1 週內。詳見 [`docs/1-decisions/ADR-0024-tier1-refactor-revised.md`](docs/1-decisions/ADR-0024-tier1-refactor-revised.md)。Phase 4' 實作見 §9 修正紀錄。
- **ADR-0023** — 已 **superseded by ADR-0024**。原文保留作為決策足跡；merge 後 30 分鐘 hands-on 階段發現 4/5 訊號處方不合理 + 3 處事實錯誤（ADR-0010 懸空、UF 系統未實作、`api/agent/integrations/` 空目錄）。

### Added

- `MISSION.md`（root）— Claude Code 持續迭代任務書（北極星 6 條完工條件 + 階段優先 + per-stage 驗收 + 紅線清單；含 Reality Check 與 session 進度日誌），供 `/goal @MISSION.md` 鎖 session 用
- `docs/architecture/adr/ADR-0106-agent-single-actor-refund-langgraph-exception.md` — agent 自動退款單簽特例正典（CR-0009 HD-02=a）
- `api/routers/work_orders_ops_v2.py` 新增 2 endpoints：customer-confirm + customer-reject（CR-0009 admin path；agent JWT 呼叫）
- `api/routers/refunds_v2.py:130+` 新增 POST `:agent-initiate`（HD-02 single-actor，role enforce agent|system）
- `agent/app.py:387` + `:407` customer-confirm/reject 改 v2 tenant path
- `agent/integrations/admin_api.py:282` refunds 改 `:agent-initiate`
- `agent/integrations/admin_api.py:356` sop-drafts 改 v2 tenant-scoped path
- `SQL/migrations/016-sop-v2-list-expand.sql` — sop_drafts.deleted_at + kb_audit_log doc_type CHECK 擴 'sop'
- `docs/architecture/adr/ADR-0104-sop-v2-list-design.md` — CR-0006 §8 5 HD 決策 ADR
- `api/routers/sops_v2.py` 新增 6 endpoints：GET list / GET single / POST create / DELETE soft / GET family-reviews list / GET family-reviews:pending（CR-0006 step 2/3 落地）
- `api/services/sop_draft_service.py:soft_delete_draft` 新增（HD-02 軟刪）
- `api/services/sop_draft_service.py:list_drafts / get_draft` 加 `deleted_at IS NULL` 過濾
- `web/src/lib/kb-adapter.ts:kbDocumentToSopDraft` 新增（meta-wrap → flat SopDraft）
- `web/src/app/knowledge-base/sop-drafts/[id]/page.tsx` GET + refresh GET 改 v2 + adapter（2 caller 遷完）
- `api/routers/kb_v2.py:660+` POST /kb/documents:export（HD-06=a CSV-first，?format=json 切換；MVP case only；EXPORT_MAX=10000）
- `web/src/app/knowledge-base/cases/page.tsx:161` search caller 從 v1 改打 v2 :search + kbDocumentToCaseEntry adapter
- `web/src/lib/kb-adapter.ts` 新增 — `KBDocument` interface + `kbDocumentToCaseEntry` adapter（CR-0005 step 3/3 解 meta-wrap shape 與 UI flat shape 不一致）
- `web/src/app/knowledge-base/cases/[id]/page.tsx` GET → v2 + adapter
- `web/src/app/knowledge-base/cases/[id]/edit/page.tsx` GET + PUT → v2 + adapter
- `web/src/app/knowledge-base/cases/new/page.tsx` POST → v2 + doc.id 導頁
- `api/routers/kb_v2.py:360+` 新增 CR-0005 step 2/3：
  * `_write_kb_audit_log` helper（best-effort 寫 saas.kb_audit_log，失敗 log warn 不阻擋）
  * `PUT /kb/documents/{docId}`（doc_type 自動 fallback / case 完整支援 / manual 暫 501 待 update_manual impl）
  * `DELETE /kb/documents/{docId}`（軟刪 case_entries SET is_active=FALSE + deleted_at=NOW；manuals SET deleted_at=NOW；before-snapshot 寫 audit；204）
- `api/services/manual_service.py:list_manuals` 加 `deleted_at IS NULL` 過濾（CR-0005 HD-02 軟刪兼容）
- `api/routers/kb_v2.py:get manual` 加 `deleted_at IS NULL` 過濾
- `SQL/migrations/015-kb-v2-expand.sql` — CR-0005 step 1/3：case_entries.deleted_at + manuals.deleted_at + saas.kb_audit_log（pending psql apply）
- `docs/architecture/adr/ADR-0103-kb-v2-expand-design.md` — CR-0005 §8 4/6 HD 決策 ADR
- `api/services/work_order_service.py` 新增：
  * `submit_door_check_v2`（HD-01 強制 arrival 前置：查 work_order_events arrival → 409）
  * `propose_reschedule_v2`（INSERT saas.reschedule_proposal；HD-02 slots 1-3 驗證 + send_via line/sms/email）
- `api/routers/work_orders_v2.py:560+` 新增 `POST /tenants/{tid}/work-orders/{id}/door-check`（CR-0007 / `_DoorCheckSubmitRequest`）
- `api/routers/work_orders_ops_v2.py:330+` 新增 `POST /tenants/{tid}/work-orders/{id}/reschedule:propose`（CR-0007 / `_ProposeRescheduleV2Body` + `_ProposedSlot`）
- `web/src/app/my-orders/[id]/door-check/page.tsx:161` v1 → v2 `tenantPath(/work-orders/{id}/door-check)`
- `web/src/app/work-orders/[id]/page.tsx:1076` v1 → v2 `tenantPath(/work-orders/{id}/reschedule:propose)`；移除 setOrder（v2 propose 不變更 scheduled_at，待 RSVP 後 confirm）
- `SQL/migrations/014-reschedule-proposals.sql` — saas.reschedule_proposal 表（CR-0007 落地步驟 1/3；pending psql apply）
- `docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md` — CR-0007 §8 5 HD 決策正式落地 ADR
- `SQL/migrations/MIGRATION_REGISTRY.md`：014 row 加入（pending-apply 狀態標記）
- `api/routers/settlements_v2.py:75-130` 新增 `GET /tenants/{tid}/settlements` v2 endpoint（CR-0008 落地；預設 last_3_months + period_end desc）
- `api/services/settlement_service.py` `list_settlements` 擴 `period_filter` / `sort_by` 參數（v1 預設不變，向後相容）
- `docs/_audit/CR-0007-door-check-reschedule-contract.md` — door-check + reschedule contract 重設計 CIA（5 HD，HD-01 已裁）
- `docs/_audit/CR-0008-settlements-get-list-v2.md` — 最小 CIA（2 HD，本 session 全裁完並實作）
- `docs/_audit/CR-0009-agent-caller-migration-p4-t1.md` — agent caller P4-T1 CIA（5 HD，HD-02 已裁）
- `docs/_audit/CR-0010-fr-0019-promote-to-active.md` — FR-0019 promotion CIA（3 HD，HD-01/02/03 已裁並實作）
- `docs/_audit/CR-0005-kb-v2-expand-and-shape.md` — KB v2 expand CIA（PUT/DELETE/search/export/upload + 響應 shape 6 HD），解 9 個 v1 caller 遷移路徑
- `docs/_audit/CR-0006-sop-v2-list-expand.md` — SOP v2 list expand CIA（sop-drafts + family-reviews list/CRUD 5 HD），解 5 個 v1 caller
- `web/src/components/layout/AuthGuard.tsx`：mount RbacChangedBanner（之前定義未掛載），補齊 RBAC realtime 全鏈路
- `web/src/app/accounting/page.tsx:124` settlement list 從 `/api/v1/accounting/settlements?limit=50` 遷至 v2 `tenantPath("/settlements?limit=50")`（CR-0008 落地）
- `docs/4-exploration/WBS-0004-phase-5-flow-index-backlog-2026-q2.md` — Phase 5' Flow INDEX defer 紀錄 + T1-T4 啟動條件 / R1-R2 移除條件
- `docs/4-exploration/WBS-0003-phase-3.3-backlog-2026-q2.md` — Phase 3.3 backlog 推進紀錄（最終 16/18 page + hook 演化 5→8 features）
- `docs/1-decisions/ADR-0025-harness-branching-pipeline.md` — Phase 4' 修正版 ADR
- `docs/1-decisions/ADR-0024-tier1-refactor-revised.md` — 修正版 ADR（含 Phase 4' §9 修正紀錄）
- `docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md` — 初版 ADR（已 superseded）
- `docs/4-exploration/WBS-0002-2026-q2-tactical-refactor.md` — 對應 WBS v2.0（覆寫 v1.0）
- `CHANGELOG.md`（本檔）
- `agent/harness/__init__.py`：由空檔變為 PIPELINE 結構化常數 + PipelineEntry NamedTuple + module docstring（per ADR-0025）
- `agent/harness/{safety_gate,data_correction,quick_reply,intent_handler,pc_creator,profile_updater,validator_pipeline,memory_manager,agent_audit}.py`：各加 `PHASE: str` 模組層級常數（per ADR-0025）
- `web/src/hooks/`：新增目錄，含 5 個 hook（useRealtimeChannel, useSSEChannel, useBroadcast 自 lib/ 遷移；usePaginatedFetch 新增）+ README
- `docs/1-decisions/releases/`：83 個 v1.x.x.md release notes（自 root `report/` 遷移）
- `docs/_archive/legacy/web_design_spec_prompt_pipeline/`：legacy 設計系統 pipeline（自 root 遷移）

### Changed

- `web/src/app/admin/schedule-requests/page.tsx`：reject 從 `POST /api/v1/admin/schedule-requests/{id}/reject` 遷至 v2 `POST /tenants/{tid}/exceptions/{id}:approve`（body.decision="reject" 區分）；移除 P3-KEEP flat 註解（原註解「reject 無對應 v2 端點」與 exceptions_v2.py:33 不符，實為文件 stale）
- `web/src/components/admin/CustomerForm.tsx`、`web/src/app/admin/customers/[id]/edit/page.tsx`：docstring 同步至 v2 路徑（實際 caller 早已 v2，註解 stale）
- `web/docs/system-completion-status.md`：P3.5 Track-B caller 補遺改標 ✅ 100%（2026-06-04 取證收尾，原表述 stale）；總體 88% → 89%；架構遷移 85% → 88%；Caller 遷移 v1→v2 80% → 92%；§8 P0 移除已完成的 P3.5 條目、新增 P1「Reconciliation dual-sign UX rework」backlog
- `docs/_audit/CR-0003-full-cutover-wbs.md`：新增 §5 進度區（append-only），標記 P0/P1/P2/P3/P3.5 ✅、P4 ⏳
- `MISSION.md`：P3.5 驗收條件改標 ✅ 已收尾；迭代優先順序更新為「P4 Cutover 目前在這」+ 並行 backlog 區段
- `docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md`：frontmatter `status: superseded`、`superseded_by: [ADR-0024]`；補 §8 變更紀錄
- `docs/4-exploration/WBS-0002-2026-q2-tactical-refactor.md`：v1 → v2（5 Phase 範圍縮減 50%+；S5 改為 BACKLOG）
- `.gitignore`：新增 `api/data/`、`web/test-results/` 兩條（runtime 產物，含個資不入版控）
- `web/src/lib/api.ts`：檔頭註解路徑指向新位置 `web/types/api.generated.ts`（取代舊路徑 `docs/02-design/specs/generated/...`）

### Notes

本章節為 Q2 戰術級重構期間累積，待全部 Phase 1'-4' 完成後另開 release tag。

**Hands-on 修正歷程**：ADR-0023 於 2026-05-11 PR #62 merge 後 30 分鐘，進入 Phase 1.1 hands-on 階段。先發現 `report/` 是 95 個 v1.x.x release notes（非垃圾）、`api/data/` 命名類比錯誤，繼派 3 個 Explore agent 對全 5 訊號做深度驗證，揭露 4/5 處方不合理 + 3 處事實錯誤。Supersede 為 ADR-0024（hands-on 修正版），整體工期估計從 2-3 週縮減為 1 週內。決策軌跡保留作為「假設驅動 → hands-on 驗證」學習案例。

---

## [Historical] — Pre-2026-Q2

> 2026-Q2 之前的變更未維護於本檔。歷史紀錄請參考：
>
> - Git commit history（`git log --oneline`）
> - 各模組 module-boundary 文件（`docs/1-decisions/module-boundary/*.md`）
> - WBS Q1 進度（`docs/4-exploration/WBS-0001-2026-q1.md`）
