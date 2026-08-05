---
id: CR-0210
title: 平台營運與知識庫功能的規格落地缺口（含尚未開發的工單積木引擎）
status: draft
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, API contract, Domain model, DB schema, External integration, Architecture boundary, Test plan]
related: [TC-PLT-CFG-01, TC-PLT-PROV-01, TC-PLT-FLOW-01, TC-TEC-LIFE-01, TC-TEC-REVOKE-01, TC-REF-INTAKE-01, TC-REF-PUBLISH-01, FR-PLT-03, FR-PLT-07, FR-PLT-08, FR-TEC-01, FR-TEC-02, FR-TEC-08, FR-REF-01, FR-REF-03, FR-REF-04, FR-REF-05, FR-DAT-01, BR-KN-001, BR-KN-002, BR-SOP-002, CR-0114, CR-0166, CR-0167, CR-0195, CR-0197, ADR-012, ADR-P010, ADR-P011, ADR-P012, ADR-P013]
---

# CR-0210 — 平台營運與知識庫功能的規格落地缺口

> **走查基準**：Luca 2026-08-03 靜態走查（commit `2cfeca92`）→ 2026-08-04/05 回程式碼查證。
> **本文件證據基準**：commit `01114100`（本文所有 `檔案:行號` 皆於此 commit 重新開檔覆核；
> 與走查文件行號不同者已逐處標明偏移原因）。

---

## 1. 一句話

這 7 支 TC **不是同一種東西**——其中 1 支（TC-PLT-FLOW-01 工單積木引擎）是**規格寫了但從未排進開發**，
程式碼樹零命中，要裁決的是「要不要做／何時做」而不是「什麼時候修」；另 1 支（TC-PLT-PROV-01）
是**正典自己標了「階段二」、業主自己裁決了「純手動」，但測試計畫把它列成 P0 並要求自動化狀態機**，
要裁決的是哪份文件為準；剩下 5 支才是真的有程式碼、但**閘門只做了一半**（保護層保護不到該保護的東西、
SLO 破線不會停止推廣、撤證不影響派工、bronze 紅線腳本沒接 CI、汲取失敗只印 stderr）。

---

## 2. 需求追溯

### 2.1 逐支 TC 的正典出處

| TC | 追溯需求 | 正典條文出處 | 正典本身的狀態 |
|---|---|---|---|
| TC-PLT-CFG-01 | FR-PLT-08 | `smartlock-docs/enterprise/04_SRS.md:388`；`14_ADR/ADR-012_Agent_Configuration_Studio.md:44`（受保護層／客製層兩層表） | 前置條件欄自標「Config Registry 就緒（🔜 規劃中）」 |
| TC-PLT-PROV-01 | FR-PLT-03 | `04_SRS.md:383` | 主流程欄自標「🔜 規劃中自動化 + CD，ADR-P012」；`:577` 明列為**階段二** |
| TC-PLT-FLOW-01 | FR-PLT-07 | `04_SRS.md:387` | 主流程欄自標「🔜 規劃中 AI Onboarding Compiler」；**前置條件欄＝「DSL schema 凍結」，未達成** |
| TC-TEC-LIFE-01 | FR-TEC-01 | `04_SRS.md:351`（＋驗收面實際落在 `:352` FR-TEC-02） | active；`:362` 有 CR-0195 標注 |
| TC-TEC-REVOKE-01 | FR-TEC-08 | `04_SRS.md:358` | active，但其「各品牌訂閱後更新派工可用性」依賴 FR-PLT-04（`04_SRS.md:384` 自標「🔜 規劃中，Phase 1 Redis / Phase 2-3 Kafka」）|
| TC-REF-INTAKE-01 | FR-DAT-01、FR-REF-01 | `04_SRS.md:330`、`:341` | FR-REF-01 的「汲取機制」欄自標 **`[待確認]`**，並列在 `:555` ChangeRequest 清單第 2 項 |
| TC-REF-PUBLISH-01 | FR-REF-03、FR-REF-04、FR-REF-05 | `04_SRS.md:343`、`:344`、`:345`；`:518` BR-KN-001、`:519` BR-KN-002、`:516` BR-SOP-002 | FR-REF-04 的「references ↔ pgvector CI 同源檢查」自標「🔜 規劃中」 |

### 2.2 🛑 正典之間的矛盾（這本身就是要裁決的事）

**① FR-PLT-03 三方矛盾（最嚴重）**

- `04_SRS.md:383` — provisioning 自動化欄自標「🔜 規劃中」；`04_SRS.md:577` 標注再確認一次「FR-PLT-03 License provisioning 自動化（階段二）」。
- `20_Test_Cases.md:418` — TC-PLT-PROV-01 判定基準「未完成任一步不得啟用 License；重跑冪等且有 provisioning audit」，**優先級 P0**。
- 程式碼／業主裁決 — `api/services/brand_application_service.py:3`「業主裁決 2：核准後開站**純手動**」，同一裁決寫進 DB 註解 `SQL/platform/Schema_platform.sql:101`（CR-0114 裁決 2）。

一個**被業主明文決議不自動化**的流程，在測試計畫裡是 P0 且要求自動化狀態機。依 `.claude/rules/change-governance.md`「Source of Truth Conflict」，不得腦補實作。

**② 20_Test_Cases.md 自己前後矛盾**

`20_Test_Cases.md:120`（FR-PLT-03）、`:124`（FR-PLT-07）、`:125`（FR-PLT-08）三列的追溯狀態欄都寫「⚠ 完全沒有案例」，
但同一份文件 `:418`／`:419`／`:420` 就有 TC-PLT-PROV-01／TC-PLT-FLOW-01／TC-PLT-CFG-01 三支對應案例。
追溯矩陣段落與 §13 案例主表未同步。

**③ FR-TEC-02 驗收 vs CR-0114 R4 裁決 3**

- `04_SRS.md:352` FR-TEC-02 驗收欄：「未過准入閘門不得進入派工候選集」；`:362` CR-0195 標注再強調「**不變且未被放寬**」。
- `api/services/dispatch_service.py:555-557` 註解：「CR-0114 R4（裁決 3）：鎖品牌授權由『過濾』改『標示』——全部啟用中師傅皆可見」。

人工派工路徑（`list_dispatch_candidates`）與 SRS 驗收條文直接衝突，且衝突已被程式碼註解記錄下來，屬**已知的、有意的**背離，但正典側從未加標注。

**④ FR-REF-04 / BR-KN-001 的「bronze 白名單」對 refinery 事實軌不成立**

- `04_SRS.md:344` FR-REF-04 後置條件：「Publisher 灌注前校驗 source 屬 bronze 白名單」；`:518` BR-KN-001 同語。
- 但 refinery 事實軌（`case_entry`）的來源是**問題卡＋對話逐字稿**，不是 bronze 檔（`knowledge-pipeline/refinery/refinery/publisher.py:20-53` 的 `source_problem_card_id`；`refine.py` 的 provenance 錨點同為問題卡）。
- `grep -rni bronze knowledge-pipeline/refinery/` **零命中**（獨立複驗）。

FR-REF-04 把兩條血緣完全不同的軌（外部素材 raw→bronze→silver→corpus / 診斷對話→draft→case_entries）寫成同一個 Publisher 的責任。這是規格層的模型錯配，不是實作漏做。

---

## 3. 歷史成因

| 現象 | 成因（有據） |
|---|---|
| flow/DSL/block 全零命中 | FR-PLT-07 的**前置條件是「DSL schema 凍結」**（`04_SRS.md:387`），該前置從未達成。沒有 schema 就沒有解析器可寫——這是排程問題不是實作問題。 |
| provisioning 無 audit、無前置閘 | CR-0114 裁決 2 明文「純手動」。人工流程的稽核軌在 checklist 文字（`scripts/deploy/provision_brand.py:88-110`）與人的執行紀錄裡，程式面本來就不會有。 |
| 受保護層保護不到 domain-safety | FR-PLT-08 成文時（ADR-012）假設 skill 與 config 同屬一個 Config Registry。CR-0167／ADR-032 之後 skill 的 SSOT 移到 `saas.skill_revision` 並走 60s 熱更新（`agent/lockcore/agent/skill_sync.py:1-10`），保護層機制（`config_namespace.is_protected`）留在 config 那一側，沒有跟過去。 |
| SLO 只回建議不真 halt | `api/services/config_m18_service.py:985-986` docstring 自述：「halt 動作由 admin 顯式呼 rollback —— 對齊 dispute 負值 resolution 人工 trail 精神，**避免自動 trigger 風險**」。這是刻意設計，不是遺漏。但 canary cron 後來（`config_canary_advance_cron.py`）補上了自動推進，一邊自動推、一邊不自動停，兩個決策沒對齊。 |
| 人工派工不排除未授權技師 | CR-0114 R4 裁決 3／裁決 7 的刻意分岔：自動派工過濾、人工派工標示。 |
| 撤證不影響派工 | `api/services/technician_certification_service.py:4-5` 明文「與 `technician_brand_authorization`（063，dispatch 品牌過濾用）**職責分離**」。認證矩陣本來就是為師傅詳情頁的展示資料而建。 |
| bronze 紅線腳本沒接 CI | `audit_corpus.py:1-3` docstring 寫「任一違規 exit 1，**可入 CI**」——「可入」不是「已入」。 |

