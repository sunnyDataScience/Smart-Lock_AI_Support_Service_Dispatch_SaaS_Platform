# 部署 Secret 問題排查手冊

- **最後更新**：2026-04-30
- **適用對象**：執行 `agent/scripts/deploy.sh` 的工程師
- **配套文件**：`cloud_run_deploy.md`（完整部署流程）、`opik_incident_2026-04-30.md`

---

## 1. 部署前必做的三步驗證

每次部署前，**先在本機跑這三個指令**，全綠才執行 `./agent/scripts/deploy.sh`：

```bash
# Step 1：確認 gcloud 已登入且 token 未過期
gcloud auth print-access-token > /dev/null && echo "OK: gcloud 已登入" || echo "FAIL: 跑 gcloud auth login"

# Step 2：確認專案
gcloud config get-value project
# 預期輸出：cedar-scope-489604-g3

# Step 3：確認 6 個 secret 存在
gcloud secrets list --project=cedar-scope-489604-g3
# 預期看到：DB_PASSWORD / LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN / OPIK_API_KEY / OPIK_WORKSPACE / POSTGRES_URI
```

---

## 2. 已知陷阱：Pre-flight 全紅 ≠ Secret 真的缺

### 2.1 症狀

`./agent/scripts/deploy.sh` 跑完 pre-flight 階段出現：

```
FAIL: gcloud 未登入，請執行: gcloud auth login
FAIL: Secret LINE_CHANNEL_SECRET 不存在
FAIL: Secret LINE_CHANNEL_ACCESS_TOKEN 不存在
FAIL: Secret POSTGRES_URI 不存在
FAIL: Secret OPIK_API_KEY 不存在
FAIL: Secret OPIK_WORKSPACE 不存在
```

### 2.2 真正原因

**gcloud auth token 過期** → `gcloud secrets describe` 在無 auth context 下全部失敗 → pre-flight 把它解讀成「secret 不存在」（false negative）。

Secret 實際上**全部都在 Secret Manager**。

### 2.3 修復步驟

```bash
gcloud auth login                                   # 重新登入
gcloud auth print-access-token > /dev/null && echo OK   # 驗證 token 取得成功
./agent/scripts/deploy.sh                            # 重跑部署
```

### 2.4 判讀規則（記在腦裡）

| Pre-flight 第一行訊息 | 意義 |
|---|---|
| `FAIL: gcloud 未登入` | **後續所有 secret FAIL 都是假的**，先處理 auth |
| `OK: gcloud 已登入` 但 secret FAIL | secret 真的有問題，依下方 §3 處理 |

---

## 3. Secret 各別處理對照表

| Secret | 用途 | 重建指令 |
|---|---|---|
| `DB_PASSWORD` | Cloud SQL 原始密碼（拼接 POSTGRES_URI 用） | `echo -n 'NEW_PW' \| gcloud secrets versions add DB_PASSWORD --data-file=-` |
| `POSTGRES_URI` | Cloud SQL Unix socket 完整連線字串 | **永遠用 `./deploy.sh --update-db-uri`**，禁止手動拼接 |
| `LINE_CHANNEL_SECRET` | LINE webhook 簽章驗證 | LINE Developers Console → Channel settings → Channel secret |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE 推播 / reply API | LINE Developers Console → Messaging API → Channel access token |
| `OPIK_API_KEY` | OPIK 雲端 SDK 認證 | comet.com → Account Settings → API Keys |
| `OPIK_WORKSPACE` | OPIK workspace 標識 | comet.com → workspace 名稱 |

### 3.1 POSTGRES_URI 安全重建（密碼變更後唯一正確流程）

```bash
# 1. 先更新 DB_PASSWORD secret
echo -n 'NEW_RAW_PASSWORD' | gcloud secrets versions add DB_PASSWORD --data-file=-

# 2. 用 deploy.sh 自動重建（含 URL encode + round-trip 驗證）
./agent/scripts/deploy.sh --update-db-uri
```

**禁止做的事**：
- ❌ 手動 `echo -n 'postgresql://lock-ai:xxx@/...' | gcloud secrets versions add POSTGRES_URI`
- ❌ 在 shell 用變數插值密碼（會踩 `$`、`!`、`#` 等特殊字元）
- ❌ 跳過 round-trip 驗證直接寫入

