---
id: CR-0004
title: Track B — 8 個 BUILD_WITH_CIA 模組 grounded CIA + 跨模組裁決
status: decisions-recorded-owner-delegated
created: 2026-06-02
decided: 2026-06-02
author: Opus 4.8 (adjudication) + Sonnet (per-module grounded CIA)
supersedes: null
related:
  - docs/_audit/CR-0003-full-cutover-wbs.md
  - docs/_audit/CR-0002-p2-tenant-scoped-rfc7807-rls.md
  - docs/_audit/p2-docs-grounded-decision-matrix-2026-06-02.md
  - docs/_audit/spec-code-gap-audit-2026-06-01.md
tier: 4-exploration
---

# CR-0004 — Track B（BUILD_WITH_CIA）grounded CIA + 跨模組裁決

> **本文是動 code 前的硬 gate（rules/change-governance.md）。** Track A（BUILD_TENANT_SCOPED，~35 模組含 P2-W6 media/dispatch-logs）已完成並全綠。Track B = 8 個需「真設計」（多表 / 狀態機 / SoD / governance / 不可逆 schema 遷移）的模組，依治理規則各需 CIA + 業主裁 §8 後才可實作。本文彙整 8 份 grounded CIA（以 `docs/` 為事實來源）+ Opus 對 5 個 docs 衝突的裁決 + 跨模組實作順序。
>
> 🛑 **§8 未獲業主裁決前，Track B 不動任何 code / DB schema。**

---

## 0. 一句話現況

8 個模組全部 `risk=HIGH`。**只有 `config-m18-governance` 是 `READY_AFTER_OWNER`**（spec 6 條 path 已在 merged openapi.yaml、canonical DDL §9 四表已定義、無 C-10 schema 衝突 → 只待業主形式拍板 HD-01~06）。**其餘 7 個全部 `BLOCKED_ON_CONFLICT`**，幾乎都卡在同一個跨模組 DESTRUCTIVE 決定：**C5 — DB schema 命名遷移（`saas.*` canonical vs 現行 `public.*` legacy）**。

---

## 1. C5 是「主決定」（master gate）— 一次裁、全模組共用

gap-audit C-10/C-11 明標多張 legacy 表（`public.disputes` / `public.reconciliations` / `public.inventory_items` / `public.data_corrections` / `public.price_rules` / `public.vouchers` / `public.problem_cards.resolution_layer`…）**不在 canonical 53 表 DDL**，「會打爆現有資料」「破壞性決定」「動手前各自跑 CIA」。

**裁決官建議（仍須業主最終拍板，AI 無權代決不可逆資料遷移）：統一一套遷移範式，避免每模組各裁產生不一致：**

> 新建 `saas.<canonical表名>`（含 `tenant_id`）→ **dual-write 過渡**（同時寫 `public.*` + `saas.*`）+ **backfill**（反推 tenant_id）→ 前端/agent caller 歸零且 v2 E2E 綠後（CR-0003 P4 gate）才 **DROP legacy `public.*` 表**。

例外個案：
- **inventory**：`public.inventory_items` 無 tenant_id 且涉 owner 三分流帳務（ADR-0052），風險最高 → 須**先決 tenant scope**（HD-INV-01）才能定 schema。
- **data-corrections**：可選方案 B（`public` 就地 `ADD COLUMN IF NOT EXISTS tenant_id`，最小破壞）作過渡，端態仍建議遷 `saas`。
- **vouchers**：在 `public` schema，void 的 `ALTER TABLE` 目標 schema 須先裁（HD-VCH-004）；hash chain backfill **不可分批**，須在 maintenance window 一次完成。
- **problem_card.resolution**：`saas.problem_card` 須 `ALTER TABLE ADD COLUMN resolution_layer text CHECK(L1/L2/L3) NULLABLE`（resolution HD-2）。

**➡️ OWNER DECISION D-C5（最高優先）**：是否採用上述「dual-write + backfill → P4 DROP」統一範式？inventory/data-corrections/vouchers 的例外是否照建議處理？

---

## 2. 五個 docs 衝突的裁決（Opus）

