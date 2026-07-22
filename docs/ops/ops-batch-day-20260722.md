# OPS 批次日 Runbook — 2026-07-22（業主裁決「今天做」）

> **目標**：一個下午清完全部一次性雲端配置——之後「部署殘項」這個類別從每輪清單永久消失。
> **雲端現況基準**：0719 部署（七服務、migration 水位 110）；0720 起所有 code 變更（CR-0172~0177、
> CR-0176 全系列、migration 111-114）**均未上雲**。
> **執行方式**：逐 Step 用 `!` 執行區塊指令；每 Step 結尾有驗證，綠了才進下一步。
> **總鐵律**（沿 0720 checklist）：**schema 先於 code；tech-api 先於 brand-api；金鑰先於任何真實綁定；backfill 最後。**

---

## Step 0 — 前置（2 分鐘）

```bash
gcloud auth login   # 若已登入可跳過
gcloud config set project cedar-scope-489604-g3
git -C ~/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform pull   # 確認在最新 dev-ding
```

## Step 1 — Secrets（5 把新金鑰＋授權，冪等）

```bash
./scripts/ops/opsday-20260722-1-secrets.sh
```

- 建：`GDPR_DEK_KEK`／`USER_PII_BIDX_KEY`／`MEDIA_ENC_KEY`／`LINE_UID_ENC_KEY`／`LINE_UID_BIDX_KEY`（隨機 hex64，已存在跳過絕不覆蓋）
- 驗：既有 9 把（含 `LINE_CHANNEL_SECRET`，agent 已在用）齊備
- ⚠️ 出現 MISSING 先補齊再往下（那些值來自憑證非隨機）

## Step 2 — DB（備份 → 品牌庫套 111-114 → 技師庫 Schema_line_notify）

```bash
# 2a. 備份（必做）
gcloud sql backups create --instance=lock-ai

# 2b. 起 proxy（prod ADC 常 invalid_rapt → 直接 --gcloud-auth；另開終端跑）
cloud-sql-proxy cedar-scope-489604-g3:asia-east1:lock-ai --gcloud-auth --port 5432
```

```bash
# 2c. 【前置盤點 gate】0720 checklist §A2 的 strict 重複盤點（非 0 先停，回報我）
export POSTGRES_URI="postgresql://lock-ai:<DB_PASSWORD>@127.0.0.1:5432/lock-ai-db"
psql "$POSTGRES_URI" -c "SELECT reference_id, push_kind, count(*) FROM line_push_outbox WHERE push_kind IN ('work_order_assigned','work_order_accepted','work_order_document','scope_change_result') AND reference_id IS NOT NULL AND status <> 'dead' GROUP BY 1,2 HAVING count(*) > 1;"

# 2d. 品牌庫全量冪等套用（涵蓋 111/112/113/114＋自動登錄 schema_migrations）
./scripts/db/apply-schema-prod.sh

# 2e. 技師庫：Schema_line_notify 新版（CR-0173 兩欄+索引；別套品牌庫）
export TECH_POSTGRES_URI="postgresql://lock-ai:<DB_PASSWORD>@127.0.0.1:5432/lock_tech"
psql "$TECH_POSTGRES_URI" -f SQL/tech_authority/Schema_line_notify.sql
```

**Step 2 驗證**（全過才進 Step 3）：

```bash
psql "$POSTGRES_URI" -c "SELECT to_regclass('saas.data_encryption_key'), to_regclass('saas.purge_audit');"   # 兩者非 NULL
psql "$POSTGRES_URI" -c "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name IN ('display_name_enc','email_enc','phone_enc','email_bidx','phone_bidx');"   # 5 列
psql "$POSTGRES_URI" -c "SELECT indexname FROM pg_indexes WHERE indexname IN ('idx_users_email_bidx','idx_users_phone_bidx','uq_outbox_ref_kind_strict');"   # 3 列
psql "$POSTGRES_URI" -c "SELECT version FROM public.schema_migrations WHERE version IN ('111','112','113','114') ORDER BY 1;"   # 4 列
psql "$TECH_POSTGRES_URI" -c "SELECT column_name FROM information_schema.columns WHERE table_name='technicians' AND column_name LIKE 'line_user_id_%';"   # enc+bidx 2 列
```

## Step 3 — CD WIF（一次性，之後 GitHub 按鈕即可部署）

```bash
gh auth status || gh auth login
./scripts/ops/opsday-20260722-3-wif.sh
```

煙囪測試：GitHub → Actions → **cloud-run-deploy** → Run workflow（service=`api`）→ 綠。

## Step 4 — 依序重佈（schema 已就緒，code 上場）

> 順序鐵律：**tech-api → brand-api → platform-api → agent → web 三站**。
> api.sh 本輪已把全部新 secrets 烤入（pre-flight 會自動驗存在性）。

```bash
# 4a. tech-api（先行：brand 的推播 internal 鏈依賴它）
API_SURFACE=tech SERVICE_NAME=lock-tech-api ./scripts/deploy/api.sh

# 4b. brand-api（all 面＋掛技師庫）
MOUNT_TECH_URI=1 ./scripts/deploy/api.sh

# 4c. platform-api
API_SURFACE=platform SERVICE_NAME=lock-platform-api ./scripts/deploy/api.sh

# 4d. agent（⚠️ 不帶 RAG_TENANT_ID——RAG 屬 cutover 輪，見 §排除）
./scripts/deploy/agent.sh

# 4e. web 三站（新 code：SSO 置頂版登入頁＋OTel/PII scrub，Casdoor env 未設=SSO 鈕不顯示，預期）
./scripts/deploy/web.sh
WEB_APP=tech-portal SERVICE_NAME=lock-tech-web ./scripts/deploy/web.sh
WEB_APP=platform-console SERVICE_NAME=lock-platform-web ./scripts/deploy/web.sh
```