---

## 4. 現況證據（回查證後對走查文件的更正）

走查文件 7 支中 5 支引用有偏移或有誤，逐條列出（走查文件本身**不改**，更正記在本 CR）：

| TC | 走查文件寫法 | 覆核後事實 |
|---|---|---|
| TC-PLT-CFG-01 | 「受保護的 namespace 目前**只有 `payment_gate` 一個**」 | 實際三個：`payment_gate`（`SQL/migrations/103-config-namespace-owner-protected.sql:37-39`）、`settlement_policy`（`SQL/migrations/118-settlement-policy-namespace.sql:42`）、`dispatch_policy`（`SQL/migrations/127-dispatch-policy-namespace.sql:39-41`）。三者皆非 escalation／domain-safety，**結論不變**，但保護層覆蓋面被說小了。 |
| TC-PLT-CFG-01 | 引 `103-...sql:36-40` / `:37-40` | UPDATE 語句實際在 `:37-39`（`:36` 是註解、`:40` 空行）。語意無誤。 |
| TC-TEC-LIFE-01 | 「重送註冊冪等 → **部分**：回 409 `EMAIL_TAKEN`，非冪等回既有」 | **這條結論是錯的**。註冊端點掛了冪等守衛：`api/routers/auth.py:370` `idem: IdempotencyContext \| None = Depends(_public_register_idem)`、`:381` `await idem.save(201, sanitized)`，工廠在 `api/core/idempotency.py:311-335`；既有測試 `api/tests/test_cr_0165_register_idempotency.py:56-58` 斷言同 key 同 body 回放 201 同 id；且 `web/tech-portal/src/lib/api.ts:641` 對所有 POST 自動注入 `Idempotency-Key`。409 只在不帶 key 或帶不同 key 時發生。**本子項應判「一致」。** |
| TC-TEC-LIFE-01 | 投影白名單在 `tech_mirror.py:43-49`／不鏡射註解在 `:51-56` | 實際 `_MIRRORED_TABLES` 在 `:38-44`、註解在 `:46-52`。內容正確。 |
| TC-TEC-REVOKE-01 | 「撤銷認證後候選集排除 → **部分**」 | 應為**完全沒有**：`grep -n technician_certification api/services/dispatch_service.py` exit=1 零命中。走查此處偏輕。 |
| TC-REF-INTAKE-01 | 把 `audit_corpus.py` 描述成「CI gate」 | `.github/workflows/` 現有 **20 支** workflow，以檔名呼叫 `scripts/ci` 腳本的只有 `migration-drift-check.py`。`audit_corpus.py` 與 `references-provenance-check.py` **既無 workflow 也無 pytest wrapper**（對照組：`endpoint-guard-audit.py` 有 `api/tests/test_sec_legacy_endpoint_guards.py:180` 的子行程包裝）。所以 bronze-only 紅線目前是「人工可跑的腳本」，不是「被強制執行的閘」。 |
| TC-REF-INTAKE-01 | `db.py:21-26` / `audit_corpus.py:55-57`、`:64-68` / `_provenance.py:27-30` | 實際 `db.py:20-25`、`audit_corpus.py:57-59`（gdrive 紅線）與 `:60-70`（provenance/漂移）、`_provenance.py:24-27`。各偏移 1-2 行，內容正確。 |
| TC-REF-PUBLISH-01 | 「Family Reviewer 逾時暫停 publish → **找不到**」 | **判重**。cron 只 SELECT 屬實（`api/realtime/family_review_sla_cron.py:94-108` 全檔無 `UPDATE sop_drafts`），但「暫停」在下游：`api/services/sop_draft_service.py:405-417` 的 `adopt_draft` 在灌 KB/RAG 前硬 gate `SELECT 1 FROM family_reviews WHERE sop_draft_id=%s AND action='approved'`，缺就丟 **425 `FAMILY_REVIEW_REQUIRED`**。逾時期間本來就沒有 approved 列 → publish 進不去。 |
| TC-REF-PUBLISH-01 | 「同人雙簽（refinery draft）→ **找不到**」並列為缺口 | **判重**。FR-REF-05（`04_SRS.md:345`）把雙簽定義在 **SOP 高風險軌**，該軌有 `SOD_VIOLATION` 403（`api/services/family_review_service.py:226-231`）。refinery draft 軌對應的是 FR-REF-03，草稿由 LLM 批次產生、**沒有人類 proposer**，「同一人簽兩次」在該軌結構上不存在。 |

> 走查文件三支未發現引用問題：TC-PLT-PROV-01、TC-PLT-FLOW-01（零命中主張以多種寫法重跑全部成立）、TC-TEC-REVOKE-01。

---

## 5. 程式碼現狀（分五塊）

### 5.1 TC-PLT-FLOW-01 —— 功能不存在（不是缺陷）

零命中經多寫法覆核：`DSL`（大小寫敏感）於 `api/ web/src SQL/ agent/ scripts/` 只命中一個**假陽性**
（`api/data/media/…/*.png` 的二進位內容剛好含 `DSL` 字元序列）；
`flow_dsl` / `block_library` / `積木` / `vertical.?pack` / `workflow_definition` / `flow_version` / `block_type` **全零**；
補試 `workflow|state_machine|flow_definition|flow_engine` 於 `api/ SQL/` 的 .py/.sql，只命中
`api/tests/test_cr_0190_release_governance.py` 的 GitHub Actions workflow（無關）。

repo 內**確有**「版本化＋發佈閘＋回滾＋稽核」的成熟四段式範式，但對象是 config 與 skill：

- `api/services/config_m18_service.py:334`（`create_draft`）→ `:391`（`start_rollout`）→ `:574`（`rollback`）→ `:192-214`（`_append_audit`，append-only）
- `api/services/skill_service.py:82-105`（`validate_publishable` 發佈閘）→ `:324`（`publish`）→ `:378`（`rollback`）→ `:493-522`（`_write_audit`）

既有狀態機**硬編碼在 service**、不是可匯入的定義檔：
`api/services/technician_lifecycle_service.py:38-45`（`_ALLOWED_TRANSITIONS` 模組層 dict）、
`api/services/work_order_service.py`（`STATE_CONFLICT` 判定散於各轉移函式）。
同檔 `:48-52` 另有一張**無人讀取的死表**，其註解自己寫著「這張表目前**沒有任何地方讀它**……別誤以為改了這裡就會生效」。

### 5.2 TC-PLT-CFG-01 —— 保護層保護不到該保護的東西，SLO 破線不停推廣

**① 保護層錯位。** config 側機制健全：`api/services/config_m18_service.py:168-173` 的
`CONFIG_PROTECTED_OVERRIDE` 403，且**排在 admin bypass（`:174-175`）之前**——連 admin 都不能做租戶層 override。
但 FR-PLT-08 / ADR-012:44 指名要保護的 **escalation／domain-safety 根本不是 config namespace**，
它是 skill 內的 Markdown 段落（`agent/lockcore/skills/locksmith-product-knowledge/SKILL.md:33`、`:56`）。
而 skill 發佈閘 `api/services/skill_service.py:82-105` 只驗五件事：skill 名 kebab-case、路徑無 traversal、
路徑碰撞、`SKILL.md` ≤16KB、frontmatter 有 `name`/`description`——**零內容段落檢查**。

疊上 CR-0167：skill SSOT 已在 `saas.skill_revision`，`SkillSync` 60s 輪詢物化到 workspace overlay
（`agent/lockcore/agent/skill_sync.py:1-10`、`:31` `_DEFAULT_POLL_SECONDS = 60`）。
**淨效果：租戶 admin 可以發佈一版把 domain-safety 整段刪掉，60s 內對真實 LINE 客戶生效，全程無任何閘。**