| # | 衝突 | 裁決官 ruling | 仍需業主最終拍板？ |
|---|---|---|---|
| **C1** | invoices：FR-0011 `status=draft`（卡 Q7 金流 provider 未選）vs CR-0003 排 BUILD_V2 vs SOW-0001(Approved) 列 /accounting/invoices | **分兩段**：(a) 現在可建 **read-only** list+get tenant-scoped（擴 spec `/tenants/{tid}/accounting/invoices`）；(b) **付款生成/寫入凍結**至 FR-0011 轉 active。tier-4 draft「可參考不視為硬授權」，read-only 無金流副作用、不違反 Never-break。 | ✅ 是 |
| **C2** | reconciliations/disputes：spec **無** path vs FR-0013(active P0) 要 dual-sign 三維 SoD | **以 FR-0013 為準擴 spec**（補 SoD header X-Initiator/X-Approver/X-Executor + ReconciliationV2/DisputeV2 schema） | ✅ 是（確認擴 spec 方向） |
| **C3** | pricing-rules：spec 只有 `/pricing/calculate` vs ADR-0067/BR-M18 要走 M18 staged rollout vs code 有 `/pricing/rules` CRUD | **路徑 C 混合過渡**：短期保留 tenant-scoped `/pricing/rules` CRUD（遷 `saas.price_rule`）+ 寫入並行寫 `saas.change_request` 走 ADR-0046/0064；Phase II 待 config-m18 就位後將 pricing namespace 漸進納入 M18。（DDL config_namespace seed **無** pricing namespace、BR-M18 基礎設施未實作 → 純 M18 立刻做會把 pricing 釘死） | ✅ 是（且 calculate 入參格式 HD-4 須另裁） |
| **C4** | resolution：standalone `/resolve` vs sub-resource `/problem-cards/{id}/resolve`（_source/02）vs chatbot 命名空間 | **統一進 `/tenants/{tid}/problem-cards/{id}/resolve` sub-resource**；FAQ/RAG 引擎封裝為 chatbot-internal | ✅ 是（路由形狀 HD-1 形式拍板） |
| **C5** | DB schema 命名（見 §1） | **跨 8 模組 DESTRUCTIVE，裁決官拒絕代決** → 見 §1 D-C5 | ✅ **是（最高優先）** |

---

## 3. 跨模組實作順序（依賴拓樸）

```
S0 [前置 gate，全部共同阻塞]
   業主簽核 (a) CR-0003 P0 Q1-Q6 + (b) P1-T1 spec 合併(已完成 commit 0af385ea) + (c) C5 schema 命名範式統一裁決
        │
        ▼
S1 [Phase 0 critical path，最先，阻塞 pricing] ── config-m18-governance
        │   ADR-0067「Phase I MVP 不能在缺這套治理的地基上跑」。先決 HD-01~06、跑 migration 002 GRANT、
        │   建 router+service+staged rollout state machine+ACL read+cache。就位才解鎖 pricing 走 M18。
        ▼
S2 [共用 dual-sign] ── reconciliations → disputes
        │   同源 FR-0013 三維 SoD，共用 core/deps.py require_sod_actors。先收斂 reconciliations 設計，disputes 對齊重用。
        ▼
S3 [schema 根基最重，阻塞 work-orders/material-request] ── inventory
        │   FR-0007 row-lock 扣庫存；canonical 53 表完全無 inventory 表。先決 HD-INV-01(tenant scope) + 簽 ADR-0052/0053(現為 Draft)。
        ▼
S4 [依賴 config-m18 就位] ── pricing-rules（路徑 C）
S5 [tenant scope 直遷，依賴 C5+RBAC] ── data-corrections（可與 S2/S4 平行）
S6 [依賴 saas.problem_card migration + S0] ── resolution
S7 [平台級 flat，獨立性最高，但 hash chain+schema 須先裁] ── vouchers-void
```

**並行性**：S1(config-m18) 與 S3(inventory) 的 CIA/決策階段可平行（不同 HD），但 S1 **code 須最先完成**（Phase 0）。S2 / S5 / S7 領域不同無共用表，CIA 與實作可開獨立 worktree 平行。S4 code block 於 S1；S6 block 於 `saas.problem_card` migration。

---

## 4. Ready vs Blocked

| 模組 | 狀態 | gate |
|---|---|---|
| **config-m18-governance** | 🟢 `READY_AFTER_OWNER` | 只待業主裁 HD-01~06（spec/DDL 都備齊、無 C-10 衝突） |
| pricing-rules | 🔴 `BLOCKED_ON_CONFLICT` | C3 + C5；治理層 block 於 config-m18 就位 |
| reconciliations | 🔴 `BLOCKED_ON_CONFLICT` | C2 + C5 |
| disputes | 🔴 `BLOCKED_ON_CONFLICT` | C2 + C5 + status enum 三方不一致 |
| inventory | 🔴 `BLOCKED_ON_CONFLICT` | C5 + tenant scope（HD-INV-01）+ ADR-0052/0053 簽核 |
| data-corrections | 🔴 `BLOCKED_ON_CONFLICT` | C5 + agent harness init_db tenant_id 對稱（ADR-0030） |
| resolution | 🔴 `BLOCKED_ON_CONFLICT` | C4 + C5（saas.problem_card resolution_layer 欄） |
| vouchers-void | 🔴 `BLOCKED_ON_CONFLICT` | C5 + append-only 衝突（HD-VCH-002）+ keeperRole 未定義 |

