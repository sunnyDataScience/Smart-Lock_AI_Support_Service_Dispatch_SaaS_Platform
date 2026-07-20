---
title: LINE 推播 Hardening 批次 — 生產部署 Release Checklist
date: 2026-07-20
status: active
scope: CR-0175 / CR-0172 / CR-0174 / CR-0173 + R24 env 前置
audience: 部署執行者（業主 / SRE）
source: codegraph 稽核 workflow（10 agent：5 萃取 + 5 對 code 稽核驗證，wf_79ce9f00-106）
related:
  - docs/4-exploration/CR-0175-line-push-outbox-idempotency.md
  - docs/4-exploration/CR-0172-tech-dispatch-push-outbox.md
  - docs/4-exploration/CR-0174-line-uid-tenant-resolution.md
  - docs/4-exploration/CR-0173-tech-line-uid-encryption.md
  - docs/uat/redeploy-sop-20260716.md
  - docs/uat/cloud-deploy-report-20260719.md
---

# LINE 推播 Hardening 批次 — 生產部署 Release Checklist

> 本批次 = dev-ding 上 14 個待 push commit（含 4 個 CR + R24 系列修正）。
> **每個步驟的行號/env 名/檔名都已對照實際 code 稽核過**（非記憶）。逐項打勾執行。

---

## 0. 一頁摘要

| CR | 一句話 | 動到的服務 | 動到的庫 | Schema? | Flag? | 新 Secret? |
|---|---|---|---|---|---|---|
| **CR-0175** | 客戶推播 outbox 冪等（enqueue 去重 + `x_line_retry_key`） | brand/dispatch-api | 品牌/派工庫（本機 5433 / prod `lock-ai-db`） | migration 111 | — | — |
| **CR-0172** | 技師派工推播改走 outbox（送達保證） | brand/dispatch-api（+ tech-api 收端） | 同上（既有表加 `push_kind` 值，無 DDL） | 無 | `TECH_DISPATCH_VIA_OUTBOX`（**維持關**） | — |
| **CR-0174** | 反解 `line_uid` 補 tenant scope、fail-closed 防跨租戶洩漏 | brand/dispatch-api | 同上（純 code） | 無 | — | — |
| **CR-0173** | 技師 `line_user_id` 欄位級加密（Fernet + blind index） | tech-api | 技師權威庫（本機 5434 / prod `lock_tech`） | `Schema_line_notify.sql` +2 欄 +1 索引 | — | **`LINE_UID_ENC_KEY` / `LINE_UID_BIDX_KEY`** |
| **R24 系列** | webhook 驗簽 fail-closed + secret strip + 缺 env 告警 | tech-api（+ 客戶側 api） | 無 | 無 | `ALLOW_UNSIGNED_LINE_WEBHOOK`（**必須不設**） | 確認既有 + 補 `LINE_CHANNEL_SECRET` |

**服務拓樸**：雲端為 `lock-tech-api`（`API_SURFACE=tech`）與 brand/dispatch-api（`API_SURFACE=all` 或 `dispatch`）兩個 Cloud Run。outbox worker 只在 all/dispatch 面啟動。

**兩庫別搞混**（最常見致命雷）：
- **品牌/派工庫**（`POSTGRES_URI`）：本機埠 **5433** / db `lock_AI_data`；prod `lock-ai-db` → migration 111、107/108/109、CR-0174 盤點
- **技師權威庫**（`TECH_POSTGRES_URI`）：本機埠 **5434** / db `lock_tech`；prod `lock_tech` database → `Schema_line_notify.sql`、CR-0173 backfill

---

## 1. ⚠️ 部署前必改 `scripts/deploy/api.sh`（稽核發現的真 gap）

稽核逐行讀 `api.sh` 確認：**以下 4 個 env / secret 目前腳本沒掛**，漏掉不會 fail-fast，只會靜默降級。手動 `gcloud run set-env` 掛的話，**下次 `api.sh` 重佈會用 `--set-secrets`/`--set-env-vars` 全量覆蓋洗掉**（同 0719 C-4/C-5 同源雷）。**先補進腳本再部署**：