**② SLO 破線不會停止擴散。** `config_m18_service.py:983-986` docstring 自述「本函式只回 decision，不真實 halt」；
`:1031-1040` 對 `saas.config_rollout` **只 SELECT**；`:1062-1067` 只回 `should_halt` + 建議字串；
唯一寫入是 `:1069-1075` 的 audit（且借用 `action="rollout_started"` enum，靠 `diff.slo_check` 標識）。
而自動推進 `api/realtime/config_canary_advance_cron.py:105-115` 的 SELECT 條件是
`strategy='canary_5_50_100' AND current_stage IN ('5%','50%') AND next_stage_eta < NOW()`——
**全函式不讀任何 SLO 結果**。所以 SLO 破線時 rollout 仍會照 ETA 自動 5%→50%→100%。

**③ eval 結果不入任何 audit 表。** `agent/scripts/run_forbidden_gate.py:8` 產物落 `evals/forbidden_run_<ts>.json` 檔案，
`:11` 自述「1=gate 未過（CI 據此 **block deploy**）」，走 `.github/workflows/forbidden-eval-gate.yml`。
它擋的是**部署**，不是 config/skill 的**發佈端點**；結果不進 `saas.config_audit` 也不進 `saas.skill_audit_log`。
TC 判定基準「版本、審核、**測試**與 rollback 全留 audit」的「測試」那一項未達成。

**④ 兩套 audit 的失敗語意不一致。** config audit 在同交易內（`:192-214`）；
skill audit 是 best-effort，失敗僅 warning（`skill_service.py:503`、`:521`）。

### 5.3 TC-PLT-PROV-01 —— 一條被裁決為手動的流程

- `api/services/platform_tenant_service.py:123-162` `update_license` **全函式**只驗三件事：
  plan_tier 值域（`:140-142`）、core 強制保留（`:145`）、未知模組 422（`:146-149`），
  然後直接 `UPDATE tenant`（`:156-159`）。**無任何建庫／LINE 綁定／health check 前置條件**。
  變更只留一行 `logger.info`（`:160-161`）。
- `provisioning` 一詞於 `api/`、`SQL/`、`web/platform-console/` **零命中**（自行重跑，含更寬鬆的 `provision`）；
  平台庫 `SQL/platform/Schema_platform.sql` 只有 5 個 `CREATE TABLE`（users:17 / revoked_jti:50 /
  brand_applications:63 / monitor_target:112 / tenant:139），**確無 audit 表或 event 表**。
- 冪等三處落點語意不一致：`platform_tenant_service.py:203` `ON CONFLICT (slug)` 冪等；
  `scripts/db/provision-brand-tenant.sh:36-42` 檔頭自述冪等；
  `scripts/deploy/provision_brand.py:143-145` 對已存在的 `.env` 直接 `return 1` **拒絕重跑**（與 TC「重跑冪等」相反）。
- LINE 綁定是 checklist 純文字（`provision_brand.py:100` 第 [6] 步）；
  該 checklist（`:88-110`，共 8 步）**完全沒有 health check 步驟**（`grep -n health scripts/deploy/provision_brand.py` 零命中），
  health check 在部署腳本層 `scripts/deploy/agent.sh:275-291`，與 License 不連動。
- **附帶發現（架構邊界）**：`assert_module_entitled`（`platform_tenant_service.py:178-183`）
  在 `api/` 內**除自身與測試外零呼叫點**（唯一命中是 `api/tests/test_cr_0166_license.py`）。
  實際在消費 License 的是 `knowledge-pipeline/refinery/refinery/entitlement.py:25-49` 的**獨立實作**，
  且兩者 fail 語意不同——refinery 版在平台庫未配置時 **fail-open**（`entitlement.py:29-31` 回 `True`）。

### 5.4 TC-TEC-LIFE-01 / TC-TEC-REVOKE-01 —— 派工准入閘的三個洞

**成立的部分**（不要重做）：
生命週期硬排除成立（`api/services/dispatch_service.py:187` `_DISPATCH_INELIGIBLE_STATUSES`，
套用點 `:448-449`，人工 `list_dispatch_candidates` 與自動 `auto_match_dispatch` 共用 `_score_rows`）；
復權 CAS 成立（`technician_lifecycle_service.py:79-86` + `:110-118` DB 層 CAS，端點掛 `require_platform_admin`）；
撤證即時性成立（`technician_brand_auth_service.py:7-9` pull-on-read，候選查詢每次 live 讀權威庫無快取）；
身分 PII 不外流成立（`api/core/tech_mirror.py:46-52` 明確排除 `password_hash`/`email`/`phone`/`address`，
`technician_kyc` 完全不鏡射）。

**洞①：人工派工候選集不排除未獲品牌授權技師。**
`dispatch_service.py:555-563` 只標 `brand_authorized`（true/false/null），
`:569` 只讓已授權者排前，**可見性不變**。與 `04_SRS.md:352` FR-TEC-02 驗收直接衝突。

**洞②：品牌查無授權列時 fail-open。**
`dispatch_service.py:392-404`：`brand_auth_enforce` 開 → 回空集合（fail-closed）；未開 → 回 `None`＝不過濾。
該開關**預設 off**（CR-0197 D1(c) 業主裁決）。
但 `dispatch_service.py:319-327` 的 docstring 已於 2026-08-05 更新記錄了一件事：
**「平台後台還沒有維護授權名單的 UI」這個前提已經解除**——UI 於 2026-08-02 落地
（commit `a38e5f80`，`web/platform-console/src/components/technicians/BrandAuthorizationPanel.tsx`，
掛於 `platform/technicians/[id]/page.tsx:358`）。也就是說「閘門能不能開」的最後一個 code 前提沒有了，
**剩下的純粹是營運動作與業主決定**。

**洞③：撤銷 `technician_certification` 對候選集零影響。**
`grep -n technician_certification api/services/dispatch_service.py` exit=1。
派工只讀 `technicians.status` 與 `technician_brand_authorization`。
且 `technician_certification_service.py:166-181` 的 `delete_certification` 是**硬 DELETE、無任何 audit**。
TC-TEC-REVOKE-01 步驟的第一個動作（撤銷認證）對候選集毫無影響。

**洞④：三條路徑（撤證／停權／復權）皆無通知發送。**
以 `notification|notify|push|broadcast|line_push` 重掃
`technician_lifecycle_service.py`、`technician_brand_auth_service.py`、`technician_certification_service.py`
三檔零命中；`technician.certification_revoked`（FR-TEC-08，`04_SRS.md:358`）以
`certification[._-]?revoked` / `revoke[d]?[._-]?certification` / `cert_revoked` 重掃全樹亦零命中。
同理 FR-TEC-01 要求的 `technician.registered` 事件（`04_SRS.md:351`）以四種寫法重掃全樹零命中。

**洞⑤：稽核非冪等（走查未計分的實質缺陷）。**
`technician_brand_auth_service.py:115-120` 的 UPDATE **沒有 `AND authorized = TRUE` 條件**，
對已是 FALSE 的列仍會 `RETURNING` 命中；`:125` 的 `_audit_lifecycle` 位於 `row is None` 分支之後、
**無條件執行**。所以重複撤銷同一品牌會**每次都 append 一筆 `brand_auth_revoked` 稽核列**。
更精準地說：`:108` 的 docstring 自己寫「重複撤 200 no-op」——**行為與 docstring 矛盾**，
它在稽核軌上不是 no-op。

### 5.5 TC-REF-INTAKE-01 / TC-REF-PUBLISH-01 —— 知識軌的紅線沒有執行點

**成立的部分**（不要重做）：
未核可零落地成立（`review.py:89-108` 是唯一落地入口，`reject`/`re_refine` 不呼叫 publisher，
落地與狀態轉移同交易）；跨租戶 publish 成立（`service.py:92-94` token tenant 比對、`review.py` 一律
`WHERE tenant_id`、`api/routers/skills_v2.py:151` 走 token claim 非請求參數）；
汲取重送冪等成立（`store.py:42` `ON CONFLICT (tenant_id, draft_key) DO NOTHING`）；
tenant default-deny 成立（`knowledge-pipeline/refinery/refinery/db.py:20-25`，
未設 `REFINERY_TENANT_ID` 直接 `RuntimeError`，**絕不退回全庫查詢**）；
knowledge_ready gate 成立（`intake.py:25-38` 的
`status='resolved' AND knowledge_ready=TRUE AND NOT EXISTS(活 draft)`）；
facts 帶 tenant/provenance 進 pgvector 成立（`publisher.py:34-53`）；行為軌 append-only 成立
（`publisher.py:56-70` 產新檔、`skill_service.py:443-478` merge 嚴格加性）。

