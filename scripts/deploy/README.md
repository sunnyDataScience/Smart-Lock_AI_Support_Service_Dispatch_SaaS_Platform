# scripts/deploy/ — Cloud Run 部署手冊

對應 [`scripts/README.md`](../README.md) 情境 C：產品環境部署到 GCP Cloud Run。

## 目前涵蓋

| 服務 | 腳本 | 部署目標 |
| :--- | :--- | :--- |
| **agent** (LINE Bot) | `agent.sh` | Cloud Run service `smart-lock-agent` |
| **api** (FastAPI 後端) | `api.sh` | Cloud Run service `smart-lock-api` |
| **web** (Next.js Admin) | `web.sh` | Cloud Run service `smart-lock-web`（standalone build, ~215MB） |

---

## 首次部署完整流程

依以下順序，**每步都跑通才進下一步**。

### 步驟 1：GCP 專案前置設定（一次性）

```bash
# 認證
gcloud auth login
gcloud auth application-default login
gcloud config set project cedar-scope-489604-g3

# 啟用必要服務
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    sqladmin.googleapis.com

# 建 Artifact Registry repo（agent / api 共用）
gcloud artifacts repositories create lock-ai-repo \
    --repository-format=docker \
    --location=asia-east1
```

### 步驟 2：建立 Secret Manager 中的所有 secret

> ⚠️ **建 secret 千萬別讓值帶尾換行**。`openssl rand -hex 32 | gcloud secrets create`
> 會把 openssl 的尾 `\n` 一起存進去 —— `INTERNAL_API_TOKEN` 帶換行會讓 agent 放進
> `X-Internal-Token` header 時被 httpx 拒（`Illegal header value`），橋接全失敗。
> 一律用 `tr -d '\n'`（或 `printf '%s'`）去尾換行。（2026-06-16 首次部署踩雷。）

```bash
# agent 與 api 都會用到的 DB 密碼
printf '%s' "<ACTUAL_PROD_DB_PASSWORD>" | gcloud secrets create DB_PASSWORD --data-file=-

# agent 從 DB_PASSWORD 自動拼接 POSTGRES_URI（用 --update-db-uri）
./scripts/deploy/agent.sh --update-db-uri

# LINE Bot
printf '%s' "<LINE_CHANNEL_SECRET>" | gcloud secrets create LINE_CHANNEL_SECRET --data-file=-
printf '%s' "<LINE_CHANNEL_ACCESS_TOKEN>" | gcloud secrets create LINE_CHANNEL_ACCESS_TOKEN --data-file=-

# OPIK（觀察性，可選）
printf '%s' "<OPIK_API_KEY>" | gcloud secrets create OPIK_API_KEY --data-file=-
printf '%s' "<OPIK_WORKSPACE>" | gcloud secrets create OPIK_WORKSPACE --data-file=-

# api 的 JWT（記得 tr -d 去換行）
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create API_JWT_SECRET_KEY --data-file=-

# agent ↔ api 內部橋接認證（兩服務共用同一值；必須去尾換行）
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create INTERNAL_API_TOKEN --data-file=-

# 授權 service account 讀所有 secret（每個都要）
SA="lock-ai@cedar-scope-489604-g3.iam.gserviceaccount.com"
for s in DB_PASSWORD POSTGRES_URI LINE_CHANNEL_SECRET LINE_CHANNEL_ACCESS_TOKEN \
         OPIK_API_KEY OPIK_WORKSPACE API_JWT_SECRET_KEY INTERNAL_API_TOKEN; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:${SA}" --role=roles/secretmanager.secretAccessor
done
```

> deploy 腳本會自動帶入：api 用 `POSTGRES_URI / API_JWT_SECRET_KEY / INTERNAL_API_TOKEN /
> LINE_CHANNEL_ACCESS_TOKEN` + env `AGENT_TENANT_ID` + 解析 web URL → `CORS_ORIGINS`；
> agent 用 `LINE_* / POSTGRES_URI / OPIK_* / INTERNAL_API_TOKEN` + 解析 api URL →
> `LOCK_API_BASE_URL`；web build 時烤入 `NEXT_PUBLIC_API_BASE_URL` + `NEXT_PUBLIC_REALTIME_BASE_URL`。