- [ ] **tech 面 SECRETS 追加兩把加密金鑰**（在 `api.sh:93-96` 的 `if [[ "${API_SURFACE}" == "tech" ]]` 區塊內）：
  ```sh
  SECRETS="${SECRETS},LINE_UID_ENC_KEY=LINE_UID_ENC_KEY:latest,LINE_UID_BIDX_KEY=LINE_UID_BIDX_KEY:latest"
  ```
- [ ] **tech 面補 `TECH_PORTAL_URL`**（env-var，非 secret）：未設時 `tech_portal_base()`（`technician_line_service.py:88`）退 `http://localhost:3001`，派單/池單推播的深連結會推 localhost 給技師 → 打不開（fail-soft 不阻斷）。
- [ ] **all 面補 `LINE_CHANNEL_SECRET`**（客戶側 OA webhook 驗簽）：`api.sh:79` 目前只掛 `LINE_CHANNEL_ACCESS_TOKEN`、**未掛** `LINE_CHANNEL_SECRET`。缺了客戶 webhook（`/api/v1/line/webhook`）fail-closed **全 401**（`line_webhook.py:233`）。
- [ ] **`PLATFORM_LINE_*` 補進 pre-flight `required_secrets`**（`api.sh:174-182`）：目前預檢清單沒有它們，只靠 `--set-secrets` 部署步驟硬失敗把關，不會提前 warn。

> 這 4 項本身可另開一個 `chore(deploy)` 收斂為腳本管控（見 §7 follow-up）。本次至少手動確保部署當下 env 到位。

---

## 2. Secret Manager 前置

建 secret 一律 `printf %s "$VALUE" | gcloud secrets create ...`（**不帶尾換行**——aiohttp 嚴格模式拒發帶 `\n` 的 header，0719 C-5 踩過；code 已多處 `.strip()` 防護但建 secret 端仍要乾淨）。

**新建（本批次新增）：**
- [ ] `LINE_UID_ENC_KEY`（CR-0173 Fernet 金鑰）：`python -c "import secrets;print(secrets.token_urlsafe(48))" | gcloud secrets create LINE_UID_ENC_KEY --data-file=-`
- [ ] `LINE_UID_BIDX_KEY`（CR-0173 blind index 金鑰，**必須與 ENC_KEY 不同值**）：同法建立
- [ ] 授權 tech-api runtime SA 讀這兩把（比照 `api.sh:189-191` API_JWT 授權範本）：
  ```sh
  gcloud secrets add-iam-policy-binding LINE_UID_ENC_KEY  --member=serviceAccount:<tech-api-SA> --role=roles/secretmanager.secretAccessor
  gcloud secrets add-iam-policy-binding LINE_UID_BIDX_KEY --member=serviceAccount:<tech-api-SA> --role=roles/secretmanager.secretAccessor
  ```
- [ ] **兩把金鑰值離線妥存（密碼保管庫），標註「永不輪換/遺失」** — code 無金鑰版本前綴（CR-0173 §9 S5 未做），金鑰一變/遺失，所有既有 `line_user_id_enc` 密文永久解不開、bidx 全對不上（換綁去重失效）。
- [ ] `LINE_CHANNEL_SECRET`（客戶側 OA channel secret，`api.sh` 未掛需補建）

**確認既有（本批次依賴，缺了會壞）：**
- [ ] `PLATFORM_LINE_CHANNEL_SECRET`（技師側 webhook 驗簽，R24 fail-closed；缺 → tech-api webhook 對所有請求 **403**、技師綁定全斷）
- [ ] `PLATFORM_LINE_CHANNEL_ACCESS_TOKEN`（技師側推播/回覆；缺 → fail-soft no-op，綁定寫入成功但師傅收不到「✅ 綁定完成」、派單不發）
- [ ] `INTERNAL_API_TOKEN`（brand-api ↔ tech-api service-to-service；brand 與 tech **兩面同值**，否則收端 `require_internal_token` 回 401/403）
- [ ] `LINE_CHANNEL_ACCESS_TOKEN`（客戶側推播，`api.sh:79` 已掛）

> ⚠️ 客戶側 `LINE_CHANNEL_*` 與技師側 `PLATFORM_LINE_CHANNEL_*` 是**兩個不同 channel、兩把不同 token**，混用會推錯官方號 / 驗簽失敗。

---

## 3. 主部署順序（合併 5 個 CR 的交錯依賴 → 一條序列）

