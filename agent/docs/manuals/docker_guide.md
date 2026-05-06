# Docker 容器操作手冊

本文件說明如何在本地用 Docker 容器執行 agent，搭配 ngrok 對外暴露給 LINE webhook 測試。

---

## 前置需求

- Docker Desktop 已安裝並啟動
- 專案主目錄下有 `.env` 和 `credentials.json`（GCP Service Account）
- PostgreSQL 容器（pgvector）已啟動

---

## 1. 啟動 PostgreSQL（pgvector）

首次建立：

```bash
docker run --name lock_AI \
  -e POSTGRES_USER=lock \
  -e POSTGRES_PASSWORD=0000 \
  -e POSTGRES_DB=lock_AI_data \
  -p 5433:5432 \
  -d pgvector/pgvector:pg17
```

後續重啟只需：

```bash
docker start lock_AI
```

---

## 2. 準備 `.env.docker`

Docker 的 `--env-file` 不會去除引號，所以需要一份無引號版本。在專案主目錄執行：

```bash
sed 's/="\(.*\)"/=\1/' .env > .env.docker
```

> `.env.docker` 已加入 `.gitignore`，不會被 commit。

---

## 3. 建構 Agent Image

```bash
# 從專案根目錄 build（context = PROJECT_ROOT，因為 uv workspace 共享 uv.lock）
docker build --platform linux/amd64 -f agent/Dockerfile -t smart-lock-agent .
```

Image 採用 multi-stage uv build：
- **builder**：copy uv binary + 鎖定檔，跑 `uv sync --frozen --no-dev --package smart-lock-agent`，享 cache mount + bytecode 預編譯
- **runtime**：`python:3.11-slim-bookworm` + builder 的 `.venv` + agent 原始碼，無 build tools 與 uv binary，image 體積最小

secrets（`.env`、`credentials.json`）透過專案根 `.dockerignore` 排除，不會包進 image。

---

## 4. 啟動 Agent 容器

```bash
MSYS_NO_PATHCONV=1 docker run -d \
  --name smart-lock-test \
  --env-file /path/to/project/.env.docker \
  -v /path/to/project/credentials.json:/app/credentials.json:ro \
  -e POSTGRES_URI="postgresql://lock:0000@host.docker.internal:5433/lock_AI_data" \
  -e GOOGLE_APPLICATION_CREDENTIALS="/app/credentials.json" \
  -p 8080:8080 \
  smart-lock-agent
```

**說明：**

| 參數 | 用途 |
|------|------|
| `--env-file` | 載入無引號版 `.env` |
| `-v credentials.json:/app/credentials.json:ro` | 掛載 GCP 憑證（唯讀） |
| `-e POSTGRES_URI` | 透過 `host.docker.internal` 連到宿主機的 PostgreSQL |
| `-e GOOGLE_APPLICATION_CREDENTIALS` | 讓 Google SDK 自動找到憑證 |
| `-p 8080:8080` | 對應 Cloud Run 預設 port |

> **Windows Git Bash 注意**：必須加 `MSYS_NO_PATHCONV=1`，否則 `/app/credentials.json` 會被自動轉換成 Windows 路徑。

---

## 5. 啟動 ngrok Tunnel

首次建立（需要 authtoken）：

```bash
docker run -d --name ngrok \
  -e NGROK_AUTHTOKEN=<your-token> \
  ngrok/ngrok http host.docker.internal:8080
```

查看 tunnel URL：

```bash
curl -s http://localhost:4040/api/tunnels | python -m json.tool
```

取得 `public_url` 後，到 LINE Developers Console 更新 webhook URL 為：

```
https://xxxx-xxx-xxx.ngrok-free.app/webhook
```

---

## 6. 常用操作

### 查看 Agent 日誌

```bash
docker logs smart-lock-test
docker logs -f smart-lock-test  # 即時追蹤
```

### 快速測試 Agent

```bash
# 健康檢查
curl http://localhost:8080/health

# 問答測試
curl "http://localhost:8080/chat?q=門打不開怎麼辦"
```

### 重建 Agent（修改程式碼後）

只需要重建 agent 容器，**不要動 ngrok**（避免 URL 變動要重設 LINE webhook）：

```bash
docker stop smart-lock-test && docker rm smart-lock-test
cd agent && docker build -t smart-lock-agent .
MSYS_NO_PATHCONV=1 docker run -d \
  --name smart-lock-test \
  --env-file /path/to/project/.env.docker \
  -v /path/to/project/credentials.json:/app/credentials.json:ro \
  -e POSTGRES_URI="postgresql://lock:0000@host.docker.internal:5433/lock_AI_data" \
  -e GOOGLE_APPLICATION_CREDENTIALS="/app/credentials.json" \
  -p 8080:8080 \
  smart-lock-agent
```

### 清除測試對話歷史

`/chat` 端點使用 `test-cli` 作為 user_id，對話歷史存在 PostgreSQL。如果需要乾淨的測試 session：

```bash
docker exec smart-lock-test python -c "
import asyncio
from psycopg import AsyncConnection

async def main():
    conn = await AsyncConnection.connect(
        'postgresql://lock:0000@host.docker.internal:5433/lock_AI_data'
    )
    for t in ['checkpoints', 'checkpoint_blobs', 'checkpoint_writes']:
        await conn.execute(
            f\"DELETE FROM {t} WHERE thread_id = 'line_test-cli'\"
        )
    await conn.commit()
    await conn.close()

asyncio.run(main())
"
```

### 停止所有容器

```bash
docker stop smart-lock-test lock_AI ngrok
```

---

## 7. 疑難排解

| 症狀 | 原因 | 解決 |
|------|------|------|
| `credentials were not found` | `credentials.json` 路徑錯誤或未設 `GOOGLE_APPLICATION_CREDENTIALS` | 確認 `-v` 掛載路徑和 `-e GOOGLE_APPLICATION_CREDENTIALS` |
| `.env` 值帶引號導致 API 錯誤 | `docker --env-file` 不去除引號 | 使用 `.env.docker`（無引號版） |
| `/app/credentials.json` 變成 Windows 路徑 | Git Bash MSYS 路徑轉換 | 加 `MSYS_NO_PATHCONV=1` |
| Agent 回答重複或受歷史影響 | PostgreSQL checkpoint 殘留 | 清除 `line_test-cli` 的 checkpoint 記錄 |
| ngrok URL 變了 | ngrok 容器被重啟 | 重新到 LINE Console 更新 webhook URL |
| `docker logs` 沒有輸出 | Python stdout buffer | Dockerfile 已設 `PYTHONUNBUFFERED=1` |