### 步驟 3：DB schema 初始化

```bash
# 先建 on-demand 備份（動 prod DB 前的保險）
gcloud sql backups create --instance=lock-ai --description="pre-schema-$(git rev-parse --short HEAD)"

# 透過 cloud-sql-proxy 連 prod DB（保護 prod，不直接暴露 5432）
./scripts/dev/proxy-up.sh   # → 127.0.0.1:5432（需 ADC：gcloud auth application-default login）

# 一鍵套用完整 schema（Schema.sql → Schema_*.sql → migrations/*.sql，全 idempotent、不灌 demo seed）
export POSTGRES_URI="postgresql://lock-ai:<DB_PASSWORD>@127.0.0.1:5432/lock-ai-db"
./scripts/db/apply-schema-prod.sh   # 結尾會掃 log 攔真錯誤

# admin 種子（讓 api 能登入；首次才需）
psql "$POSTGRES_URI" -f SQL/seeds/_admin_user.sql

./scripts/dev/proxy-down.sh
```

> 註：舊版手動逐檔 `psql -f Schema_*.sql` 已被 `apply-schema-prod.sh` 取代（順序對齊
> `scripts/dev/quickstart.sh`，且涵蓋全部 10 個 Schema 檔 + migrations 000~034，不再漏檔）。

### 步驟 4：部署服務（順序：agent → api → web）

```bash
# 4.1 部署 agent（含 build → push → deploy → health check）
./scripts/deploy/agent.sh

# 4.2 部署 api
./scripts/deploy/api.sh

# 4.3 部署 web（依賴 api 的 service URL，先把 api URL 設進 web/.env.production）
echo "NEXT_PUBLIC_API_BASE_URL=https://smart-lock-api-xxx.a.run.app" > web/.env.production
./scripts/deploy/web.sh

# 各自的 service URL 會印在 deploy.sh 結尾
```

### 步驟 5：驗證 prod 服務

```bash
# 從各 service URL 打 /health 或 /
curl https://smart-lock-agent-xxx.a.run.app/health
curl https://smart-lock-api-xxx.a.run.app/health
curl https://smart-lock-web-xxx.a.run.app/        # 200 + dashboard HTML

# 設定 LINE Bot webhook URL 到 agent service URL
# 在 LINE Developers Console: Messaging API → Webhook URL → 貼 https://...../webhook
```

---

## 日常更新部署

平常程式碼改動後重新部署：

```bash
# preflight 會驗：gcloud / docker / uv lock --check / secrets 存在
./scripts/deploy/agent.sh                # agent 改了
./scripts/deploy/api.sh                  # api 改了
```

兩支腳本都支援：

| Flag | 作用 |
| :--- | :--- |
| 無 flag | 完整：build → push → deploy → health check |
| `--build-only` | 只 build image（push 與 deploy 跳過） |
| `--deploy-only` | 用既有 image 重新 deploy（不 build） |

agent 額外支援：

| Flag | 作用 |
| :--- | :--- |
| `--update-db-uri` | 從 `DB_PASSWORD` secret 重建 `POSTGRES_URI` secret（密碼輪替時用） |

---

## Rollback（部署失敗或要回退版本）

每次 deploy 的 image tag 都是 `{git-sha}-{timestamp}`，可直接回退：

```bash
# 1. 列出 agent 所有 revision（最近 10 個）
gcloud run revisions list --service=smart-lock-agent --region=asia-east1 --limit=10

# 2. 看某 revision 用的 image
gcloud run revisions describe <REVISION_NAME> --region=asia-east1 \
    --format='value(spec.containers[0].image)'

# 3. 把 100% traffic 導回上一個 revision
gcloud run services update-traffic smart-lock-agent --region=asia-east1 \
    --to-revisions=<PREVIOUS_REVISION>=100

# 4. 確認流量切換完成
gcloud run services describe smart-lock-agent --region=asia-east1 \
    --format='value(status.traffic)'
```