---

## 4. OPIK Secret 的特殊狀態（2026-04-30 後）

OPIK 因 callback hang 事件已在 `agent/config.toml:164` `[opik].enabled = false` 暫時關閉（詳見 `opik_incident_2026-04-30.md`）。

### 4.1 目前狀態

- `OPIK_API_KEY` / `OPIK_WORKSPACE` secret **仍存在 Secret Manager**
- `deploy.sh:48-49` **仍把它們注入為 Cloud Run 環境變數**
- App 啟動時因為 `enabled=false` **不會去讀**這兩個 env var

### 4.2 為什麼不立刻清掉

- 重啟 OPIK 只需改 `config.toml` 一行 + redeploy，不需重新建 secret
- 移除掛載要改 `deploy.sh` + 撤銷 SA IAM，回退成本不小

### 4.3 何時清理

長期決定不再用 OPIK（例如選用 LangSmith / Langfuse / 自製方案）後：

1. 從 `deploy.sh:48-49` 移除 `OPIK_API_KEY` / `OPIK_WORKSPACE` 兩行
2. 從 pre-flight 必檢清單 `deploy.sh:165` 拿掉
3. `gcloud secrets delete OPIK_API_KEY` + `gcloud secrets delete OPIK_WORKSPACE`
4. 撤銷 SA 權限（如有單獨綁定）

---

## 5. Secret 權限模型速查

| 角色 | 帳號 | 權限 |
|---|---|---|
| 部署者 | `sunny@funngo.ai`（人） | `roles/secretmanager.admin`（讀寫所有 secret） |
| Runtime SA | `lock-ai@cedar-scope-489604-g3.iam.gserviceaccount.com` | `roles/secretmanager.secretAccessor`（只能讀 latest） |

### 5.1 新增 secret 後必做：授予 SA 讀權限

`deploy.sh:117-119` 已自動處理 `POSTGRES_URI` 的 IAM binding。其他 secret 若是手動建立，記得補：

```bash
gcloud secrets add-iam-policy-binding <SECRET_NAME> \
    --member="serviceAccount:lock-ai@cedar-scope-489604-g3.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" --quiet
```

### 5.2 驗證 SA 是否能讀

```bash
gcloud secrets get-iam-policy <SECRET_NAME>
# 確認 bindings 含 lock-ai@... + roles/secretmanager.secretAccessor
```

---

## 6. 部署後驗證

deploy.sh 已內建 health check retry，但失敗時手動跑一次：

```bash
curl -sS https://smart-lock-agent-1083648618124.asia-east1.run.app/health | python3 -m json.tool
# 預期：{"status": "ok", "version": "2.0-skills", "checks": {"facts_db": "ok", "audit_db": "ok"}}
```

若 `checks.facts_db` 或 `audit_db` 為 `disconnected`：
- 99% 是 `POSTGRES_URI` secret 內容錯誤 → 跑 `./deploy.sh --update-db-uri` 重建
- 看 Cloud Run logs：`gcloud run services logs read smart-lock-agent --region asia-east1 --limit 50`

---

## 7. 改進建議（待施工）

| 優先 | 改進 | 理由 |
|---|---|---|
| P0 | `deploy.sh` pre-flight 在 gcloud 未登入時 **立即 short-circuit**，不要繼續 check secret | 避免「auth 過期 → 5 個 secret 假性 FAIL」誤導 |
| P1 | Pre-flight 加一行「token 剩餘有效期」提醒 | 提早警告快過期 |
| P2 | OPIK 長期方案決定後，把 `OPIK_*` secret 從 deploy.sh 拿掉 | 降低未使用 secret 的維運面積 |

---

## 8. 相關檔案

- `agent/scripts/deploy.sh` — 部署腳本（pre-flight 在 line 130-202）
- `agent/scripts/deploy.sh:165` — 必檢 secret 清單
- `agent/config.toml:162-168` — OPIK 開關
- `agent/docs/manuals/cloud_run_deploy.md` — 完整部署流程
- `agent/docs/manuals/opik_incident_2026-04-30.md` — OPIK 事件報告