---

## 5. §8 — Human Decisions Required（彙整，業主逐項裁）

> 動 code 前須全部有答案。每項標出引用 ID。建議先處理 **D-C5（§1）** + **S0**，再依模組展開。

### config-m18-governance（S1，唯一可立即啟動者）
- **HD-01**【觀察視窗】ADR-0067 §3(≥10min) vs BR-M18-04(active, standard 30/fast 15) vs spec(min:10/default:15) 三方不一致。建議：BR-M18-04 active 為實作預設、spec min:10 為 API 下限、ADR §3 為過時草案值。**須形式確認。**
- **HD-02**【config_version_used 格式】cancellation/refund 現為 text（整列 version）。是否升 `namespace:version_id` 複合格式？影響是否 backfill（DESTRUCTIVE）。
- **HD-03**【public.system_config 棄用時序】DROP 時間點（P4 cutover vs 提前獨立 migration）。
- **HD-04**【pricing 是否納 M18】= C3，與 pricing-rules HD-1 同題。
- **HD-05**【pub/sub 選型】Redis Pub/Sub / NATS / DB LISTEN-NOTIFY / 純 TTL 30s 兜底？影響 infra 引入時序。
- **HD-06**【高風險雙簽角色 + 時段限制】FR-0043 §1.2 A4 要 IT Admin + 主管雙簽且禁半夜；spec 只有二元 X-Initiator/X-Approver。時段限制進 API 層 enforce 或只進 UI？

### inventory（S3，schema 根基）
- **HD-INV-01**【BLOCKING】tenant scope：per-tenant 獨立倉 vs platform-shared 共享倉？（schema 根本方向）
- **HD-INV-02**【BLOCKING】C-10 命名（= C5）。
- **HD-INV-03**【BLOCKING】material consume vs request 路徑合併或分離？
- **HD-INV-04**【BLOCKING，影響月結】ADR-0052 owner enum 最終值（platform/brand/locksmith vs +customer）。**ADR-0052/0053 現為 Draft，AC 未簽 → 須業主圈選 ✅。**
- **HD-INV-05**【BLOCKING，影響 WO complete gate】ADR-0053 高價件 serial 門檻（NTD 1,000?）+ 缺 serial 是否阻擋 WO complete？
- **HD-INV-06**【影響 canonical DDL】`saas.work_order` 加 `material_consumption JSONB`（分區表，須評估）。

### reconciliations（S2）
- **HD-1** C-10 schema 命名（= C5）。
- **HD-2** dual-sign 角色對應（CSM vs ops_manager；ADR-0042 4 層映射）。
- **HD-3** settlement INSERT 時機：single-approve→dual-sign 為 breaking，舊 pending settlement rows 補救策略。
- **HD-4** 60 天 cron escalation infra（Cloud Scheduler+Job vs APScheduler vs 外部腳本；與 FR-0012 月結 cron 共用？）。
- **HD-5** 確認以 FR-0013 為準擴 spec（= C2）。

### disputes（S2）
- **HD-1** C-10 schema 命名（= C5）。
- **HD-2** status enum 三方不一致 → canonical 化（建議 filed/in_review/mediation/resolved/escalated/closed_withdrawn）。
- **HD-3** dual-sign actor 順序（ADR-0014 已 HISTORICAL；ops_manager vs ops_director first/final-sign）。
- **HD-4** resolution_amount 負值是否走 DGS mutation path（ADR-0061）vs 直接寫 journal_entry。
- **HD-5** 60d SLA cron 規格（BR-M15-NN 仍是 placeholder：頻率/起算點/通知方式）。

### resolution（S6）
- **HD-1** 路由形狀最終裁定（= C4，建議 sub-resource）。
- **HD-2** `saas.problem_card` 加 `resolution_layer` 的 migration timing（不可逆）。
- **HD-3** FAQ/RAG/Escalation 邏輯去向（chatbot-internal 函式 / internal REST / 刪除）。
- **HD-4** Layer enum 統一（L1/L2/L3 vs faq_match/rag/escalation，哪套進 spec）。
- **HD-5** legacy `public.problem_cards.resolution_layer` 是否 backfill。