**洞①：raw→bronze 入口無來源准許 gate。**
`knowledge-pipeline/pipeline/raw_to_bronze/` 五支 processor
（`process_youtube.py` / `process_website.py` / `process_video.py` / `process_line.py` / `process_gdrive.py`）
對 `tenant|allowlist|white.?list|白名單|准許|gate` **零命中**（自行重跑）。
紅線只在下游 corpus 層：`audit_corpus.py:57-59`（facts 不得含 gdrive）、`:60-70`（provenance 完整＋sha256 未漂移）。
> **這一項我認為不該當缺口修 code**——bronze 是原始落地層，紅線設計上就在 corpus 層。
> 是 TC 判定基準「僅符合 gate 的資料進 **bronze**」把層次講錯了。見 §6.3。

**洞②：兩支 bronze 紅線腳本零 CI 掛載。**
`audit_corpus.py:1-3` 自述「任一違規 exit 1，**可入 CI**」，但現有 20 支 workflow 中無任何一支呼叫它；
`scripts/ci/references-provenance-check.py` 同樣無 workflow 也無 pytest wrapper。
**綠燈不代表紅線有守。**

**洞③：汲取失敗只有一行 stderr。**
`run_intake.py:59-62` 的 `except` 只 `print(..., file=sys.stderr)` + `skipped += 1`。
`knowledge_drafts` 的狀態值域（`SQL/migrations/094:32-33`）無 failure 值；
以 `failure|failed|error_log|audit_event|last_error` 複掃 refinery 全 package，只命中問題卡的 `failure_mode` 欄位。
TC 判定基準「**失敗原因可稽核**」不成立。

**洞④：`fetch_transcript` 在 try 範圍外（單檔 bug）。**
`run_intake.py:51` `transcript = intake.fetch_transcript(...)` 在 `:52` 的 `try` **之前**，
而該 try 只包 `refine_card`。DB 例外會逸出 → **單卡讀取失敗會中斷整批**，
與同段 `:59` 註解「單卡失敗不中斷批次」的設計意圖矛盾。

**洞⑤：Publisher 灌注前無來源校驗。**
`publisher.py:20-53` `publish_case_entry` 全函式對來源零校驗。
BR-KN-001（`04_SRS.md:518`）與 FR-REF-04（`:344`）都寫「Publisher 灌注前校驗來源白名單」。
但如 §2.2④ 所述，**該軌根本沒有 bronze 血緣可驗**。

---

## 6. 影響評估

### 6.1 Rewrite vs Refactor 九維打分（依 `.claude/rules/change-governance.md`）

打分基準＝**「照現行正典把 7 支全做完」**的規模，不是「按我建議的裁決路徑」的規模。

| # | 維度 | 分數 | 依據 |
|---|---|:--:|---|
| 1 | 產品目標是否改變？ | **0** | 7 支對應的需求全部已在 `04_SRS.md` 內，沒有一條是新目標。這是落地度問題不是方向問題。 |
| 2 | 核心 User Flow 是否改變？ | **1** | 新增兩條分支流程（租戶自助設計工單流程 FR-PLT-07、自動化 provisioning FR-PLT-03）；既有主流程（LINE→問題卡→派工→報價→結算）不重寫。 |
| 3 | Domain Model 是否改變？ | **2** | FR-PLT-07 要求把工單／技師狀態機從硬編碼（`work_order_service.py` 各轉移函式、`technician_lifecycle_service.py:38-45`）外部化成可設定的 flow definition——這是把「工單生命週期」這個**核心概念的定義權從 code 移到資料**，屬核心概念改。（若 D1 選 (c) 移除規格，此維降為 1。） |
| 4 | API Contract 是否大量破壞？ | **1** | 多 endpoint 新增（flow 匯入／版本／回退、provisioning step、skill 保護段落 422、`update_license` 409），既有語意大多不破；唯一破壞性是 `list_dispatch_candidates` 若改回過濾會改變回應集合。 |
| 5 | DB Schema 是否需重建？ | **1** | 全是新增表（flow_definition / block_registry / flow_version / provisioning_step / provisioning_audit / skill_protected_block / refinery_intake_failure）＋ `config_rollout.current_stage` 的 CHECK 值域擴充。migration 可處理，不需重建既有表。 |
| 6 | 模組邊界是否錯誤？ | **1** | 有些混亂，三處實證：(i) FR-PLT-08 的保護層寫在 config 域，實作卻分裂在 `config_namespace.is_protected` 與無保護的 skill Markdown 兩邊；(ii) FR-REF-04 把兩條血緣不同的軌寫成同一個 Publisher 的責任；(iii) License 的真實消費者是 `knowledge-pipeline/.../entitlement.py:25-49` 的獨立實作，`api` 的 `assert_module_entitled` 零生產呼叫點且兩者 fail 語意相反。但沒有「根本切錯」。 |
| 7 | 測試是否可信？ | **1** | 部分可信。既有測試確實在跑且全過（走查實跑 config/skill 58 項、技師 45 項、refinery 36 項）。但兩支 bronze 紅線腳本零 CI 掛載＝**綠燈不代表紅線有守**；且 `20_Test_Cases.md:120/124/125` 的追溯欄自述三個 FR「完全沒有案例」，與同檔 `:418-420` 存在的三支 TC 矛盾。 |
| 8 | 文件是否可信？ | **2** | **本 CR 最重的一維。**四組矛盾全部有據（§2.2）：FR-PLT-03 三方矛盾（SRS 標階段二／測試計畫定 P0／業主裁決純手動）、`20_Test_Cases.md` 自己前後矛盾、FR-TEC-02 驗收 vs CR-0114 R4 裁決 3、FR-REF-04 的 bronze 白名單對 refinery 事實軌不成立。 |
| 9 | 團隊/AI 是否還理解系統？ | **1** | 少數人懂。三個實證陷阱：`dispatch_service.py:355-366` 的 docstring 自身在 2026-08-05 才被修正（原文與函式體矛盾，照舊文讀會誤以為閘門在擋）；`technician_lifecycle_service.py:48-52` 的死表帶著「別誤以為改了這裡就會生效」的警語；`config_m18_service.py:985-986` 自述「不真實 halt」而 TC 判定基準以為它會 halt。 |
| | **總分** | **10 / 18** | |

### 6.2 判斷

**10 分 ∈ 7–12 分區間 →「架構重審 + 模組拆分（多 CR + 跨 sprint）」。**

具體含義：**這張 CR 本身就不該當成一張 CR 實作**。它應該在 §8 裁決後拆成 4–5 張獨立 CR 分批走，
理由是四塊之間沒有共同的技術相依，卻各自有獨立的裁決風險：

| 拆分建議 | 內容 | 依賴 |
|---|---|---|
| CR-A（規格治理，零 code） | D1 / D2 / D7 的正典標注與測試計畫定位修正 | 無，可立刻做 |
| CR-B（Agent 安全閘） | D3 skill 保護段落 + D4 SLO 自動 halt | 無 |
| CR-C（派工准入） | D5 + D6 + D11 | 依賴 CR-0197 已落地的 `brand_auth_enforce` 開關 |
| CR-D（知識軌稽核） | D8 + D9 + D10 | 無 |

若 D1 選「排開發」，工單積木引擎應另立**獨立主幹型 CR**（它是子系統，不是功能點）。

### 6.3 誠實聲明：我認為其中 3 支不該當缺陷修

依任務要求「誠實優先於完整」，以下逐條說明**不建議寫 code** 的項目：

1. **TC-PLT-FLOW-01 整支** —— 不是缺陷。`04_SRS.md:387` 該列自標「🔜 規劃中」，
   **且前置條件「DSL schema 凍結」從未達成**。沒有 schema 凍結就寫解析器等於先蓋屋頂。
   正確動作是 D1 裁決 + 在測試計畫把它標 `deferred / blocked-by: DSL schema freeze`，
   而不是留在 UAT 清單裡當永久紅燈。

2. **TC-PLT-PROV-01 的「未完成任一步不得啟用 License」與「provisioning audit」** ——
   正典自己標階段二（`04_SRS.md:383`、`:577`），業主自己裁決純手動（`brand_application_service.py:3`）。
   一條**被決議不自動化**的流程沒有自動化狀態機，這是規格與測試計畫的定位錯誤，不是實作缺口。
   建議改 `20_Test_Cases.md:418` 的判定基準與 P0 定位，code 不動。
   （唯一該修的是 `provision_brand.py:143-145` 的 `.env` 拒絕重跑——那與 TC 的「重跑冪等」相反，
   且它是工程自用腳本，修它成本低、風險低。）