---

## 部署前 Checklist

| 檢查項 | 怎麼驗 |
| :--- | :--- |
| dev 分支已合 main / 最新 commit | `git log --oneline main..HEAD` 為空 |
| uv.lock 與 pyproject.toml 同步 | `uv lock --check` |
| 本機 docker build 可過 | `docker build -f agent/Dockerfile -t test .` |
| 有 active gcloud account | `gcloud auth list --filter=status:ACTIVE` |
| 在正確 GCP project | `gcloud config get-value project` 為 `cedar-scope-489604-g3` |
| 所有 secret 存在 | `gcloud secrets list \| grep -E "DB_PASSWORD\|LINE_\|API_JWT\|OPIK"` |
| local quality_check 通過 | `cd agent && uv run python -m quality.quality_check` |

deploy script 的 preflight 會自動檢查多數項目（包含 `uv lock --check`）。

---

## 常見問題

### Q: deploy 卡在 "waiting for service to be ready"

CI/Cloud Run 啟動時會打 `/health` 重試 60 秒。若一直 fail：
1. `gcloud run services logs read smart-lock-agent --region=asia-east1 --limit=100`
2. 看是不是 DB 連不上（`POSTGRES_URI` secret 過期或密碼錯）→ `--update-db-uri`
3. 看是不是缺 secret（CMD 裡 import 找不到）→ 補上對應 secret 後重 deploy

### Q: 改了 pyproject.toml 但 image 沒拉到新版

uv.lock 與 pyproject.toml 失同步。本機跑：
```bash
uv lock      # 重生 lockfile
git add pyproject.toml uv.lock
git commit -m "chore(deps): update X"
./scripts/deploy/agent.sh
```

### Q: 想看部署的 image 實際內容

```bash
docker pull asia-east1-docker.pkg.dev/cedar-scope-489604-g3/lock-ai-repo/smart-lock-agent:<tag>
docker run --rm -it --entrypoint sh asia-east1-docker.pkg.dev/.../smart-lock-agent:<tag>
ls /app/.venv/lib/python3.11/site-packages/
```

### Q: 啟用自助忘記密碼 email（CR-0025 / ADR-0114）

自助重設預設**未送信**（`email_provider` 未配置 SMTP 時 fail-safe：token 仍建、`/auth/request-password-reset` 仍回 200，但信不送）。要實際送信：

```bash
# 1. 建 SMTP secret（用信譽 provider 的 SMTP endpoint：SendGrid / SES / ...）
printf '%s' "<SMTP_HOST>"     | gcloud secrets create SMTP_HOST --data-file=-
printf '%s' "<SMTP_USER>"     | gcloud secrets create SMTP_USER --data-file=-
printf '%s' "<SMTP_PASSWORD>" | gcloud secrets create SMTP_PASSWORD --data-file=-
# 授權 SA 讀（同既有 secret 迴圈）

# 2. api.sh 部署時帶入這些 secret 為 env（SMTP_HOST/SMTP_USER/SMTP_PASSWORD/
#    SMTP_PORT/SMTP_FROM/SMTP_USE_TLS）+ env PASSWORD_RESET_WEB_URL=<web Cloud Run URL>
#    （未設 PASSWORD_RESET_WEB_URL 時 fallback 取 CORS_ORIGINS[0]）

# 3. 套 migration 035（apply-schema-prod.sh 已涵蓋 migrations/*.sql，會自動帶到）
```

> 未配 SMTP 不會壞：request 照常 200、token 建但信不送（log 留警告）。確認 prod 真能收信再放給使用者用。

### Q: 想看 prod 對話 / audit log

**不要**直接連 prod DB query。改走情境 B：
```bash
./scripts/dev/dev-up-gcp.sh --agent-only
./tests/tools/view_logs.py 50
./tests/tools/view_facts.py --user <user_id>
```

---

## 相關文件

- [`../README.md`](../README.md) — scripts/ 全景與情境 A/B
