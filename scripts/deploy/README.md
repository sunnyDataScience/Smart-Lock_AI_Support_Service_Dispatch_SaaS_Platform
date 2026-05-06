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

```bash
# agent 與 api 都會用到的 DB 密碼
echo -n "<ACTUAL_PROD_DB_PASSWORD>" | gcloud secrets create DB_PASSWORD --data-file=-

# agent 從 DB_PASSWORD 自動拼接 POSTGRES_URI（用 --update-db-uri）
./scripts/deploy/agent.sh --update-db-uri

# LINE Bot
echo -n "<LINE_CHANNEL_SECRET>" | gcloud secrets create LINE_CHANNEL_SECRET --data-file=-
echo -n "<LINE_CHANNEL_ACCESS_TOKEN>" | gcloud secrets create LINE_CHANNEL_ACCESS_TOKEN --data-file=-

# OPIK（觀察性，可選）
echo -n "<OPIK_API_KEY>" | gcloud secrets create OPIK_API_KEY --data-file=-
echo -n "<OPIK_WORKSPACE>" | gcloud secrets create OPIK_WORKSPACE --data-file=-

# api 的 JWT
echo -n "$(openssl rand -hex 32)" | gcloud secrets create API_JWT_SECRET_KEY --data-file=-
```

### 步驟 3：DB schema 初始化

```bash
# 透過 cloud-sql-proxy 連 prod DB（保護 prod，不直接暴露 5432）
./scripts/dev/proxy-up.sh

# 套用 schema（依序執行）
psql "$POSTGRES_URI" -f SQL/Schema.sql
psql "$POSTGRES_URI" -f SQL/Schema_harness_migration.sql
psql "$POSTGRES_URI" -f SQL/Schema_v2_extensions.sql
psql "$POSTGRES_URI" -f SQL/Schema_api_phase1.sql

# admin 種子（讓 api 能登入）
psql "$POSTGRES_URI" -f SQL/seeds/_admin_user.sql

./scripts/dev/proxy-down.sh
```

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
- [`../../agent/docs/manuals/cloud_run_deploy.md`](../../agent/docs/manuals/cloud_run_deploy.md) — agent 部署細節
- [`../../docs/04-deliver/E9--deployment-and-operations-guide.md`](../../docs/04-deliver/E9--deployment-and-operations-guide.md) — 整體運維手冊