3. **TC-REF-INTAKE-01 的「僅符合 gate 的資料進 bronze」** ——
   層次錯配。bronze 是**原始落地層**（`04_SRS.md:330` FR-DAT-01：「raw → bronze（真相源，bronze-only sourcing）」），
   紅線設計上就在 corpus 層。判定基準應改成「僅符合 gate 的資料進 **facts 語料**」。

4. **TC-REF-PUBLISH-01 的「Publisher 灌注前校驗 bronze 白名單」** ——
   `04_SRS.md:344` 該欄的相鄰子句自標「🔜 規劃中」，且 refinery 事實軌**沒有 bronze 路徑可驗**。
   建議 D8 走文件限縮（選項 a），不要硬塞一個驗不到東西的檢查。

5. **TC-TEC-REVOKE-01 的「重送不重複通知」** ——
   FR-TEC-08 的「各品牌訂閱後更新派工可用性」依賴 FR-PLT-04 事件骨幹，
   而 FR-PLT-04 在 `04_SRS.md:384` 自標「🔜 規劃中（Phase 1 Redis / Phase 2-3 Kafka）」。
   在骨幹落地前「重送不重複通知」**無從驗證**。應在 TC 標 `blocked-by: FR-PLT-04`，不是留著當缺口。
   （現行以 pull-on-read 替代事件廣播——`technician_brand_auth_service.py:7-9`——是可行的替代方案，
   但 `04_SRS.md:358` 從未加標注說明這個替代。這是文件債，不是程式債。）

### 6.4 真正該修、且風險排序

| 順位 | 項目 | 嚴重度 | 理由 |
|:--:|---|:--:|---|
| 1 | skill domain-safety 段落可被租戶 admin 刪除且 60s 生效 | **P1** | 唯一一個「租戶操作能直接降低對真實客戶的安全護欄」的路徑 |
| 2 | SLO 破線不停止 canary 自動推進 | **P1** | 一邊自動推、一邊不自動停；壞版本會照 ETA 推到 100% |
| 3 | 人工派工不排除未授權技師（洞①②） | **P1** | 與 FR-TEC-02 驗收直接衝突，且 UI 前提已於 0802 解除 |
| 4 | bronze 紅線腳本零 CI 掛載 | **P2** | 綠燈不代表紅線有守 |
| 5 | 撤證無 audit、重複撤銷稽核非冪等 | **P2** | 稽核軌可信度 |
| 6 | 汲取失敗無持久化稽核、`fetch_transcript` 逸出 try | **P2/P3** | 後者是單檔 bug，CIA 豁免 |

---

## 7. 可行路徑（各決策點的技術可行性，不含裁決）

- **skill 保護段落**：現成範式可抄——在 `saas` 加 `skill_protected_block`（或在 `skill_revision` 存受保護段落 hash），
  `validate_publishable`（`skill_service.py:82-105`）增檢「受保護段落存在且未被改動」→ 422/403。
  發佈閘已是強制路徑（publish 與 rollback 都過），插入點單一。
- **SLO 自動 halt**：`check_slo_halt` 在 `should_halt` 時把 `config_rollout.current_stage` 寫成 `halted`
  （需擴 `SQL/migrations/004-config-m18.sql:91` 的 CHECK 值域＝DB schema 變更），
  並讓 `config_canary_advance_cron.py:105-115` 的 SELECT 條件排除 `halted`。兩處改動、語意單一。
- **eval 入 audit**：`run_forbidden_gate.py` 產物寫進 `saas.skill_audit_log`（或 `config_audit` 新 action），
  並把 CI gate 與發佈端點連動（目前只 block deploy，不 block publish）。
- **派工准入**：`brand_auth_enforce` 開關已在（`dispatch_service.py:310-340`），
  維護 UI 已在（`BrandAuthorizationPanel.tsx`），
  剩的是 `list_dispatch_candidates`（`:555-563`）要不要改回過濾，以及開關預設值。
- **稽核冪等**：`technician_brand_auth_service.py:116-118` 的 UPDATE 加 `AND authorized = TRUE`，
  依 `RETURNING` 是否命中決定要不要寫 audit（並保留「查無列 404」語意需另查一次）。
- **撤證 audit**：`technician_certification_service.py:166-181` 補一筆 `saas.technician_lifecycle_event`。
- **bronze 腳本接 CI**：比照 `.github/workflows/migration-drift-check.yml` 的形狀，複製即可。
- **汲取失敗稽核**：兩條路——(重) 新開 `refinery_intake_failure` 表或給 `knowledge_drafts` 加 failure 狀態
  （新 migration 且**必須登記 `SQL/migrations/MIGRATION_REGISTRY.md`**，否則 drift-check 會紅）；
  (輕) 走既有 `audit_events`（無 schema 變更，但仍動 Domain 語意）。
- **`fetch_transcript`**：把 `run_intake.py:51` 移進 `:52` 的 try 範圍。單一 function、無 contract 影響，**CIA 豁免**。

---

## 8. 🛑 Human Decisions Required

> 每題回「Dn 選 x」即可。標 ⭐ 者為建議優先回答。

### A 組 —— 規格級（要不要做）

**⭐ D1：FR-PLT-07 工單積木引擎（程式碼樹完全不存在）怎麼處理？**

這不是 bug，是**規格寫了但從未排進開發**的子系統。它的前置條件「DSL schema 凍結」（`04_SRS.md:387`）本身也未達成。

- (a) **排進開發** —— 另立獨立主幹型 CR，第一步先做 DSL schema 凍結（不寫 code），
  之後才談解析器／block 註冊表／flow 版本表／狀態機外部化。
  代價：這是子系統級工作量（保守估 2–3 個 sprint），且會把 `work_order_service` 與
  `technician_lifecycle_service` 的硬編碼狀態機翻掉——**風險最高的一項**，因為那兩個狀態機目前是派工與工單的地基。
- (b) **降級為 Phase 2** —— 正典 FR-PLT-07 加標注「v1 不實作，待 M__ 排入」，
  `20_Test_Cases.md:419` 的 TC-PLT-FLOW-01 標 `deferred / blocked-by: DSL schema freeze`，退出 UAT 清單。
  代價：驗收清單少一支 P1；好處是不再有永久紅燈誤導後續讀者（含 AI）。
- (c) **從 v1 正典移除** —— 承認積木引擎是 v2 的產品假設，把 FR-PLT-07 整列標 `deferred`，
  並把 `20_Test_Cases.md:124` 的追溯狀態改為「規格 deferred，非缺案例」。
  代價：需同步處理 ADR-P010/P011 的引用；好處是九維第 3 維降 2→1、第 8 維的矛盾少一組。

> **我的建議：(b)。**
> 理由：(a) 的實際成本不是寫 flow 引擎，而是**把既有兩個穩定運作的硬編碼狀態機拆掉**——
> 那兩個狀態機正是 TC-TEC-LIFE-01／TC-TEC-REVOKE-01 判定「成立」的部分所依賴的東西
> （`technician_lifecycle_service.py:38-45` + `:79-86` CAS 是「復權前不得自行恢復」成立的唯一原因）。
> 在 v1 UAT 期間動它，是拿已驗證的東西換未驗證的東西。
> (c) 過度——ADR-P010/P011 仍然是有效的長期方向，只是時機未到。
> (b) 保留方向、誠實標記時程，且立刻消掉一個 UAT 永久紅燈。

**⭐ D2：FR-PLT-03 provisioning 的三方矛盾，哪一份是 Source of Truth？**

`04_SRS.md:383` + `:577` 說階段二｜`20_Test_Cases.md:418` 定 P0 且要求自動化狀態機｜
`brand_application_service.py:3` + `Schema_platform.sql:101` 說業主裁決純手動。

- (a) **以業主裁決（純手動）為準** —— 改 `20_Test_Cases.md:418` 的判定基準與優先級
  （P0 → 標 `deferred`，或改寫成「手動 provisioning checklist 完整性 + tenant 隔離生效」的可驗版本），
  code 只修 `provision_brand.py:143-145` 的 `.env` 重跑行為。
  代價：平台開站流程在 v1 沒有程式化稽核軌（但本來就沒有，且是決議的結果）。