### pricing-rules（S4）
- **HD-1**【CRITICAL】機制路徑 A/B/C 擇一（= C3，建議 C）。
- **HD-2** C-10 schema 命名（= C5；`saas.price_rule` vs `saas.config_version`）。
- **HD-3** `config_namespace` pricing seed 的 JSON schema 規格 + key 命名慣例（若走 B/C）。
- **HD-4** calculate 入參格式對齊（spec pc_id/contract vs code brand/lock_type — domain model 不一致）。
- **HD-5** legacy flat CRUD 退出時序（前端是否依賴 `/admin/pricing`）。

### data-corrections（S5）
- **HD-1** C-10：就地補 tenant_id（方案 B 最小破壞）vs 遷 `saas.data_correction`（方案 A DESTRUCTIVE）。
- **HD-2** status machine：補 `resolved` 第四態 vs 維持三態。
- **HD-3** approve 後 SOP draft 自動建立時間點（本 CIA 觸發 vs phase 2 defer）。
- **HD-4** approve/reject 最低角色（require_admin / require_knowledge_owner / require_tenant）。
- **HD-5** PII/GDPR：conversation_context + user_facts 是否納 FR-0053 two-phase delete（legal_hold 欄 + soft/hard delete job）。
- **附加依賴**：agent harness `init_db` 須同步補 tenant_id（ADR-0030 對稱），否則 v2 `WHERE tenant_id` 過濾但 agent 寫入全 NULL。

### vouchers-void（S7）
- **HD-VCH-001** hash chain 五欄（issuer_party/tax_doc_ref/legal_basis/hash_prev/hash_self）V1 即補 vs V2 再補（backfill 不可逆）。
- **HD-VCH-002**【blocking】原傳票 voided_at：`UPDATE`（與 append-only/BR-AUDIT-007 衝突）vs 新建 `voucher_void_event` 事件表。
- **HD-VCH-003** keeperRole（X-Keeper-Role）value 格式：platform admin JWT role vs Service Account secret。`core/deps.py` 須新增 `require_keeper_role`（目前不存在）。
- **HD-VCH-004**【blocking】schema 命名（= C5；`public.vouchers` vs `saas.vouchers` 的 ALTER TABLE 目標）。
- **HD-VCH-005** 測資依賴 FR-0011(draft) VoucherIssued（= C1 連動）：等 provider 選型 vs 獨立先行（手動 seed）。

---

## 6. 完整 grounded CIA 原始資料

8 份逐模組 grounded CIA（as-is / to-be / affected FR/BR/ADR/DDL/API/data/test 全文）儲存於 workflow 輸出：
`.../tasks/wz3k9dl36.output`（result.cias）。本文已萃取每模組的 §8 Human Decisions + 依賴 + 順序；如需逐欄全文（含 DDL 行號引用），見該輸出檔。

---

## 7. 建議下一步（待業主）

1. **先裁 D-C5（§1 統一 schema 遷移範式）+ S0 前置** — 解鎖 7 個 BLOCKED 模組的共同 gate。
2. **同步裁 config-m18 HD-01~06** — 解鎖唯一 `READY_AFTER_OWNER` 模組，可立即開 S1 worktree。
3. 其餘模組依 §3 順序，業主裁完該模組 §8 後逐一開 CIA-approved 實作 worktree（Sonnet 開發 / Opus gate+合併）。

---

## 8. ✅ Decisions Recorded（2026-06-02，業主授權「按建議開發」）

業主於 2026-06-02 裁示「按你建議開發」，授權採用本文裁決官的推薦處置作為正式決策。記錄如下（維持 change-governance 稽核軌跡）：

### Master / 跨模組
- **D-C5（schema 命名遷移）= 採統一範式**：新建 `saas.<canonical表>`（含 `tenant_id`）→ **dual-write 過渡 + backfill** → caller 歸零 + v2 E2E 綠後（**P4 gate**）才 DROP legacy `public.*`。例外照 §1（inventory 先決 tenant scope、data-corrections 可方案 B 就地、vouchers maintenance window、problem_card ADD COLUMN）。**DROP 一律延至 P4**（本波次不做不可逆刪除）。
- **C1 invoices = 分兩段**：read-only list+get 可建；付款寫入凍結至 FR-0011 active。
- **C2 reconciliations/disputes = 以 FR-0013 擴 spec**（補三維 SoD header）。
- **C3 pricing-rules = 路徑 C 混合**：短期 tenant-scoped CRUD + 並寫 `saas.change_request`；Phase II 待 config-m18 就位納入 M18 namespace。
- **C4 resolution = 統一 sub-resource** `/tenants/{tid}/problem-cards/{id}/resolve` + 引擎 chatbot-internal。

