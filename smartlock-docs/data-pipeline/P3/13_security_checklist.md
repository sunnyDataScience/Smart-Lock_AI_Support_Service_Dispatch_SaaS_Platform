# 13 安全與生產準備檢查清單 — data-pipeline

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 建立日期 | 2026-07-07 |
| 系統名稱 | data-pipeline（`data/` 離線數據中台 + `SQL/` schema/migration/三庫）|
| 評估人員 | 架構師（依程式碼靜態分析 + 事實表）|
| 安全現況摘要 | **本系統為離線批次 + 持久層，無線上端點；主要風險在資料來源可信度、migration forward-only 無回滾、多庫手動套用一致性、無備份/還原文件** |

> 符號：✅ 已實施 ／ ❌ 未實施（風險）／ ⚠️ 部分實施 ／ N/A 不適用
>
> ⚠️ **本系統與典型 web service 的安全模型不同**：`data/` 無對外 API、無使用者輸入端點（威脅面在資料來源與 LLM 輸出）；`SQL/` 的安全焦點在 schema 演進安全、多庫隔離、備份還原。本清單依此調整維度。

---

## A. 核心安全原則

| # | 項目 | 狀態 | 說明 / 風險 |
|---|---|---|---|
| A-01 | 最小權限原則 | ⚠️ 部分實施 | pipeline 用 service account（`credentials.json`）僅 `drive.readonly` scope（`config.toml:46`）；但 DB 套用 migration 需高權限帳戶（DDL），`[待確認]` 是否用 superuser |
| A-02 | 縱深防禦 | ⚠️ 部分實施 | 三庫物理隔離（品牌/技師/平台）提供 tenant 級縱深；但 pipeline 對 LLM 輸出無二次驗證（僅 Python 覆寫 source/source_type）|
| A-03 | 零信任（LLM 輸出不信任）| ✅ 已實施 | bronze→silver 對 LLM **強制覆寫客觀事實**（source/source_type）防幻覺（`架構書.md:139-144`）；**PDF 來源不信任**（只引 URL 不抄內容）|
| A-04 | 失敗安全 | ⚠️ 部分實施 | migration `ON_ERROR_STOP=0` 是 **fail-open**（容忍錯誤續跑），靠結尾 grep 攔真 ERROR；部分失敗可能被 benign 警告淹沒（見 C-04）|
| A-05 | 審計可追溯性 | ⚠️ 部分實施 | silver 保留 provenance（source/url/chunk_index）；migration 靠 `schema_migrations` + registry，但 registry「意圖非事實」、046 前歷史不可考（B-06）|

---

## B. 資料安全

| # | 項目 | 狀態 | 說明 / 風險 |
|---|---|---|---|
| B-01 | **知識來源可信度（bronze-only）** | ✅ 已實施 | 知識內容嚴格源自 `data/storage/bronze/`（字幕/website/transcript）；**PDF（GDrive）不可信 —— references 只引 URL 不抄內容**（CLAUDE.md sourcing rule、`data/README.md:23`）。此為本系統最重要的資料完整性控制 |
| B-02 | **LLM 幻覺防護** | ✅ 已實施 | bronze→silver 由 Python 強制覆寫 `source`/`source_type`，不信任 LLM 產生的 provenance（`架構書.md:139-144`）|
| B-03 | Bronze PII 治理 | ⚠️ 部分實施 | LINE Chat（CSV 匯出）可能含客戶 PII（對話內容）；`[待確認]` bronze/silver 是否對 PII 去識別；LINE bronze 僅 1 檔，量小但仍需評估 |
| B-04 | 三庫隔離（tenant 資料）| ✅ 已實施 | 一品牌一 DB 物理隔離（CR-0110）；品牌資料強隔離；技師庫/平台庫獨立（見 ADR-003）。優於未落地的 RLS 邏輯隔離 |
| B-05 | pgvector 資料安全 | ⚠️ 部分實施 | `manual_chunks`/`case_entries` embedding 存於品牌庫，隔離同 B-04；但 embedding 可能反推原文，`[待確認]` 是否視為敏感 |
| B-06 | **Migration 審計真相** | ⚠️ 部分實施 | `schema_migrations`(046 建)為唯一真相，但 046 前套用歷史多事後回填、時間點不可考；registry 狀態「意圖非事實」雙向漂移（`MIGRATION_REGISTRY.md:7-15`）|
| B-07 | Secret 管理（非硬編碼）| ✅ 已實施 | `GEMINI_API_KEY`/`credentials.json` 放 `.env`/gitignore，**不入 toml**（CLAUDE.md config pattern）；`config.toml` 只放 `service_account_file` 路徑指標 |
| B-08 | DB 連線字串安全 | ✅ 已實施 | `POSTGRES_URI` 由 `scripts/deploy/agent.sh --update-db-uri` 自動 URL-encode（禁手動構建）；三庫 URI 走 GCP Secret Manager |
| B-09 | 種子 PII 禁入 | ⚠️ 部分實施 | `SQL/seeds/README.md` **明令 PII 禁入**；但 demo 帳號（demo-admin/adminpass123）硬編於 README；`realistic_demo_seed.py` 僅 demo（見 E-02）|