- (b) **以測試計畫（P0 自動化）為準** —— 推翻 CR-0114 裁決 2，做 provisioning 狀態機：
  平台庫新增 `tenant_provisioning_step` + `provisioning_audit` 兩表、`update_license` 前置查完成度回 409、
  把 LINE 綁定與 health check 從 checklist 升為可程式化驗證的 step。
  代價：跨 DB schema／API contract／User flow 三面向，且推翻既有業主裁決；工作量約 1 個 sprint。
- (c) **折衷** —— 維持手動開站，但補**最小稽核軌**：`update_license` 寫一筆 `provisioning_audit`
  （who/when/tier/modules，取代目前唯一的 `logger.info`），不做前置閘、不做狀態機。
  代價：小（一張表 + 一處寫入）；好處是「誰在什麼時候開通了誰」有紀錄。

> **我的建議：(a) + (c) 的組合，即「以純手動為準，但補一張 License 變更稽核表」。**
> 理由：(b) 推翻的是你自己在 CR-0114 下的裁決，而那個裁決在當時是對的
> （品牌開站一年不會發生幾次，自動化投報比極低）。但 (a) 純改文件會留下一個真實風險：
> **License 是收費與模組開通的閘，目前變更只有一行 `logger.info`**（`platform_tenant_service.py:160-161`），
> 事後查不出「誰把哪個租戶升到 pro」。這一項與 provisioning 自動化無關，值得單獨補。

### B 組 —— 安全閘門級

**⭐ D3：skill 內的 domain-safety / escalation 段落要不要變成程式化的不可覆寫層？**

現況：租戶 admin 可發佈一版把 `SKILL.md:56` 的 "Domain safety rules" 整段刪掉，
`validate_publishable`（`skill_service.py:82-105`）不檢查，SkillSync 60s 內對真實 LINE 客戶生效。
FR-PLT-08（`04_SRS.md:388`）與 ADR-012:44 都明文要求「受保護層不可 override」。

- (a) **做 protected block 機制** —— `saas` 加受保護段落註冊（表或 revision 內 hash），
  `validate_publishable` 增檢「受保護段落存在且未被改動」→ 422，補守線測試。
  代價：一張新表 + 發佈閘改動 + 需定義「哪些段落受保護」的初始清單（這本身要業主／領域專家點頭）。
- (b) **輕量版：只擋刪除，不擋修改** —— 只檢查 `SKILL.md` 是否仍含指定的 heading 錨點
  （例如 `## Domain safety rules`），缺就 422。
  代價：擋得住「整段刪掉」，擋不住「留標題改內容」；但實作成本極低（一個字串檢查）。
- (c) **不做，改文件** —— 在 FR-PLT-08 / ADR-012 加標注：「v1 的受保護層只涵蓋 config namespace
  （`payment_gate` / `settlement_policy` / `dispatch_policy`），skill 內容層的保護待 M__」。
  代價：正典與實作一致了，但風險留著；且四個 builtin skill 的安全規則對租戶完全開放。

> **我的建議：(b) 先做，(a) 排入下一輪。**
> 理由：這是本 CR 我認為**最該優先修**的一項——它是唯一一個「租戶的日常操作能直接降低對真實客戶的安全護欄」
> 的路徑，而且因為 CR-0167 的 60s 熱更新，錯誤生效速度比其他任何缺口都快。
> (b) 的成本大約是半天，能擋掉最可能發生的意外（編輯時整段誤刪）；
> (a) 才是完整解，但它需要先定義「受保護段落清單」，那是需要你和領域專家一起決定的事，不該卡住 (b)。
> (c) 我不建議——「文件與實作一致」不等於「風險被接受」，而這個風險沒有補償控制。

**D4：config rollout 的 SLO 破線要不要自動停止推廣？**

現況：`check_slo_halt` 只回建議（`config_m18_service.py:983-986` 明文「不真實 halt」），
canary cron（`config_canary_advance_cron.py:105-115`）純依 ETA 推進、不讀 SLO。
一邊自動推、一邊不自動停。

- (a) **自動 halt** —— `should_halt` 時把 `config_rollout.current_stage` 寫成 `halted`
  （需擴 004 migration 的 CHECK 值域），cron 的 SELECT 排除 `halted`。
  代價：DB schema 變更；且違背 `:985-986` 原本「避免自動 trigger 風險」的設計理由。
- (b) **不自動 halt，但停自動推進** —— 保留人工 rollback 的設計，
  但讓 cron 在推進前先呼一次 SLO 檢查，破線就**跳過推進**（不改狀態、記 warning）。
  代價：小（cron 內加一次呼叫）；語意是「壞版本停在原 stage 等人處理」而非自動回退。
- (c) **維持現狀，改文件** —— 在 TC-PLT-CFG-01 判定基準把「失敗時停止擴散」改為
  「失敗時產出 halt 建議與 audit，由 admin 顯式 rollback」，與 `:985-986` 的設計理由對齊。
  代價：TC 從紅燈變綠燈，但「壞版本會自己推到 100%」這件事仍然為真。

> **我的建議：(b)。**
> 理由：(a) 直接推翻了一個有明確理由的既有設計（避免自動 trigger），而那個理由是成立的
> ——自動回退在金流／派工域確實有風險。但 (c) 不可接受：**自動推進與人工停止是不對稱的**，
> 「凌晨三點 SLO 破線、cron 照推到 100%」不需要任何人犯錯就會發生。
> (b) 恰好補上這個不對稱：自動的東西自動停，回退仍然要人按。

### C 組 —— 語意與稽核級

**⭐ D5：人工派工候選集要不要排除未獲品牌授權技師？（FR-TEC-02 vs CR-0114 R4 裁決 3）**

`04_SRS.md:352` + `:362` 說「未過准入閘門不得進入派工候選集」且「不變且未被放寬」；
`dispatch_service.py:555-557` 註解說 CR-0114 R4 裁決 3 把過濾改成標示。

- (a) **以 SRS 為準** —— `list_dispatch_candidates` 改回過濾（或加「未授權者需帶 `override_reason` 才可挑」的硬閘），
  並把 `dispatch_policy.brand_auth_enforce` 翻成預設 on。
  代價：**必須先補齊 prod 授權名單**，否則 Chatlock／Dormakaba／美樂／Xiaomi／Gateman 全部無法派工
  （`dispatch_service.py:316-318` 已載明這五個品牌一筆授權都沒有）。維護 UI 已於 0802 落地，補資料的工具在了。
- (b) **以 CR-0114 R4 為準** —— 在 `04_SRS.md` FR-TEC-02 旁**加標注**（只可新增標注、不可改寫原文）：
  「品牌授權在人工派工改為標示＋主管判斷，自動派工維持過濾」。
  代價：零 code；但「准入閘門」在人工路徑上名存實亡。
- (c) **折衷** —— 人工候選維持全可見（派工小編需要看到全部人選），
  但**指派動作**（`assign_dispatch`）對未授權技師要求 `override_reason`
  ——把閘門從「可見性」移到「動作」。`work_order_service._assert_brand_authorized` 已有同機制。
  代價：中（一處新增檢查 + 前端要傳 override 理由）；語意上最接近 SRS「不得**進入**候選集」的意圖
  又不犧牲派工小編的可見度。

> **我的建議：(c)。**
> 理由：(a) 的問題是 SRS 那句話寫的是「候選集」，但實務上派工小編需要看到全部人選才能判斷
> （這正是 CR-0114 R4 改成標示的原因，那個決定不是隨便做的）。
> (b) 的問題是它把一個 P0 准入閘門降級為 UI 提示，而 `:362` 的 CR-0195 標注才剛強調過「不變且未被放寬」。
> (c) 讓「看得到」與「派得下去」分離：可見性服務營運，`override_reason` 服務稽核。
> 這也與報價 gate、熔斷用的是同一個安全閥機制，不引入新概念。
> 另外請注意：無論選哪個，`brand_auth_enforce` 的**預設值仍是獨立的一題**——
> 我建議維持預設 off，等你確認營運已補齊名單後再逐租戶開，這與 CR-0197 D1(c) 的裁決一致。

**D6：撤銷 `technician_certification` 要不要影響派工候選集？**

現況：`dispatch_service.py` 對 `technician_certification` 零引用；
`technician_certification_service.py:4-5` 明文「與 `technician_brand_authorization` **職責分離**」。
TC-TEC-REVOKE-01 步驟的第一個動作（撤銷認證）對候選集毫無影響。

