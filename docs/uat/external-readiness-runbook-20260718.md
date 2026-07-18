# 外部憑證到位後執行手冊（B 區就緒 runbook）— 2026-07-18

> 業主裁決「先做 2（等外部條件的線）再做 1（回歸輪）」。本手冊把**憑證到位後要做的每一步**寫成可照抄的清單：
> 你提供憑證/執行重佈 → 工程側零等待接上 B1/B2/B3 驗收。
> 工程側**已預先完成**的前置也記錄在此（§0），避免屆時重查。

---

## 〇、工程側已完成的前置（2026-07-18 深夜）

| 前置 | 狀態 | 說明 |
|---|---|---|
| 兩個 builtin skill v1 **已發佈**（本機） | ✅ | `locksmith-cs-sop` / `locksmith-product-knowledge` 均 v1 published（stamp 11/12）——本機 seed 原本只有 draft，SkillSync 無 published 可物化＝fail-soft 回退 builtin，**B2 的 60s 生效測試會誤判失敗**。已在品牌後台發佈修正 |
| migration 107/108/109 本機已套 | ✅ | 雲端要套（見 §3） |
| `Schema_line_notify.sql` 本機 lock_tech 已套 | ✅ | 雲端技師庫要套（見 §3；UAT-P1-3 的 schema 半部） |
| 四站容器全部跑最新修復版 | ✅ | 兩輪 UAT 82 findings 修復均已 build 進本機容器 |

## 一、LINE 官方帳號送件（業主執行，B1 前置）

到 [LINE Developers Console](https://developers.line.biz/) 同一個 Provider 下建**兩個 channel**：

1. **Messaging API channel**（推播用）——取得：
   - Channel secret → env `PLATFORM_LINE_CHANNEL_SECRET`
   - Channel access token（long-lived）→ env `PLATFORM_LINE_CHANNEL_ACCESS_TOKEN`
   - Webhook URL 設為：`https://<tech-api 對外域名>/api/v1/line/binding-webhook`（本機測試= `http://<內網IP>:8002/...`，需可被 LINE 打到＝雲端才實際可用）＋開啟「Use webhook」
2. **LINE Login channel**（既有客服 OA 若已有可共用 Provider）

> 憑證未設時系統 fail-soft：綁定卡顯示「開通中」、推播 no-op——**不會壞**，設了即生效。

## 二、憑證入 env ＋ 重佈（工程或業主照抄）

### 本機（先在本機驗 B1 綁定流程）

```bash
# 憑證放 shell env 或 .env（不入 git）
export PLATFORM_LINE_CHANNEL_SECRET="<from console>"
export PLATFORM_LINE_CHANNEL_ACCESS_TOKEN="<from console>"
docker compose -f web/tech-portal/docker-compose.yml up -d --build tech-api
```

### 雲端 agent 重佈（B2 LiveSkill＋B3 RAG 一次到位）

```bash
# secrets 先入 GCP Secret Manager（INTERNAL_API_TOKEN 與 api 同值）
AGENT_TENANT_ID=00000000-0000-0000-0000-000000000001 \
RAG_TENANT_ID=00000000-0000-0000-0000-000000000001 \
./scripts/deploy/agent.sh
# LOCK_API_BASE_URL 由腳本自動解析 api 的 Cloud Run URL，不用手填
# ⚠️ 動 POSTGRES_URI 一律 --update-db-uri，永不手動構建
# ⚠️ agent.sh health check 對 webhook 服務會誤報 404——看 STARTUP probe 才準
```

> 這是**最後一次**為 skill 更新重佈；之後品牌後台改知識、admin 發佈、60s 生效。

## 三、雲端 DB 待套清單（工程執行；`gcloud sql connect`，user=lock-ai db=lock-ai-db）

```
SQL/migrations/107-reconciliation-reject.sql     -- 對帳駁回審計欄
SQL/migrations/108-intake-case-links.sql         -- 進線案件關聯欄
SQL/migrations/109-payout-rule-crud.sql          -- 拆帳規則 updated_at/deleted_at
SQL/tech_authority/Schema_line_notify.sql        -- 技師庫 LINE 綁定表（雲端技師庫）
```

另：雲端品牌庫需 `agent/scripts/seed_builtin_skills.py` 把 builtin skill 入庫＋品牌後台發佈 v1（同 §0 本機做法），B2 才有 published 版可物化。

## 四、B 區驗收步驟（憑證＋重佈完成後，對照 `uat-checklist-20260718.md` B 區）

- **B1 推播實收**：師傅站帳戶頁產 6 位綁定碼 → LINE 加官方號好友傳碼 → 回「綁定成功」→ 品牌後台派單給該師傅 → LINE 即時收到通知（無客戶 PII、點連結直達工單）→ 池單發布 → 開池通知的師傅收到 → 解綁後不再收
- **B2 LiveSkill 60s**：品牌後台改一條 FAQ（可用型號知識精靈）→ admin 發佈 → 60 秒內 LINE 問 AI 客服 → 回答用新知識 → 回滾 → 60 秒內變回
- **B3 RAG 檢索**：LINE 問「非 references 措辭」的產品問題 → AI 語義檢索命中（brand 大小寫漏資料已修；需 RAG_TENANT_ID 已設＋語料已灌雲端 pgvector）
- **B4 雲壓測＋HSTS**：本機腳本雲端複跑（上雲窗口）

## 五、之後的第三輪 UAT

外部項驗完後，工程跑**第三輪代理 UAT**（已在 B 區前排定）：兩輪 82 findings 修復逐項回歸＋未測角落（看板/地圖/排班/庫存/客戶主檔/知識庫 cases/報表匯出/異常管理/稽核權限/多人並發）＋B 區結果彙整——一次收斂出貨判定。