> 鐵律：**schema 先於 code；tech-api 先於 brand-api；金鑰先於任何真實綁定；backfill 最後。**

### Phase A — Schema（先於 code）

- [ ] **A0 備份**：`gcloud sql backups create --instance=lock-ai`（`apply-schema-prod.sh` 檔頭硬性要求）
- [ ] **A1 起 proxy**：`cloud-sql-proxy <實例> --gcloud-auth --port 5432`（prod ADC 常 `invalid_rapt` → 先 `gcloud auth application-default login`，或直接 `--gcloud-auth`；`proxy-up.sh` 不吃 `--gcloud-auth` 會 exit 1，故 prod 建議手動跑）。直連被擋 → 把下列 SQL 打包交業主 `!` 執行。

- [ ] **A2 品牌/派工庫（`lock-ai-db`）前置盤點 gate**（全唯讀，非 0 就停）：
  ```sql
  -- CR-0175: strict 4 kind 存量重複（migration 會靜默刪，先知道會刪幾筆）
  SELECT reference_id, push_kind, COUNT(*) FROM line_push_outbox
   WHERE reference_id IS NOT NULL AND status <> 'dead'
     AND push_kind IN ('work_order_assigned','work_order_accepted','work_order_document','scope_change_result')
   GROUP BY reference_id, push_kind HAVING COUNT(*) > 1;              -- 期望 0 列

  -- CR-0174 核心零回歸閘：跨租戶重複 uid（>0 = 部署唯一真正阻擋點）
  SELECT line_user_id, COUNT(DISTINCT tenant_id) t, COUNT(*) n FROM users
   WHERE line_user_id IS NOT NULL GROUP BY line_user_id
   HAVING COUNT(DISTINCT tenant_id) > 1;                             -- 必須 0 列

  -- CR-0174：同租戶重複 uid（觸發新增的 fail-closed 拒答）
  SELECT tenant_id, line_user_id, COUNT(*) FROM users
   WHERE line_user_id IS NOT NULL GROUP BY tenant_id, line_user_id
   HAVING COUNT(*) > 1;                                              -- 必須 0 列

  -- CR-0174 前置存在性：users.tenant_id 欄 + saas.line_binding 表
  SELECT column_name FROM information_schema.columns
   WHERE table_schema='public' AND table_name='users' AND column_name='tenant_id';  -- 1 列
  SELECT to_regclass('saas.line_binding');                          -- 非 NULL
  ```
  > 若跨租戶重複 uid > 0：這些客戶「查進度」行為會變（舊碼 `LIMIT 1` 誤解析、新碼對非該租戶回「尚未綁定」）→ 需 release note 告知，不可略過盤點直接部署。

- [ ] **A3 套 migration 111**（品牌/派工庫 only，**別套技師庫**）：
  ```sh
  psql "$POSTGRES_URI" -f SQL/migrations/111-line-push-outbox-idempotency.sql
  ```
  內容：`BEGIN` → DELETE 存量重複（保留最大 `(created_at,id)`）→ `CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_ref_kind_strict`（partial，4 strict kind）→ `COMMIT`。冪等可重跑。
  > 單獨 `psql` **不會登錄 `public.schema_migrations`**（漂移追蹤缺 v111 一筆）；走 `scripts/db/apply-schema-prod.sh` 才會自動登錄。

- [ ] **A4 套同輪待套 migration**（品牌/派工庫，皆 `ADD COLUMN IF NOT EXISTS` forward-only）：`107-reconciliation-reject.sql`、`108-intake-case-links.sql`、`109-payout-rule-crud.sql`

- [ ] **A5 套技師權威庫 schema（`lock_tech`，CR-0173）**：
  ```sh
  psql -d lock_tech -f SQL/tech_authority/Schema_line_notify.sql   # prod 經 proxy
  # 本機： docker exec -i lock-tech-tech-db-1 psql -U lock -d lock_tech < SQL/tech_authority/Schema_line_notify.sql
  ```
  加 `line_user_id_enc TEXT` + `line_user_id_bidx CHAR(64)` + partial index `idx_technicians_line_bidx`。純 additive、冪等、**不 DROP 明文欄**（過渡期 dual-read 保留）。

