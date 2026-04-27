# GCP Cloud Run 部署手冊

本文件說明如何將 agent 部署到 GCP Cloud Run，連接 Cloud SQL 和 Secret Manager。

---

## 架構概覽

```
LINE Webhook
    ↓
Cloud Run (smart-lock-agent)
    ├── Vertex AI Gemini (LLM)
    ├── Cloud SQL PostgreSQL + pgvector (對話記憶 / 審計 / 用戶資料)
    └── Secret Manager (LINE tokens / DB 密碼)
```

---

## GCP 資源清單

| 資源 | 名稱 / 值 |
|------|-----------|
| 專案 ID | `cedar-scope-489604-g3` |
| Cloud Run 服務 | `smart-lock-agent` |
| Cloud Run URL | `https://smart-lock-agent-1083648618124.asia-east1.run.app` |
| Artifact Registry | `asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo` |
| Cloud SQL 連線名稱 | `cedar-scope-489604-g3:asia-east1:lock-ai` |
| Cloud SQL 公開 IP | `35.229.228.13` |
| 資料庫 / 使用者 | `lock-ai-db` / `lock-ai` |
| Secret Manager | `LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`、`DB_PASSWORD`、`POSTGRES_URI`、`OPIK_API_KEY`、`OPIK_WORKSPACE` |
| Service Account | `1083648618124-compute@developer.gserviceaccount.com` |

---

## 前置需求

### 0. gcloud CLI 登入與專案設定

```bash
# 登入有專案權限的 Google 帳號
gcloud auth login

# 設定預設專案
gcloud config set project cedar-scope-489604-g3
```

### 1. 操作者帳號 IAM 角色

執行部署的人（如 `sunny@funngo.ai`）需要以下角色，請由專案 Owner 授予：

| 角色 | 用途 |
|------|------|
| `roles/artifactregistry.admin` | 建立 repo、推送 image |
| `roles/run.admin` | 部署 Cloud Run 服務 |
| `roles/secretmanager.admin` | 建立和管理 secrets |
| `roles/iam.serviceAccountUser` | Cloud Run 使用 service account |
| `roles/resourcemanager.projectIamAdmin` | 設定 IAM policy（給 SA 加角色） |

```bash
DEPLOYER="user:sunny@funngo.ai"
for ROLE in roles/artifactregistry.admin roles/run.admin roles/secretmanager.admin \
            roles/iam.serviceAccountUser roles/resourcemanager.projectIamAdmin; do
  gcloud projects add-iam-policy-binding cedar-scope-489604-g3 \
    --member="$DEPLOYER" --role="$ROLE"
done
```

### 2. GCP API 啟用

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com
```

### 3. Service Account 角色（Cloud Run 執行身份）

Cloud Run 使用自訂 Service Account `lock-ai@cedar-scope-489604-g3.iam.gserviceaccount.com`，需要以下角色：

| 角色 | 用途 |
|------|------|
| `roles/cloudsql.client` | 透過 Auth Proxy 連 Cloud SQL |
| `roles/aiplatform.user` | 呼叫 Vertex AI (Gemini) API |
| `roles/storage.objectAdmin` | 多模態媒體存儲至 GCS（圖片/音訊/影片） |
| `roles/secretmanager.secretAccessor` | 讀取 Secret Manager 中的 secrets（建 secret 時逐一授予） |

```bash
SA="lock-ai@cedar-scope-489604-g3.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding cedar-scope-489604-g3 \
  --member="serviceAccount:$SA" --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding cedar-scope-489604-g3 \
  --member="serviceAccount:$SA" --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding cedar-scope-489604-g3 \
  --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
```

> 部署時需指定 `--service-account=$SA`，見下方部署指令。

### 4. 組織政策（Domain Restricted Sharing）

如果 GCP 組織啟用了 `iam.allowedPolicyMemberDomains` 約束，會導致無法設定 `allUsers` 公開存取（LINE webhook 需要無認證呼叫）。

**檢查目前狀態：**

```bash
gcloud resource-manager org-policies describe iam.allowedPolicyMemberDomains \
  --project=cedar-scope-489604-g3
```

**若被限制，請組織管理員對此專案豁免：**

在 GCP Console → Organization Policies → `iam.allowedPolicyMemberDomains` → 對 `cedar-scope-489604-g3` 設定 `allValues: ALLOW`。

---

## 部署流程

### Step 1：建立 Artifact Registry

```bash
gcloud artifacts repositories create lock-ai-repo \
  --repository-format=docker \
  --location=asia-east1 \
  --description="Smart Lock AI Agent"