---

## C. 應用（Pipeline / Migration）安全

| # | 項目 | 狀態 | 說明 / 風險 |
|---|---|---|---|
| C-01 | 輸入驗證（資料源）| ⚠️ 部分實施 | pipeline 從固定 config（playlist/Drive folder）汲取，非任意使用者輸入；但爬取的 website HTML / YouTube transcript 為外部內容，經 LLM 處理前無 sanitize（prompt injection 風險 `[待確認]`）|
| C-02 | **Migration idempotent** | ✅ 已實施 | `ADD COLUMN IF NOT EXISTS` / `DO $$ 查 pg_constraint $$` / `ON CONFLICT DO NOTHING`，可安全重套（`MIGRATION_REGISTRY.md:4`）|
| C-03 | **Migration forward-only 風險** | ⚠️ 部分實施（設計取捨）| **無 down migration、無版本鏈回滾**（見 ADR-002）；一旦套錯只能寫新 migration 修正，不能回退。生產套用前依賴手動 Cloud SQL 備份 |
| C-04 | **`ON_ERROR_STOP=0` 容錯淹沒真錯** | ⚠️ 部分實施（風險）| `apply-schema-prod.sh:47-57` 用 `ON_ERROR_STOP=0` 容忍 benign「already exists」，靠**結尾 grep 攔真 ERROR**；若真 ERROR 混在大量 benign 警告中可能被淹沒，部分套用失敗不易察覺 |
| C-05 | SQL Injection（pipeline 側）| N/A | pipeline 不對 DB 寫入（不建連線）；SQL 安全屬 api（見 `api/P3/13`）|
| C-06 | LLM 輸出注入 schema | ⚠️ 部分實施 | `generate_json(schema)` 強制結構化輸出；但 `content` 欄位為自由文字，下游若直接注入 SKILL.md，`$ARGUMENTS` 佔位符驗證（`approve_drafts.py`）是唯一 gate |
| C-07 | 產出鏈斷點的安全影響 | ⚠️ 需注意 | `silver_to_skill` 寫入死目錄（不存在），實務上**不會覆寫任何現行 references**（因目標不存在）；反而是「安全的失敗」，但也意味自動化知識更新完全失效（見 P1/05 §9）|
| C-08 | 依賴漏洞掃描 | ❌ 未實施 | `data/pyproject.toml` 用 `uv`；`[待確認]` 無 CI `pip-audit`；pipeline 依賴 yt-dlp/whisper/playwright/bs4 等，需定期掃描 |

---

## D. 基礎設施安全