- (a) **耦合** —— 派工判定加入「有效認證」條件。
  代價：改 domain model（推翻 `:4-5` 的職責分離設計）；且認證資料目前是展示用途，
  資料完整度未經營運驗證，貿然接上會擋掉大量現有技師。
- (b) **不耦合，改 TC 判定基準** —— 在 TC-TEC-REVOKE-01 加註「撤銷認證不影響候選集，
  影響候選集的是品牌授權（`technician_brand_authorization`）與生命週期狀態」。
  代價：零 code；TC 步驟第一動作變成「驗證它**不**影響」。
- (c) **不耦合但補稽核** —— 維持職責分離，但給 `delete_certification`（`:166-181` 目前是硬 DELETE 無 audit）
  補一筆 `saas.technician_lifecycle_event`。
  代價：小；解決「認證撤銷完全沒有稽核軌跡」這個獨立問題。

> **我的建議：(b) + (c)。**
> 理由：(a) 的風險不在實作而在資料——把一個沒經過營運驗證的資料表接上派工准入，
> 等於用未知品質的資料擋真實工單。(b) 讓規格與實作對齊。(c) 是獨立於 (a)/(b) 的補洞：
> 不論認證影不影響派工，「刪掉一筆認證不留任何紀錄」都不應該。

**D7：FR-TEC-08 的撤證即時廣播與「重送不重複通知」怎麼處理？**

現況：三條路徑零通知程式碼；`technician.certification_revoked` 事件全樹零命中；
`technician.registered`（FR-TEC-01）同樣零命中。
實作以 pull-on-read 替代（`technician_brand_auth_service.py:7-9`），但 `04_SRS.md:358` 從未標注此替代。

- (a) **標 blocked** —— TC-TEC-REVOKE-01 的「重送不重複通知」標 `blocked-by: FR-PLT-04`
  （事件骨幹在 `04_SRS.md:384` 自標階段二），並在 FR-TEC-08 旁加標注說明 v1 走 pull-on-read。
  代價：零 code；TC 從「缺口」變「未到驗證時機」。
- (b) **做輕量通知** —— 撤證／停權時發 WS/Redis 通知給該技師，以既有 realtime 層實作。
  代價：中（新增通知路徑 + 冪等鍵設計）；但 FR-TEC-08 要的是「**各品牌訂閱**後更新派工可用性」，
  通知技師本人並不滿足該條文。
- (c) **維持現狀不標注** —— 不建議。

> **我的建議：(a)。**
> 理由：FR-TEC-08 的驗收對象是「各品牌訂閱」，那是事件骨幹的能力，而事件骨幹本身是階段二。
> 在骨幹落地前做 (b) 只會做出一個不滿足條文、又要日後拆掉的東西。
> 但 pull-on-read 的替代**必須寫進正典標注**——否則下一個讀 `04_SRS.md:358` 的人（含 AI）
> 會以為有事件廣播，去找一個不存在的東西。

**D8：FR-REF-04 / BR-KN-001 的「Publisher 灌注前校驗 bronze 白名單」怎麼收？**

`publisher.py:20-53` 全函式無來源校驗；而 refinery 事實軌的來源是問題卡＋對話逐字稿，**沒有 bronze 血緣**。

- (a) **改文件限縮** —— 把 FR-REF-04 / BR-KN-001 的「Publisher 前校驗 bronze 白名單」
  明確限縮到 **knowledge-pipeline 外部素材軌**，並註明 refinery 診斷對話軌的來源校驗＝
  「problem_card 血緣完整」（`source_problem_card_id` 非空 + provenance 完整）。
  代價：零 code；正典與架構對齊。
- (b) **重新定義為「准許來源白名單」並實作** —— 在 `publisher.py:20-53` 前加一道來源型別白名單檢查
  （只准 `source_problem_card_id` 非空且 `draft.provenance` 完整）。
  代價：動到 `case_entries` 的落地 invariant（Domain model）+ 重新界定 Publisher 是不是紅線執行點
  （Architecture boundary）；但實作量小，且能擋住「provenance 殘缺的 draft 也能落地」。
- (c) **兩者都做** —— (a) 改文件釐清層次，(b) 補一道實際擋得住的檢查。

> **我的建議：(c)。**
> 理由：(a) 單獨做會留下一個真空——目前 `publisher.py` 對 draft 內容**完全信任**，
> 一個 provenance 空的 draft 只要被 approve 就會進 pgvector 且 `verified=TRUE`。
> (b) 單獨做則會讓正典繼續寫著一個對半數軌道不成立的條文。
> 兩件事成本都很小，一起做才是把地圖和世界對齊。

**D9：兩支 bronze 紅線稽核腳本要不要接進 CI？（change-governance 明列「改變 CI quality gate」需 CIA）**

`audit_corpus.py` 與 `scripts/ci/references-provenance-check.py` 目前無 workflow、無 pytest wrapper。

- (a) **接進 GitHub Actions** —— 比照 `.github/workflows/migration-drift-check.yml` 的形狀新增 workflow。
  代價：小；但若現有語料有既存違規，會立刻讓 CI 變紅（需先跑一次確認基線）。
- (b) **接成 pytest** —— 比照 `endpoint-guard-audit.py` 的做法（`api/tests/test_sec_legacy_endpoint_guards.py:180` 子行程包裝）。
  代價：小；好處是與現有測試套件同一入口，但 refinery 語料不在 `api/tests` 的範圍內，位置略彆扭。
- (c) **不接，改文件** —— 把 `audit_corpus.py:1-3` 的「可入 CI」改成「人工稽核腳本，發布前手動執行」。
  代價：零；但 bronze-only 是 **BR-KN-001 級別的紅線**，靠人記得跑不可靠。

> **我的建議：(a)，但分兩步：先在本機跑一次確認基線乾淨，再接 workflow。**
> 理由：bronze-only 是你反覆強調的硬規則（PDF 不可信、只引 URL），
> 現在它的執行方式是「有人記得跑就跑」。這不是紅線，是建議。
> 先跑基線是因為若現有語料已有違規，直接接 CI 會讓所有 PR 立刻紅，反而導致大家 skip 它。

**D10：refinery 汲取失敗要不要持久化稽核？**

現況只有 `run_intake.py:60` 一行 stderr；`knowledge_drafts` 狀態值域無 failure 值。

- (a) **新表** —— 開 `refinery_intake_failure`（tenant_id / card_id / error / occurred_at）。
  代價：新 migration + **必須登記 `SQL/migrations/MIGRATION_REGISTRY.md`**（否則 drift-check 會紅）。
- (b) **走既有 `audit_events`** —— 無 schema 變更，新增一個 action。
  代價：小；但 `audit_events` 是業務稽核表，塞批次技術失敗會稀釋它的語意。
- (c) **不做，改判定基準** —— TC-REF-INTAKE-01 的「失敗原因可稽核」改為「失敗原因可從批次日誌追溯」。
  代價：零；但 refinery 是排程跑的，stderr 在 Cloud Run 會被日誌輪替吃掉。

> **我的建議：(a)。**
> 理由：refinery 是**無人看著跑的批次**，失敗訊息落在會被輪替的 stderr 等於沒有。
> 這與 `audit_corpus.py:9-10` 的既有決定同一個道理（那裡明文寫「CI log 會輪替，只印在 stdout 等於沒保留」）
> ——同一個專案已經為同一個問題做過一次正確判斷，這裡照做即可。(b) 會污染業務稽核表的語意。

**D11：重複撤銷同一品牌授權的稽核列要冪等，還是保留「每次操作都留痕」？**

`technician_brand_auth_service.py:116-118` 的 UPDATE 無 `AND authorized = TRUE`，
`:125` 的 `_audit_lifecycle` 無條件執行 → 重複撤銷會重複寫稽核列。
而 `:108` 的 docstring 自己寫「重複撤 200 no-op」——**行為與 docstring 矛盾**。

- (a) **改成冪等** —— UPDATE 加 `AND authorized = TRUE`，依 `RETURNING` 是否命中決定寫不寫 audit
  （「查無列 404」的語意需另查一次以區分「沒這筆」與「已是 FALSE」）。
  代價：小；動到既有測試預期。
- (b) **維持每次留痕，改 docstring** —— 承認「每次 API 呼叫都留一筆」才是完整稽核，
  把 `:108` 的「no-op」改成「重複撤 200，稽核仍記一筆（操作留痕）」。
  代價：零 code；但稽核表會被重複操作灌水，且 `technician_lifecycle_event` 是給人看狀態變化的表。
