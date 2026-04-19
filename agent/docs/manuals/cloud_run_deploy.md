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
| Secret Manager | `LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`、`DB_PASSWORD` |
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

# DB Password
echo -n "<your-db-password>" | \
  gcloud secrets create DB_PASSWORD --data-file=-

# 授予 Cloud Run service account 存取權
SA="1083648618124-compute@developer.gserviceaccount.com"
for SECRET in LINE_CHANNEL_SECRET LINE_CHANNEL_ACCESS_TOKEN DB_PASSWORD; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
done
```

### Step 3：Build & Push Image

```bash
cd agent

# Build for linux/amd64（Cloud Run 需要）
docker build --platform linux/amd64 \
  -t asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:latest .

# Push
docker push asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:latest
```

### Step 4：部署到 Cloud Run

```bash
gcloud run deploy smart-lock-agent \
  --image=asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:latest \
  --region=asia-east1 \
  --platform=managed \
  --allow-unauthenticated \
  --service-account=lock-ai@cedar-scope-489604-g3.iam.gserviceaccount.com \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --timeout=60 \
  --add-cloudsql-instances=cedar-scope-489604-g3:asia-east1:lock-ai \
  --set-env-vars="VERTEX_PROJECT_ID=cedar-scope-489604-g3,VERTEX_LOCATION=us-central1,POSTGRES_URI=postgresql://lock-ai:<URL_ENCODED_PASSWORD>@/lock-ai-db?host=/cloudsql/cedar-scope-489604-g3:asia-east1:lock-ai" \
  --set-secrets="LINE_CHANNEL_SECRET=LINE_CHANNEL_SECRET:latest,LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest"
```

> **冷啟動說明**：`--min-instances=0` 代表閒置時容器會縮到 0，下次請求需要冷啟動（約 5-10 秒，含 LLM 初始化、PostgreSQL 連線、技能索引載入）。
>
> ```bash
> # 開啟常駐（消除冷啟動，約 $15-20/月）
> gcloud run services update smart-lock-agent --region=asia-east1 --min-instances=1
>
> # 關閉常駐（省錢，允許冷啟動）
> gcloud run services update smart-lock-agent --region=asia-east1 --min-instances=0
> ```
>
> 不需要重新 build/push，update 即時生效。

> **POSTGRES_URI 注意**：密碼中的特殊字元需要 URL encode（`@` → `%40`、`[` → `%5B`、`;` → `%3B`、`+` → `%2B`、`*` → `%2A`）。Cloud SQL Auth Proxy 使用 Unix socket 連線，所以 host 部分用 `?host=/cloudsql/<連線名稱>`。

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

# 重新 build + push
docker build --platform linux/amd64 \
  -t asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:latest .

docker push asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:latest

# 部署新版本
gcloud run deploy smart-lock-agent \
  --image=asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:latest \
  --region=asia-east1 \
  --service-account=lock-ai@cedar-scope-489604-g3.iam.gserviceaccount.com
```

> 環境變數和 secrets 不需要重新設定，Cloud Run 會保留上次的設定。

---

## 驗證

```bash
# Health check
curl https://smart-lock-agent-1083648618124.asia-east1.run.app/health

# Chat 測試
curl "https://smart-lock-agent-1083648618124.asia-east1.run.app/chat?q=門打不開怎麼辦"

# Webhook 測試（應回 Invalid signature）
curl -X POST https://smart-lock-agent-1083648618124.asia-east1.run.app/webhook \
  -H "Content-Type: application/json" -d '{}'

# 即時日誌（串流，Ctrl+C 停止）
gcloud alpha run services logs tail smart-lock-agent --region=asia-east1

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
| Vertex AI 403 | Service account 缺少 `aiplatform.user` | 加上 IAM 角色 |
| POSTGRES_URI 連線錯誤 | 密碼特殊字元未 URL encode | 用 Python `urllib.parse.quote()` 編碼密碼 |
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