| # | 項目 | 狀態 | 說明 / 風險 |
|---|---|---|---|
| D-01 | **備份與還原文件** | ❌ 未實施 | `apply-schema-prod.sh` 僅**提醒**手動 `gcloud sql backups create`，非自動；**無備份/還原策略文件、無 RTO/RPO、無定期還原測試**。forward-only 無回滾更放大此缺口 |
| D-02 | **多庫手動套用一致性** | ⚠️ 部分實施（風險）| 品牌庫（×N，一品牌一庫）+ 技師庫 + 平台庫**手動套用擴散**；一致性靠人工 + `split-tech-db.sh --verify`；無自動 drift 比對 CI；漏套某庫某 migration 難察覺 |
| D-02b | `TECH_POSTGRES_URI` 漏設靜默退化 | ⚠️ 部分實施（風險）| 未設時靜默 fallback 回主連線，技師庫雙寫失效退回單庫（`00_platform/P2/09 §6 R-05`）；無啟動守衛 |
| D-03 | DB 存取控制 | ⚠️ 部分實施 | migration DDL 需高權限帳戶；`[待確認]` 是否分離 app 帳戶（最小權限）與 migration 帳戶（DDL）|
| D-04 | Cloud SQL 連線加密 | ✅ 已實施 | prod 套用經 cloud-sql-proxy（加密通道）|
| D-05 | pipeline 執行環境 | N/A | 離線批次，本機/CI 執行；不對外開 port |
| D-06 | Migration CI 整合 | ❌ 未實施 | `[待確認]` 無 CI 在部署前自動套 migration + 驗 `schema_migrations` drift |
| D-07 | 原始資產保存 | ⚠️ 部分實施 | raw 層近空殼（各源 1-2 檔）；`[待確認]` 原始影片/CSV 是否留存，若不在 repo 則 bronze 無法從頭重建（見 P1/05 R-07）|

---

## E. 合規

| # | 項目 | 狀態 | 說明 / 風險 |
|---|---|---|---|
| E-01 | GDPR 硬刪能力 | ⚠️ 部分實施 | `saas.forget_request`(021) 提供兩階段刪除（soft→hard，30d cooldown）；`saas.*` 治理表（config_audit/kb_audit_log/ai_decision_trace）支援審計；但 pipeline 端 bronze/silver 內若含 PII（LINE CSV），刪除範圍 `[待確認]` 是否涵蓋檔案系統 |
| E-02 | 資料分類政策 | ⚠️ 部分實施 | `SQL/seeds/README.md` 明令 PII 禁入 seed；但無正式資料分類文件涵蓋 bronze/silver 內容分級 |
| E-03 | 知識來源授權合規 | ⚠️ 部分實施 | YouTube/website 內容爬取；`[待確認]` 品牌官方影片/網站內容再利用的授權範圍（bronze-only + 只引 URL 部分緩解）|
| E-04 | 變更管理程序 | ✅ 已實施 | migration 走 CR 編號（CR-NNNN）+ registry 認領；schema 變更觸發 CIA gate（`.claude/rules/change-governance.md`）|
| E-05 | AI 治理審計 | ✅ 已實施 | `saas.ai_decision_trace`(022) 提供 PRD source / charter_rule / owner_decision_ref 三軸 traceability（但服務 agent runtime，非 pipeline）|

---

## F. 審查結論

### F.1 整體評估

> **pipeline（`data/`）：功能性退役狀態，非安全阻斷。**
> `data/` 的產出鏈已斷（寫入死目錄），這在安全上是「安全的失敗」（不會覆寫現行 references），但功能上是自動化完全失效。**首要風險非安全漏洞，而是文件誤導**：後人照 `data/README.md` 操作會失敗。
>
> **schema（`SQL/`）：可運作，但生產健壯性有缺口。**
> 核心安全控制（bronze-only sourcing、LLM 幻覺防護、三庫物理隔離、secret 管理、migration idempotent）**已實施**。主要缺口在**基礎設施層**：無備份/還原文件（D-01）、多庫手動套用一致性（D-02）、forward-only 無回滾（C-03）、`ON_ERROR_STOP=0` 容錯淹沒真錯（C-04）。

### F.2 具體行動項