gcloud auth configure-docker asia-east1-docker.pkg.dev --quiet
```

### Step 2：建立 Secret Manager Secrets

```bash
# LINE Channel Secret
echo -n "<your-channel-secret>" | \
  gcloud secrets create LINE_CHANNEL_SECRET --data-file=-

# LINE Channel Access Token
echo -n "<your-access-token>" | \
  gcloud secrets create LINE_CHANNEL_ACCESS_TOKEN --data-file=-

# DB Password（存原始密碼，不需要 URL encode）
echo -n "<your-db-password>" | \
  gcloud secrets create DB_PASSWORD --data-file=-

# OPIK API Key（LLM Observability）
echo -n "<your-opik-api-key>" | \
  gcloud secrets create OPIK_API_KEY --data-file=-

# OPIK Workspace
echo -n "<your-opik-workspace>" | \
  gcloud secrets create OPIK_WORKSPACE --data-file=-

# 授予 Cloud Run service account 存取權
SA="1083648618124-compute@developer.gserviceaccount.com"
for SECRET in LINE_CHANNEL_SECRET LINE_CHANNEL_ACCESS_TOKEN DB_PASSWORD POSTGRES_URI OPIK_API_KEY OPIK_WORKSPACE; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
done
```

### Step 2.5：建立 POSTGRES_URI Secret（自動 URL encode）

> **重要**：不要手動拼接 POSTGRES_URI。密碼中的特殊字元（`@`, `+`, `*`, `[`, `;` 等）需要 URL encode，手動處理極易出錯導致連線失敗。

```bash
# 從 DB_PASSWORD 自動拼接 POSTGRES_URI（Python URL encode + round-trip 驗證）
cd agent && ./scripts/deploy.sh --update-db-uri
```

腳本會自動：
1. 從 Secret Manager 讀取 `DB_PASSWORD`（原始密碼）
2. 用 Python `urllib.parse.quote()` URL encode
3. 拼接完整 URI：`postgresql://lock-ai:{encoded}@/lock-ai-db?host=/cloudsql/...`
4. Round-trip 驗證（encode → decode → 比對原始密碼）
5. 寫入 `POSTGRES_URI` secret

**更新密碼時**也用同樣流程：
```bash
# 更新 DB_PASSWORD
echo -n "<new-password>" | gcloud secrets versions add DB_PASSWORD --data-file=-

# 重建 POSTGRES_URI
cd agent && ./scripts/deploy.sh --update-db-uri
```

### Step 3 & 4：Build, Push & Deploy（一鍵完成）

> 推薦使用 `deploy.sh` 一鍵完成，包含 pre-flight 檢查、image 版本標記、health check 重試。

```bash
cd agent

# 完整部署（pre-flight → build → push → deploy → health check）
./scripts/deploy.sh

# 只 build image 不部署
./scripts/deploy.sh --build-only

# 只部署（用已存在的 latest image）
./scripts/deploy.sh --deploy-only
```

**deploy.sh 自動執行：**
1. **Pre-flight 檢查**：gcloud 登入、專案、Docker、5 個 secret 存在性、POSTGRES_URI 格式驗證
2. **Build & Push**：image 標記為 `{git-sha}-{timestamp}`（支援 rollback）+ latest
3. **Deploy**：Cloud Run 部署含 Cloud SQL Auth Proxy、Secret Manager、環境變數
4. **Health check**：6 次重試 x 10s，辨識 200（正常）/ 503（DB 降級）

**Image 版本管理**：每次 build 產生唯一 tag（如 `abc1234-20260427-0930`），同時更新 `:latest`。需要 rollback 時：

```bash
# 列出歷史 image
gcloud artifacts docker images list \
  asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent

# 部署指定版本
gcloud run deploy smart-lock-agent --region=asia-east1 \
  --image=asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:<tag>
```

> **冷啟動說明**：目前設定 `--min-instances=1`（常駐，約 $15-20/月）。
>
> ```bash
> # 關閉常駐（省錢，允許冷啟動約 5-10 秒）
> gcloud run services update smart-lock-agent --region=asia-east1 --min-instances=0
>
> # 開啟常駐
> gcloud run services update smart-lock-agent --region=asia-east1 --min-instances=1
> ```
>
> 不需要重新 build/push，update 即時生效。

> **POSTGRES_URI 注意**：不要手動拼接。請使用 `./scripts/deploy.sh --update-db-uri` 自動從 `DB_PASSWORD` 建立（含 URL encode + round-trip 驗證）。詳見 Step 2.5。

### Step 5：設定公開存取

```bash
# 允許所有流量進入
gcloud run services update smart-lock-agent \
  --region=asia-east1 --ingress=all

# 允許未認證呼叫（LINE webhook 需要）
gcloud run services add-iam-policy-binding smart-lock-agent \
  --region=asia-east1 \
  --member=allUsers \
  --role=roles/run.invoker
```

> 如果 `add-iam-policy-binding` 失敗並顯示 `FAILED_PRECONDITION`，代表組織政策尚未豁免，請參考前置需求第 4 點。

### Step 6：設定 LINE Webhook

到 [LINE Developers Console](https://developers.line.biz/) 更新 webhook URL：

```
https://smart-lock-agent-1083648618124.asia-east1.run.app/webhook
```

---

## 更新部署（程式碼修改後）

```bash
cd agent

# 一鍵完成（build + push + deploy + health check）
./scripts/deploy.sh
```

> 環境變數和 secrets 不需要重新設定，Cloud Run 會保留上次的設定。
> deploy.sh 會自動產生含 git SHA + 時間戳的 image tag，支援 rollback。

---

## 驗證

```bash
# 取得服務 URL
SERVICE_URL=$(gcloud run services describe smart-lock-agent \
  --region=asia-east1 --format='value(status.url)')

# Health check（200=正常，503=DB 降級）
curl "${SERVICE_URL}/health"
# 正常回應: {"status":"ok","version":"2.0-skills","checks":{"facts_db":"ok","audit_db":"ok"}}
# 降級回應: {"status":"degraded","version":"2.0-skills","checks":{"facts_db":"disconnected","audit_db":"ok"}}

# Chat 測試
curl "${SERVICE_URL}/chat?q=門打不開怎麼辦"

# Webhook 測試（應回 Invalid signature）
curl -X POST "${SERVICE_URL}/webhook" \
  -H "Content-Type: application/json" -d '{}'

# 即時日誌（串流，Ctrl+C 停止）
gcloud run services logs tail smart-lock-agent --region=asia-east1

# 歷史日誌（最近 N 筆）
gcloud run services logs read smart-lock-agent --region=asia-east1 --limit=100
```

---

## 查看日誌

```bash
# 即時日誌
gcloud run services logs read smart-lock-agent --region=asia-east1 --limit=50

# 串流日誌
gcloud run services logs tail smart-lock-agent --region=asia-east1
```

也可以在 GCP Console → Cloud Run → smart-lock-agent → Logs 頁面查看。

---

## 疑難排解

| 症狀 | 原因 | 解決 |
|------|------|------|
| 403 Forbidden | `allUsers` 未授權或組織政策限制 | 檢查 IAM binding 和 `iam.allowedPolicyMemberDomains` 約束 |
| 容器啟動失敗 | 環境變數缺少或格式錯誤 | `gcloud run services describe` 確認 env vars |
| DB 連線失敗 | Cloud SQL Auth Proxy 未啟用或 service account 缺 `cloudsql.client` | 確認 `--add-cloudsql-instances` 和 IAM 角色 |
| `/health` 回 503 | DB 連線異常（POSTGRES_URI 錯誤或連線中斷） | 執行 `./scripts/deploy.sh --update-db-uri` 重建 URI，檢查 health 回應中的 `checks` 欄位 |
| Vertex AI 403 | Service account 缺少 `aiplatform.user` | 加上 IAM 角色 |
| POSTGRES_URI 連線錯誤 | 密碼特殊字元未 URL encode | 執行 `./scripts/deploy.sh --update-db-uri`（自動 encode） |
| Quick Reply 重複詢問品牌 | DB 連線中斷後 `load_facts` 返回空值 | 所有 DB 模組已內建 `_ensure_conn()` 自動重連機制，應自動恢復；若持續發生檢查 `/health` |
| LINE webhook 無回應 | webhook URL 設定錯誤或 SSL 問題 | 確認 URL 結尾是 `/webhook`，Cloud Run 自帶 SSL |

---

## Cloud Run 檔案系統注意事項

Cloud Run 容器的檔案系統是**可寫但短暫的**（ephemeral）——容器重啟後所有寫入的檔案會消失。

| 功能 | 寫入路徑 | 影響 | 建議 |
|------|---------|------|------|
| 用戶軟輪廓 (.md) | `./data/profiles/` | 重啟後消失，但硬事實（電話、地址、設備）存在 PostgreSQL 不受影響 | 可接受；或設 `user_profile.enabled = false` 只用 PostgreSQL facts |
| 多模態媒體 | `./data/media/` | 檔案只在單次請求中使用（下載→存檔→讀回→送 LLM），重啟不影響 | 目前正常運作；長期可改用 GCS 後端 |

> 如需完全關閉檔案系統寫入，修改 `config.toml`：
> ```toml
> [user_profile]
> enabled = false       # 關閉 .md 輪廓，保留 PostgreSQL facts
> 
> [multimodal]
> enabled = false       # 關閉多模態處理
> ```

---

## 資料庫連線韌性

所有 DB 模組均使用 `autocommit=True` 並內建自動重連機制，防止 CloudSQL 閒置斷線（idle transaction timeout）導致功能異常。

### 連線模式

| 模組 | 檔案 | autocommit | 自動重連 |
|------|------|-----------|----------|
| Checkpointer | `memory/postgres_saver.py` | `True` | 由 LangGraph 管理 |
| User Facts | `profiles/manager.py` | `True` | `_ensure_conn()` |
| Audit Storage | `storage/postgres_impl.py` | `True` | `_ensure_conn()` |
| Data Correction | `harness/data_correction.py` | `True` | `_ensure_conn()` |

### 斷線防護鏈

```
CloudSQL 連線中斷（idle timeout / 網路問題 / 重啟）
  → _ensure_conn() 偵測 closed / broken
  → 自動重連（autocommit=True，無殘留 transaction）
  → 成功 → 繼續操作
  → 失敗 → 優雅降級（返回空值/跳過寫入），不阻斷用戶對話
  → /health 回 503 + checks 細節，方便監控
```

### 為什麼用 autocommit=True

psycopg3 預設 `autocommit=False`，每個 `execute()` 自動開啟 implicit transaction。若程式碼沒有 `commit()` 或 `rollback()`，transaction 會一直開著。CloudSQL 會在 idle transaction 超時後強制關閉連線，導致後續所有操作靜默失敗。`autocommit=True` 讓每個 SQL 語句獨立完成，不留殘留 transaction。

---

## 資料庫維護

### Cloud SQL 表格清單

| 表名 | 用途 | 必要 |
|------|------|------|
| `audit_log` | 對話審計日誌（含 PII masking） | 是 |
| `checkpoints` | LangGraph 對話記憶 | 是 |
| `checkpoint_blobs` | LangGraph 對話記憶（二進位資料） | 是 |
| `checkpoint_writes` | LangGraph 對話記憶（寫入記錄） | 是 |
| `checkpoint_migrations` | LangGraph schema 版本管理 | 是 |
| `user_facts` | 用戶硬事實（電話、地址、設備型號，SCD Type 2） | 是 |
| `user_soft_profiles` | 用戶軟輪廓（品牌特定欄位） | 是 |
| `data_corrections` | #資料修正 回報記錄 | 是 |

> 舊的 RAG 向量表 `langchain_pg_collection` 和 `langchain_pg_embedding` 已於 2026-04-14 移除，目前不使用 RAG。

### 臨時連線 Cloud SQL（維護用）

Cloud SQL 預設不開放外部連線，需臨時授權 IP：

```bash
# 授權目前 IP
MY_IP=$(curl -s ifconfig.me)
gcloud sql instances patch lock-ai --authorized-networks="$MY_IP/32" --quiet

# 用 Docker 內的 psql 連線
MSYS_NO_PATHCONV=1 docker run --rm \
  -e PGPASSWORD='<db-password>' \
  postgres:17 psql -h 35.229.228.13 -p 5432 -U lock-ai -d lock-ai-db

# 完成後務必移除授權
gcloud sql instances patch lock-ai --clear-authorized-networks --quiet
```

---

## 成本估算

| 資源 | 免費額度 | 超出計費 |
|------|---------|---------|
| Cloud Run | 200 萬次請求/月、360,000 vCPU-秒/月 | 按用量 |
| Cloud SQL (db-f1-micro) | 無免費額度 | ~$10/月 |
| Secret Manager | 10,000 次存取/月 | $0.06/10,000 次 |
| Artifact Registry | 0.5 GB | $0.10/GB/月 |