- (c) **折衷** —— UPDATE 加條件（狀態層冪等），但無論是否命中都寫 audit，
  以 `reason` 欄位區分「實際撤銷」與「重複請求」。
  代價：小；兩種需求都滿足。

> **我的建議：(a)。**
> 理由：`saas.technician_lifecycle_event` 這張表的用途是**生命週期事件**，不是 API 呼叫日誌。
> 一個技師的「品牌授權被撤銷」在生命週期上只發生一次，寫五筆會讓後續讀這張表的人
> （含將來要做技師申訴／稽核報表的人）誤判。API 呼叫層的留痕應該走 access log，不是這張表。

---

## 9. Suggested Implementation Order（待 §8 裁決後）

### S0 — 先做，不等裁決（CIA 豁免，單檔無 contract 影響）

| 項 | 內容 | 驗證 |
|---|---|---|
| S0-1 | `run_intake.py:51` 的 `fetch_transcript` 移進 `:52` 的 try 範圍 | 既有 refinery 測試 36 項；補一條「單卡 transcript 讀取失敗不中斷批次」 |
| S0-2 | `technician_brand_auth_service.py:108` 的 docstring 與行為對齊（不論 D11 選哪個，矛盾都要消） | 無需測試（純註解） |
| S0-3 | 刪除 `technician_lifecycle_service.py:53` 起的死表 `_EVENT_TRANSITIONS`（全檔唯一出現處就是定義，屬單檔死碼） | `grep -rn _EVENT_TRANSITIONS api/` 確認零引用後刪；跑技師生命週期測試 45 項 |

> S0-3 若你希望保留它作為描述性文件，則改為在 `:48-52` 的既有警語旁補「保留為文件用途」即可——請在 §8 之外一併示下。

### S1 — 文件層（零 code，依 D1/D2/D6/D7/D8/D9 裁決）

**可完全平行，互不相依。** 所有動作限於：`smartlock-docs/` **只加標注、不改寫原文**；
`20_Test_Cases.md` 的判定基準與優先級屬測試計畫，可依裁決修改。

1. D1 → FR-PLT-07 標注 + TC-PLT-FLOW-01 標 deferred
2. D2 → TC-PLT-PROV-01 判定基準與 P0 定位修正
3. D6(b) → TC-TEC-REVOKE-01 判定基準加註「撤證不影響候選集」
4. D7(a) → FR-TEC-08 標注 pull-on-read 替代 + TC 標 blocked-by FR-PLT-04
5. D8(a) → FR-REF-04 / BR-KN-001 限縮到外部素材軌
6. 一併修 `20_Test_Cases.md:120/124/125` 追溯欄與 `:418-420` 的自相矛盾（§2.2②）
7. 一併修走查文件的四處判定更正（§4）——**寫在本 CR，走查文件本身不動**

**驗證**：`grep` 確認每處標注都有引用具體 ID（FR-/BR-/TC-/CR-）；無任何 `smartlock-docs/` 原文行被改寫（`git diff` 逐行檢查）。

### S2 — 安全閘門（依 D3/D4，可與 S1 平行，兩項彼此獨立）

| 步 | 內容 | 相依 | 驗證 |
|---|---|---|---|
| S2-1 | D3(b) skill 保護段落 heading 錨點檢查加入 `validate_publishable`（`skill_service.py:82-105`） | 無 | 新測試：發佈缺 `## Domain safety rules` 的 SKILL.md → 422；既有 `test_skills_v2_endpoint.py` 不得回歸 |
| S2-2 | D4(b) canary cron 推進前查 SLO，破線跳過（`config_canary_advance_cron.py:105-115`） | 無 | 新測試：破線 rollout 不被 advance、stage 不變、記 warning；`test_config_m18.py` 不得回歸 |
| S2-3 | D3(a) 若採完整版：`skill_protected_block` 表 + migration（**登記 MIGRATION_REGISTRY.md**） | S2-1 | migration 冪等（連套兩次退出碼 0）；全套對照基線零新增失敗 |

### S3 — 派工准入（依 D5/D6，**必須序列**）

順序不可調換——先有名單才能談閘門，先有稽核才能談撤證語意。

1. **S3-1**（營運，非 code）：用已落地的 `BrandAuthorizationPanel.tsx` 補齊 Chatlock／Dormakaba／美樂／Xiaomi／Gateman 五個品牌的授權名單。
   驗證：prod 唯讀查詢 `technician_brand_authorization` 各品牌筆數 > 0 且非 `is_mock`。
2. **S3-2**：依 D5 實作（若選 (c)：`assign_dispatch` 對未授權技師要求 `override_reason`）。
   驗證：未授權技師無 override 指派 → 403；帶 override → 200 且落稽核。
3. **S3-3**：依 D11 修稽核冪等（`technician_brand_auth_service.py:116-118` + `:125`）。
   驗證：連撤兩次同一品牌 → `technician_lifecycle_event` 只增一列。
4. **S3-4**：依 D6(c) 給 `delete_certification`（`:166-181`）補 lifecycle audit。
   驗證：刪除認證後 `technician_lifecycle_event` 有對應列。
5. **S3-5**：`brand_auth_enforce` 是否翻預設 on——**等 S3-1 完成且業主確認**才動。

### S4 — 知識軌稽核（依 D8/D9/D10，S4-1 與 S4-2 可平行，S4-3 需 S4-1 先過）

1. **S4-1**：D9(a) 先在本機跑 `audit_corpus.py` 與 `references-provenance-check.py` 建基線。
   驗證：兩支 exit=0；若非 0，先修語料再談接 CI。
2. **S4-2**：D10(a) 新增 `refinery_intake_failure` 表 + migration（**登記 MIGRATION_REGISTRY.md**），
   `run_intake.py:59-62` 的 except 改為同時寫庫。
   驗證：migration 於兩庫各連套兩次退出碼 0；新測試「單卡失敗留一筆失敗紀錄」。
3. **S4-3**：D9(a) 接 workflow（比照 `migration-drift-check.yml`）。
   驗證：故意塞一筆 gdrive 來源的 facts → CI 紅；還原 → 綠。
4. **S4-4**：D8(b) `publisher.py:20-53` 前加來源型別白名單。
   驗證：provenance 殘缺的 draft 核可 → 拒絕落地且整交易回滾；既有 refinery 36 項不得回歸。

### S5 — License 稽核（依 D2(c)）

`update_license`（`platform_tenant_service.py:123-162`）補寫一筆稽核（who/when/tier/modules），
取代目前唯一的 `logger.info`（`:160-161`）。
驗證：`test_cr_0166_license.py` 不得回歸；新測試斷言 License 變更留下可查列。

### S6 — 收尾（所有分支完成後）

1. 更新 `CHANGELOG.md` `[Unreleased]` 的 Added / Changed / Decisions
2. 有架構決策者新開 ADR（append-only；舊的標 `superseded_by`）
3. 回填本 CR §8 的裁決結果與 §9 各步的 commit sha
4. 更新 `docs/uat/static-walkthrough-20260803/` 對應 TC 的「判定更正」標注
5. 更新 `smartlock-docs/enterprise/27_Roadmap` WBS 狀態欄（只標已驗證項）

### 全套驗證門檻（每一個 S 分支合併前）

- 受影響套件測試全綠，且**對照 scratch 基線零新增失敗**
- 有 migration 者：兩庫各連套兩次退出碼 0（冪等）+ drift check 綠 + REGISTRY 已登記
- **禁止對 5433 埠的 UAT 庫跑 pytest**（會污染業主驗收資料）

---

## 附錄：本 CR 的查證方式

- 所有 `檔案:行號` 於 commit `01114100` 重新開檔覆核；與走查文件（基準 `2cfeca92`）不同者已在 §4 標明。
  行號偏移主要來自 `dispatch_service.py` 於 2026-08-05 的 docstring 更新（`:537-545` → `:555-563`、`:603-608` → `:624-626`）。
- 零命中主張全部自行重跑並加碼多種命名寫法（camelCase / snake_case / kebab-case / 中文）：
  `DSL` 的唯一命中經確認為 PNG 二進位假陽性；
  `technician.registered` / `technician.certification_revoked` 各試四種寫法；
  `provisioning` 另試更寬鬆的 `provision`；
  `raw_to_bronze/` 另試 `tenant|allowlist|white.?list|白名單|准許|gate`。
- 未啟動任何服務、未連 prod、未對 5433 UAT 庫執行任何動作。
- 本 CR 未修改 repo 內任何其他檔案；`smartlock-docs/` 全程唯讀。