### config-m18-governance（S1，本波次先做）
- **HD-01 觀察視窗 = BR-M18-04(active)**：standard 30min / fast-track 15min / 硬下限 10min（API min:10）。
- **HD-02 config_version_used = 暫不改格式**：保留現行 text（整列 version），**新增 namespace 粒度由新 saas.config_version 提供**；既有欄位不 backfill（避免不可逆），P4 再評估統一格式。
- **HD-03 public.system_config DROP = 延至 P4**：dual-write 過渡（舊 config_service 續用、新 saas.config_version 並行）。
- **HD-04 pricing 納 M18 = Phase II**（同 C3 路徑 C；本波次 config-m18 不含 pricing namespace）。
- **HD-05 pub/sub = 短期純 TTL 30s 兜底**（不引入 Redis/NATS infra；invalidation 走 in-process TTL + 重讀，pub/sub 留 Phase II）。
- **HD-06 高風險雙簽 = API 層 enforce X-Initiator/X-Approver SoD；時段限制（禁半夜）暫只進 admin UI**（API 層 Phase II 補）。

### 其餘模組（S2-S7，依序待各自開工前確認）
- inventory：**HD-INV-01 tenant scope = per-tenant 獨立倉**（最貼近現行多租戶模型）；ADR-0052 owner enum = platform/brand/locksmith（不含 customer，對齊 ADR-0052 推薦）；ADR-0053 serial 門檻 = NTD 1,000 且缺 serial **阻擋 WO complete**。（開工前 inventory CIA 再確認）
- reconciliations/disputes：dual-sign 重用 `core/deps.py require_sod_actors`；status enum 對齊 FR-0013；60d cron 用 Cloud Scheduler + Cloud Run Job（與月結共框架）。
- data-corrections：C-10 採方案 B 就地補 tenant_id 過渡（端態遷 saas）；補 `resolved` 第四態；approve 觸發 SOP draft 延 phase 2；RBAC require_admin；GDPR 納 FR-0053。
- vouchers-void：hash chain V1 即補；voided 用**新建反向分錄 + voucher_void_event 事件表**（不 UPDATE 原 row，守 append-only）；keeperRole = platform admin JWT role；schema 遷 saas（dual-write）。
- **agent refunds SoD gap（P3 發現）**：agent 自動退款流暫續用 legacy /api/v1/refunds；v2 system-actor 退款路徑列入 refunds 後續 CR（與 vouchers 同波評估）。

> **實作順序仍嚴守 §3 S0→S7**；每模組開工前以本決策為基線，遇 grounded CIA 細節衝突再回報。

### 進度
- ✅ **S1 config-m18 done**（merge `2c4dbf1e`，2026-06-02）：saas.config_* 4 表 + 7 endpoint + SoD/audit/ACL/rollback，25 測試綠、回歸 524+1skip。Opus gate 修 parent-restore + 繁中。Phase II：canary auto-advance/SLO halt（需 scheduler）。
- ✅ **S2 done**（reconciliations `4c265155` + disputes `b23edabf`）：
  - reconciliations：saas.reconciliation + saas.settlement dual-write；CSM review → ops_manager co-sign（跨兩 call SoD）→ settlement INSERT。19 測試、spec +4 path。
  - disputes：saas.dispute；FR-0013 狀態機 filed→in_review→(mediation)→resolved|escalated|closed_withdrawn；dual-sign close（重用跨兩 call 範式）；reopen→新 dispute parent lineage（AC-05）。33 測試、spec +8 path。回歸 576+1skip。60d cron + 負值 DGS = Phase II。
- ✅ **S3 inventory done**（merge `ba42c2ab`）：saas.inventory_item（per-tenant + owner ADR-0052 + serial_required ADR-0053）+ saas.inventory_transaction；6 endpoint；:consume/:return/:restock 用 transaction + FOR UPDATE（FR-0007 AC-05；insufficient→409、serial→422）。29 測試、回歸 605+1skip、spec +6 path。ADR-0052/0053 採推薦值（status frontmatter↔body 不一致已記錄）。follow-up：serial 擋 WO complete / material-request 語意整合（HD-INV-03）/ reorder 通知。
- ⏳ S4 pricing-rules（路徑C 依賴 config-m18）/ S5 data-corrections / S6 resolution / S7 vouchers-void — 待續，同範式。