### Phase B — Code 部署（tech-api 先於 brand-api）

- [ ] **B1 先部署 tech-api**（`API_SURFACE=tech`）：`./scripts/deploy/api.sh`（帶 §1 改好的 secrets）
  - 讓 tech-api Cloud Run URL 先存在（brand-api 才解析得到 `TECH_API_BASE_URL`）
  - 掛上 `LINE_UID_ENC_KEY`/`LINE_UID_BIDX_KEY`（CR-0173 讀寫 enc）、`PLATFORM_LINE_*`（R24 fail-closed 驗簽 + 推播）、`TECH_PORTAL_URL`
- [ ] **B2 再部署 brand/dispatch-api**（`API_SURFACE=all` 或 `dispatch`）：`./scripts/deploy/api.sh`
  - CR-0175 enqueue 去重 + worker `x_line_retry_key`；CR-0172 worker tech-dispatch 分支；CR-0174 tenant fail-closed
  - `api.sh` 自動 `gcloud run services describe lock-tech-api` 解析 `TECH_API_BASE_URL`（服務名非預設先 `export TECH_API_SERVICE_NAME=<實際名>`，否則只印 WARN、推播 no-op）

> **CR-0175 schema-first 硬約束**：新 enqueue 走 `ON CONFLICT (reference_id, push_kind) WHERE <predicate>`，Postgres 需先有 `uq_outbox_ref_kind_strict` 當 arbiter；index 不在 → `InvalidColumnReference (42P10)`，strict-kind enqueue 全 500。A3 必須先於 B2。
>
> **CR-0173 金鑰-first 硬約束**：金鑰須在 tech-api code 部署前就位；否則走具名 dev-fallback 假金鑰，該窗口綁定用假金鑰加密，日後設真金鑰即永久解不開（decrypt fail-soft 回 None → 推播靜默跳過）。

### Phase C — Backfill（code 之後，非阻斷）

- [ ] **C1 CR-0173 技師存量明文加密**（0719 UAT 已建技師綁定 → 技師庫恐有存量明文列）：
  ```sh
  # 金鑰須與 tech-api runtime 同一組
  TECH_POSTGRES_URI=... LINE_UID_ENC_KEY=... LINE_UID_BIDX_KEY=... \
    python scripts/backfill_tech_line_uid_encryption.py --dry-run     # 先看「待回填 N 列」唯讀
  # 確認後拿掉 --dry-run 實跑（就地加密 + 清空明文欄）
  ```
  > 過渡期 dual-read（enc 優先、legacy 明文回退）撐著，backfill 不阻斷推播；但為 PII-at-rest 合規應跑。全新乾淨庫可略。

### Phase D — Flag（本次維持現況，灰度）

- [ ] **`TECH_DISPATCH_VIA_OUTBOX` 維持不設**（= 走舊同步 `_notify_tech_line`，行為與部署前一致，零副作用灰度）。**啟用另擇時**：設字面 `'1'`（`true/yes` 無效！）並跑一次「派工→outbox sent→技師 LINE 實收」雲端親驗。啟用前提：本 CR image 已上線（worker 有 tech-dispatch 分支），否則 row 入庫但 worker 查不到 line_uid → dead。
- [ ] **確認 `ALLOW_UNSIGNED_LINE_WEBHOOK` 未設**（設 `'1'` = 客戶 webhook 放行未簽章請求 = 裸端點，prod 絕不可開）。

---

## 4. 部署後驗證清單

### 服務 / 連線
- [ ] `api.sh` 末段 `${SERVICE_URL}/health` health check 綠燈（非 webhook 誤報路徑）；確認 running image 含本批次 commit（避免舊 image 假驗證）
- [ ] tech-api 啟動 log **不得**出現 `LINE_UID_ENC_KEY 未設 → dev fallback` / `LINE_UID_BIDX_KEY 未設`（出現 = 金鑰沒注入、正走假金鑰）

### CR-0175 outbox 冪等（品牌/派工庫）
- [ ] `SELECT indexname FROM pg_indexes WHERE indexname='uq_outbox_ref_kind_strict';` → 回 1 列
- [ ] 重跑 A2 strict 盤點 SQL → 0 列
- [ ] 觀察 4 個 strict kind 的 enqueue 無 `InvalidColumnReference`/無 500；重複 enqueue 時 api log 見「outbox enqueue 冪等命中既有」
- [ ] LINE 推播仍見「outbox push ok」、`push_message` 無 `TypeError`（證部署 image 的 line-bot-sdk 支援 `x_line_retry_key`；pin `>=3.0`，本機解析 3.23.0）