每支腳本末段自帶 health check（agent 對 webhook 服務誤報 404 屬已知，看 STARTUP probe）。

## Step 5 — Backfill（金鑰與新 code 都就位後，最後做）

```bash
# 5a. 技師 line_user_id 加密回填（技師庫；先 dry-run 看筆數）
export LINE_UID_ENC_KEY=$(gcloud secrets versions access latest --secret=LINE_UID_ENC_KEY)
export LINE_UID_BIDX_KEY=$(gcloud secrets versions access latest --secret=LINE_UID_BIDX_KEY)
TECH_POSTGRES_URI="$TECH_POSTGRES_URI" python scripts/backfill_tech_line_uid_encryption.py --dry-run
TECH_POSTGRES_URI="$TECH_POSTGRES_URI" python scripts/backfill_tech_line_uid_encryption.py

# 5b. 品牌庫 users PII 加密+bidx 回填（不清明文；exit 3=KEK 不符立即停手回報）
export GDPR_DEK_KEK=$(gcloud secrets versions access latest --secret=GDPR_DEK_KEK)
export USER_PII_BIDX_KEY=$(gcloud secrets versions access latest --secret=USER_PII_BIDX_KEY)
POSTGRES_URI="$POSTGRES_URI" python scripts/backfill_user_pii_encryption.py --dry-run
POSTGRES_URI="$POSTGRES_URI" python scripts/backfill_user_pii_encryption.py

# 5c. 回填驗證
psql "$TECH_POSTGRES_URI" -c "SELECT count(*) FILTER (WHERE line_user_id IS NOT NULL) AS plain_left, count(*) FILTER (WHERE line_user_id_enc IS NOT NULL) AS enc_done FROM technicians;"   # plain_left=0
psql "$POSTGRES_URI" -c "SELECT count(*) FILTER (WHERE email IS NOT NULL AND email <> '' AND email_bidx IS NULL) AS bidx_missing FROM users WHERE display_name IS DISTINCT FROM '[REDACTED]';"   # 0
```

## Step 6 — 收尾驗證清單

| # | 動作 | 預期 |
|---|---|---|
| 1 | `curl -s -o /dev/null -w "%{http_code}" https://smart-lock-api-sjmxp23sqq-de.a.run.app/health`（tech/platform api 同式） | 200 |
| 2 | tech-api log：`gcloud run services logs read lock-tech-api --region=asia-east1 --limit=50` | 無「LINE_UID_ENC_KEY 未設 → dev fallback」 |
| 3 | 客戶側 webhook 無簽名：`curl -s -o /dev/null -w "%{http_code}" -X POST https://smart-lock-api-sjmxp23sqq-de.a.run.app/api/v1/line/webhook -d '{}'` | **401**（fail-closed 生效） |
| 4 | 技師側 webhook 錯簽名：`curl -s -o /dev/null -w "%{http_code}" -X POST https://lock-tech-api-sjmxp23sqq-de.a.run.app/api/v1/technicians/line-webhook -H "X-Line-Signature: bad" -d '{}'` | **403** |
| 5 | 三站首頁 200＋登入頁**只有密碼表單**（無 SSO 鈕） | 預期（Casdoor 未上雲） |
| 6 | 品牌後台登入→改客戶資料→再讀 | 正常（dual-write/read 生效無感） |
| 7 | LINE 問答一輪（客服 OA） | 正常回覆（agent 重佈無回歸） |
| 8 | 派單一筆→技師 LINE 數秒實收＋深連結非 localhost | 通（TECH_PORTAL_URL 生效） |
| 9 | deprecation metrics：admin token `curl -H "Authorization: Bearer $TOKEN" https://smart-lock-api-sjmxp23sqq-de.a.run.app/api/v1/admin/deprecation/v1-metrics` | JSON（**30 天零命中窗自今日起算**） |

## 今日明確排除（各有硬前置，非今日可完）

| 項 | 為什麼不是今天 | 歸屬 |
|---|---|---|
| **Casdoor 上雲＋prod tokenFormat** | prod 根本沒有 Casdoor 實體（R6 未上、23_Deployment_Guide 🔜）。上雲輪必做：pin 版本部署＋`tokenFormat=JWT-Custom`＋`tokenFields` **大寫 Go 名**白名單（CR-0177 §11 定案值）＋bootstrap 雷（`casdoor_bootstrap.py:151` 建新 app 仍寫 `JWT`）＋web.sh 補 `NEXT_PUBLIC_CASDOOR_*` build-args＋R2 prod 帳號映射重驗 | Casdoor 上雲輪 |
| **RAG 生產啟用** | agent image 缺 `mcp` 套件＋runtime 無 `uv`（config 靠 `uv run` 起 stdio server）——屬 build/code 變更，正式設計=rag sidecar+streamableHttp（僅存在於註解，無實作） | RAG cutover 輪 |
| **SigNoz 叢集** | 整套服務部署非配置；未部署前四站/api/agent 的 OTel 埋點全 no-op（無害） | 可觀測性部署輪 |
| **KYC_ENCRYPTION_KEY 輪替** | prod 既有 KYC 密文以 dev fallback 加密——直接換鑰=既有密文全滅，需先寫再加密腳本 | KYC 金鑰再加密輪 |

## 完成後效果

- 每輪部署不再有「手動 set-env 被洗掉」問題（全部烤入 api.sh＋pre-flight 驗證）
- CD 按鈕化：GitHub Actions 選服務即部署
- CR-0172~0177 全系列 hardening 正式在 prod 生效；v1 deprecation 30 天窗起算
- GDPR crypto-shred 端到端可用（DEK/密文/bidx 全鏈在 prod 落地）