| 行動項 ID | 優先級 | 描述 | 驗收條件 |
|---|---|---|---|
| DA-01 | P0 | **標記 pipeline 文件 superseded 或修復產出鏈**：`data/README.md`/`架構書.md` 加 `status: superseded`（方案 B），或修 `config.toml` 產出目標對齊 references（方案 A）| 跑 `silver_to_skill` 不再寫死目錄，或文件明載退役（P1/05 §9）|
| DA-02 | P1 | **建立備份/還原策略文件 + RTO/RPO**：三庫（品牌×N/技師/平台）備份策略；定期還原測試記錄；forward-only 補救 runbook | 有備份 SOP + 至少一次還原演練記錄 |
| DA-03 | P1 | **Migration drift CI**：CI 自動比對 `MIGRATION_REGISTRY.md` vs 各環境 `schema_migrations`；套用時真 ERROR 阻斷（改善 `ON_ERROR_STOP` 判讀）| drift 出現時 CI 失敗；真 ERROR 不被 benign 淹沒 |
| DA-04 | P1 | **三庫 URI 啟動守衛**：部署啟動時斷言 `POSTGRES_URI`/`TECH_POSTGRES_URI`/`PLATFORM_POSTGRES_URI` 完整可達，禁止靜默 fallback | 漏設 `TECH_POSTGRES_URI` 時啟動失敗而非靜默退化 |
| DA-05 | P2 | **Bronze/Silver PII 評估**：評估 LINE CSV / 對話內容 PII，決定去識別或納入 `forget_request` 刪除範圍 | PII 處理策略文件；GDPR 硬刪涵蓋檔案系統 |
| DA-06 | P2 | **DB 帳戶最小權限分離**：分離 app 帳戶（DML）與 migration 帳戶（DDL），移除 superuser 日常連線 | app 帳戶無法 `DROP TABLE`（測試驗證）|
| DA-07 | P2 | **pipeline 依賴 CVE 掃描**：CI 加 `pip-audit`（`uv`）掃 yt-dlp/whisper/playwright 等依賴 | 高危 CVE 阻斷 CI |

### F.3 上線前必要條件摘要

- [ ] DA-01 完成（pipeline 文件不再誤導）
- [ ] DA-02 完成（備份/還原文件 + 至少一次還原演練）
- [ ] DA-03 完成（migration drift CI）
- [ ] DA-04 完成（三庫 URI 啟動守衛）
- [ ] B-01/B-02（bronze-only + 幻覺防護）持續複查

---

## G. 生產準備檢查清單

| # | 項目 | 狀態 | 備註 |
|---|---|---|---|
| G-01 | pipeline 可重跑（冪等）| ⚠️ 部分實施 | bronze→silver 有冪等檢查；silver→skill 產出目標死目錄（不可完成）|
| G-02 | Migration idempotent | ✅ 已實施 | `IF NOT EXISTS` / `pg_constraint` 查存在 |
| G-03 | 套用真相可查 | ⚠️ 部分實施 | `schema_migrations` 為真相，但 046 前歷史不可考、registry 漂移 |
| G-04 | 回滾計畫 | ❌ 未實施 | forward-only 無 down migration；靠手動備份（未文件化）|
| G-05 | 備份驗證 | ❌ 未實施 | 無定期還原測試記錄（D-01）|
| G-06 | 多庫套用一致性 | ⚠️ 部分實施 | 手動套用 + `--verify`，無自動 drift CI（D-02）|
| G-07 | Secret 管理 | ✅ 已實施 | `.env`/Secret Manager，不入 toml；`POSTGRES_URI` 禁手動構建 |
| G-08 | 知識來源可信度 | ✅ 已實施 | bronze-only + PDF 只引 URL + Python 覆寫 provenance |
| G-09 | 產出鏈完整性 | ❌ 未實施 | silver→skill 斷開；自動化知識更新失效（P0 行動 DA-01）|
| G-10 | 依賴 CVE 掃描 | ❌ 未實施 | 無 `pip-audit` CI（DA-07）|
| G-11 | 原始資產可重建 | ⚠️ `[待確認]` | raw 近空殼；原始影片/CSV 留存未明 |
| G-12 | 文件時效性 | ❌ 未實施 | `data/` README/架構書描述 superseded 舊架構，未標 status（DA-01）|

---

*文件結尾 — data-pipeline / P3 / 13_security_checklist.md v1.0 / 2026-07-07*