### CR-0172 技師派工 outbox（flag 關 = 基線）
- [ ] flag 關：派一張工單 → 已綁定技師數秒內收 LINE；log 見舊同步 `_notify_tech_line`；`line_push_outbox` **不應**出現 `tech_dispatch_assigned` row
- [ ] （若日後開 flag 再驗）`SELECT push_kind,status,attempts,last_error FROM line_push_outbox WHERE push_kind='tech_dispatch_assigned' ORDER BY created_at DESC LIMIT 5;` → status `pending`→`sent`

### CR-0174 跨租戶洩漏封死（品牌/派工庫）
- [ ] 取樣 `SELECT id,tenant_id,line_user_id FROM users WHERE line_user_id IS NOT NULL LIMIT 1;`
- [ ] 對的 tenant 仍查得到：`... WHERE line_user_id='<uid>' AND tenant_id='<correct>'::uuid;` → 1 列
- [ ] 別的 tenant 封死：`... WHERE line_user_id='<uid>' AND tenant_id='<other>'::uuid;` → 0 列（對照不帶 tenant 的舊查詢會撈到 = 修復生效）
- [ ] 端到端：已綁定 LINE 帳號點 rich menu「查進度」→ default 租戶客戶仍正確回追蹤連結
- [ ] app log **不應**出現 `resolve_user_by_line_uid: 同租戶多筆 users 撞同 line_uid → fail-closed 拒答`（Q4=0 的必然）

### CR-0173 技師加密 + R24（技師庫 / webhook）
- [ ] `\d technicians` 含 `line_user_id_enc` / `line_user_id_bidx` + `idx_technicians_line_bidx`
- [ ] backfill 後：`SELECT count(*) FROM technicians WHERE line_user_id IS NOT NULL;` → 0；`... WHERE line_user_id_enc IS NOT NULL;` → = 已綁定技師數
- [ ] `curl` tech-api webhook 帶錯 `X-Line-Signature` → **403**（技師側）；客戶側 `/api/v1/line/webhook` 無簽名 → **401**
- [ ] 端到端綁定：師傅站產 6 位碼 → LINE 傳碼 → 收「✅ 綁定完成」；SQL 驗 `line_user_id_enc` 有密文、明文欄 NULL
- [ ] 端到端派單：品牌後台派單 → 技師 LINE 即時收到；log **不得**有 `line_user_id 密文解密失敗`（= 金鑰不匹配訊號）、`tech LINE notify 未配置`；深連結非 localhost（`TECH_PORTAL_URL` 已設）

---

## 5. 回滾速查

| CR | 回滾方式 | 注意 |
|---|---|---|
| **CR-0172** | 最快：`TECH_DISPATCH_VIA_OUTBOX` 設 `'0'`/移除 → 下次 dispatch 即回舊同步。新 push_kind 值 additive，殘留 row 無害可留 | 不需重 build |
| **CR-0175** | 先 revert code 再 `DROP INDEX uq_outbox_ref_kind_strict`（順序：code 先於 drop index，否則 ON CONFLICT 找不到 arbiter 報錯） | migration 已刪的重複列不可逆（乾淨庫 DELETE=0 無損） |
| **CR-0174** | 純 code：revert commit `4f73793b` 重部署，或切回前一 revision | 回退 = 重新打開跨租戶洩漏，僅功能異常時暫用 |
| **CR-0173** | 無旗標（加密恆開）：revert tech 面 code。schema additive 留著即可 | **backfill 跑後 / 新綁定產生後不可乾淨回退**（明文已 NULL，舊 code 讀不到）；遇 decrypt 異常正解是「修金鑰」非 revert；**嚴禁輪換/刪金鑰**（既有密文全變孤兒） |
| **R24** | 無 code 回退標的；fail-closed 誤擋 = 補正確 `PLATFORM_LINE_CHANNEL_SECRET`（技師側無 bypass flag）；客戶側緊急可暫設 `ALLOW_UNSIGNED_LINE_WEBHOOK=1`（安全降級，修好即移除） | — |

---

## 6. 最容易踩的雷（Top 8）

1. **兩把 CR-0173 金鑰要在真實綁定前就位** — dev-fallback 是**具名固定假金鑰**，沒設時「看起來能用」會遮蔽誤配；先用假金鑰綁/回填、之後設真金鑰 → 舊密文永久解不開且 fail-soft 靜默。
2. **`TECH_DISPATCH_VIA_OUTBOX` 只認字面 `'1'`** — `true/TRUE/yes/on` 全被判為「關」靜默留舊路徑。
3. **別套錯庫** — migration 111 + 107/108/109 → 品牌/派工庫（5433）；`Schema_line_notify.sql` + backfill → 技師庫（5434/`lock_tech`）。backfill 誤指 5433 UAT 庫會污染 seed。
4. **CR-0175 predicate 必須逐字對齊** — `_DEDUP_INDEX_PREDICATE`（`line_push_outbox_service.py:67-72`）與 migration index 的 `WHERE` 完全一致，否則 ON CONFLICT 無法推斷 arbiter，每次 strict enqueue 500。
5. **tech-api 必須先於 brand-api 部署** — 否則 `api.sh` 解析不到 `TECH_API_BASE_URL`，技師派單推播雲上靜默不發。
6. **secret 尾端換行** — `printf %s` 建立；aiohttp 拒發帶 `\n` 的 header。
7. **手動 `set-env` 會被下次 `api.sh` 重佈洗掉** — 4 個未掛 env（§1）務必補進腳本，別靠 Console 手動掛。
8. **prod 直連常 `invalid_rapt`** — `cloud-sql-proxy --gcloud-auth`，或打包 SQL 交業主 `!` 執行；**UAT 期間別對 5433 跑全套 pytest**（單庫 fallback 洩測試資料、破壞 seed）。

---

## 7. Follow-up backlog（本次不做，各 CR §11 已 defer，另開 CR）

- **api.sh 收斂**：`LINE_UID_ENC_KEY`/`LINE_UID_BIDX_KEY`/`TECH_PORTAL_URL`/`LINE_CHANNEL_SECRET` 補進腳本 `--set-secrets`/`--set-env-vars` 管控；`PLATFORM_LINE_*` 補進 `required_secrets` 預檢。（`chore(deploy)`）
- **啟動 fail-fast 告警**：technician webhook fail-closed 路徑（`technician_line.py:106`）與 no-op 推播分支補 `logger.error`；app 啟動對 4 個關鍵 env 做 preflight。（R1/R8）
- **CR-0175**：真 DB 整合測試（雙 enqueue 只落一筆 / crash-replay 不重送）補跑。
- **CR-0172**：S4 池單（notify-pool）納入 outbox（N-fan-out）；S5 技師派工冪等去重（需 `(reference_id,push_kind,technician_id)` 唯一索引 migration）；S6 flag 全開穩定後移除舊直推呼叫點。
- **CR-0174**：S3 移除 users fallback（前提先做 legacy 回填 `record_auto_binding`）；S4 刪 `LINE_DEFAULT_TENANT_ID` env + 灰度常數。HD-1 記錄：客戶/品牌為單一共用官方帳號、webhook 無 destination，per-tenant 官方帳號需另開 CR。
- **CR-0173**：穩定後另開 CR `DROP` 明文欄 `technicians.line_user_id` + 收斂 dual-read；HD-F 客戶側 `saas.line_binding` 欄位級加密（複用同一 `core/line_uid_crypto`）；金鑰輪換機制（§9 S5）+ 重加密 runbook；`technician_line_service.py` 檔頭 `HD-4=a 明文` 註解更新 + 新 ADR（推翻 HD-4=a）。
- **文件更正**：`docs/uat/external-readiness-runbook-20260718.md:25` 技師 webhook URL 過時（`/api/v1/line/binding-webhook` → 實際 `/api/v1/technicians/line-webhook`）。

---

_產出：codegraph 稽核 workflow（10 agent，每項對照 code 行號驗證）。逐項行號如 `api.sh:93-96`、`technician_line.py:105` 均為稽核當下實際位置，動 code 後以 code 為準。_
