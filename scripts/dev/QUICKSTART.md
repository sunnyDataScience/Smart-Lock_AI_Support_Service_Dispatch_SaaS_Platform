# Smart Lock 平台 — 一鍵啟動操作手冊

> 給工程師、PM、業主或合作方在本機看 demo 用。對應 `scripts/dev/quickstart.sh` 與 `scripts/seed/realistic_demo_seed.py`。

---

## TL;DR

```bash
# 在專案根目錄
./scripts/dev/quickstart.sh
```

5 分鐘後打開 <http://localhost:3000> → 用 `test@lock-ai.com` / `changeme123` 登入。

> 第一次跑會稍久（要下載 Docker image + 跑 schema migration）。第二次起只需 30 秒。

---

## 一、事前準備（首次安裝）

### 1. 安裝必要工具

| 工具 | 用途 | 安裝指令（Mac） |
|---|---|---|
| **Docker Desktop** | 跑 PostgreSQL | <https://www.docker.com/products/docker-desktop/> |
| **uv** | Python 套件管理 | `brew install uv` 或 `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js 20+** | 跑前端 | `brew install node` |
| **Git** | 拉專案 | Mac 內建 |

驗證：
```bash
docker --version    # 24+ 即可
uv --version        # 0.4+ 即可
node --version      # 20+ 即可
```

### 2. 拉專案 + 建 `.env`

```bash
git clone <repo-url> Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform
cd Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform

# 從範例複製
cp .env.example .env

# 編輯 .env，至少填這幾個（若只看 demo 可保留範例值）
#   GEMINI_API_KEY=<可選；若不接 LLM 可空>
#   DATABASE_URL=postgresql://lock:0000@localhost:5433/lock_AI_data
```

### 3. 確認 Docker Desktop 已啟動
打開 Docker Desktop app（Mac 工具列有鯨魚圖示）。

---

## 二、日常操作

### A. 一鍵啟動（最常用）

```bash
./scripts/dev/quickstart.sh
```

腳本會依序：
1. 啟動 PostgreSQL Docker 容器（pgvector/pg17，:5433）
2. 套用資料庫 schema + 28 個 migrations（只第一次）
3. 套用既有 fixture（admin 帳號 / 示範技師）
4. 套用 **真實感大量假資料**（51 客戶 / 83 工單 / 35 保固 / 23 爭議 / 48 庫存 / 24 退款）
5. 啟動 backend（FastAPI :8001，背景）
6. 啟動 frontend（Next.js :3000，背景）
7. 印出網址 + 登入帳號

完成後會看到：
```
════════════════════════════════════════════════
  ✓ 開發環境就緒
════════════════════════════════════════════════
  Frontend (admin):  http://localhost:3000
  Backend API:       http://localhost:8001
  API docs:          http://localhost:8001/docs
  PostgreSQL:        localhost:5433  (lock / 0000 / lock_AI_data)

  登入 admin 帳號:    test@lock-ai.com / changeme123
```

### B. 停止

直接 `Ctrl+C`。腳本會收尾 backend / frontend，**但 PostgreSQL 容器保留**（資料不會掉）。

要連 DB 也關：
```bash
docker stop lock_AI
```

### C. 砍掉重來

當資料髒掉或想完全重置：
```bash
./scripts/dev/quickstart.sh --fresh
```

會：移除舊 DB 容器 → 建新容器 → 重套 schema → 重套 seed。

### D. 重跑假資料（不重啟服務）

DB 已存在、只想補資料：
```bash
python3 scripts/seed/realistic_demo_seed.py | \
  docker exec -i lock_AI psql -U lock -d lock_AI_data
```

或調整數量：
```bash
python3 scripts/seed/realistic_demo_seed.py \
  --customers 100 --work-orders 200 --invoices 150 | \
  docker exec -i lock_AI psql -U lock -d lock_AI_data
```

---

## 三、登入帳號

| 角色 | Email | 密碼 |
|---|---|---|
| 系統管理員 | `test@lock-ai.com` | `changeme123` |
| 示範技師 | `test@lock-ai.com` | `changeme123` |
| 派工員 | `dispatcher@example.com` | `changeme123` |

---

## 四、常用後台頁面

打開 <http://localhost:3000> 登入後：

### 派工 / 工單
| 頁面 | 路徑 | 看點 |
|---|---|---|
| 派工佇列監控 | `/admin/dispatch-queue` | 4 KPI 卡 + 派工歷程表 + 即時推播 |
| 派工人工介入 | `/admin/dispatch-manual?work_order_id=...` | 候選技師 + 5 種 reason_code 指派 |
| 工單列表 | `/work-orders` | 83 筆 + 4 filter（狀態/期間/品牌/keyword）|
| 工單看板 | `/work-orders/kanban` | 依 status 分欄 |
| 工單地圖 | `/work-orders/map` | 地址標記 + SLA 排序 toggle |
| 新增工單 | 三 view 右上 button | 兩步驟 modal（選 problem card → 客戶資訊）|

### 客服 / 客戶
| 頁面 | 路徑 | 看點 |
|---|---|---|
| 客戶主檔 | `/admin/customers` | 51 客戶 + 4 filter |
| 對話管理 | `/conversations` | LINE 對話歷程 |
| 問題卡 | `/problem-cards` | 80 筆 + 4 filter |
| 知識庫 | `/knowledge-base` | SOP + manual |

### 帳務
| 頁面 | 路徑 | 看點 |
|---|---|---|
| 月結算總覽 | `/accounting` | 對帳 + 結算 + 批次操作 |
| 發票管理 | `/accounting/invoices` | 63 筆 + 4 filter |
| 營收報表 | `/accounting/revenue` | 日/週/月/季切片 + 自訂期間 + 匯出 |
| 會計傳票 | `/accounting/vouchers` | PDF 匯出 |
| 退款審批 | `/admin/refunds` | 24 筆 + SLA 分群 |

### 售後
| 頁面 | 路徑 | 看點 |
|---|---|---|
| 保固索賠 | `/admin/warranty-claims` | 35 筆 + 5 詳情頁 + 證據縮圖 |
| 爭議仲裁 | `/admin/disputes` | 23 筆 + 5 類型 chip filter + 證據面板 + 決議表單 |

### 庫存 / 技師
| 頁面 | 路徑 | 看點 |
|---|---|---|
| 庫存 | `/admin/inventory` | 48 品項 + 補貨 / 編輯 / 異動紀錄 |
| 技師主檔 | `/technicians` | 17 技師 + 4 filter |

### 報表
| 頁面 | 路徑 | 看點 |
|---|---|---|
| KPI 儀表板 | `/admin/reports/kpi` | 轉換漏斗 + 異常率 + 平均處理時長 |
| 技師排行 | `/admin/reports/technician-ranking` | 綜合評分 + 期間 + 排序 + 區域 |
| SOP 績效 | `/admin/knowledge-base/sop-performance` | 4 KPI + 狀態分佈 + Top N |

### Phase II（新模組）
| 頁面 | 路徑 |
|---|---|
| 簽核入箱 | `/admin/approval-inbox` |
| AI 治理 | `/admin/ai-governance` |
| SOP 回饋 | `/admin/sop-feedback` |
| RMA 品質 | `/admin/rma-quality` |
| 品牌 B2B 對帳 | `/admin/brand-b2b` |
| 技師生命週期 | `/admin/technicians-lifecycle` |
| GDPR 遺忘權 | `/admin/gdpr-forget-queue` |

---

## 五、Demo 操作示範流程

給合作方或業主看時，建議走這條 5 分鐘流程：

### 流程 A：客服 → 派工 → 完工
1. **`/admin/dispatch-queue`** — 看待派工佇列 / 點某工單「人工介入」
2. **`/admin/dispatch-manual?work_order_id=...`** — 看候選技師排序 / filter 後指派
3. **`/work-orders/[id]`** — 看工單詳情 / 完工狀態
4. **`/accounting/invoices`** — 看對應發票
5. **`/admin/reports/kpi`** — 看 KPI 漏斗變動

### 流程 B：售後爭議處理
1. **`/admin/disputes`** — 點某 filed 爭議 row
2. 看雙方證據面板（客戶 + 技師上傳照片）
3. 在決議表單填「CSM 提案」+ 金額 → 送出 → status 轉 in_review
4. 再次選同筆 → 填「最終決議 ≥ 5 字」→ co-sign 結案

### 流程 C：保固索賠
1. **`/admin/warranty-claims`** — 看 35 筆混合狀態列表
2. 點某筆「檢視詳情」進詳情頁
3. 看設備 / 保固期 / 關聯工單 / 證據媒體縮圖
4. 點關聯工單 → 開新分頁跳轉

---

## 六、故障排除

### Q1. 「`port 8001 已被占用`」
有另一個 backend 在跑。找出來停掉：
```bash
lsof -i :8001
kill -9 <PID>
```

### Q2. 「`docker: command not found`」
Docker Desktop 沒啟動，或 PATH 沒帶到。先打開 Docker Desktop app。

### Q3. 「`postgres did not become ready within 30s`」
DB 容器啟動異常。看 log：
```bash
docker logs lock_AI --tail 50
```
常見：port :5433 已被占用 → 改 port 或停掉占用者。

### Q4. 前端顯示「`401 Unauthorized`」
登入 token 過期或被清。重新登入即可。

### Q5. 假資料沒進去 / 頁面空蕩
看 seed log：
```bash
tail -50 .dev-logs/seed.stderr
```
通常是 schema 與資料不對齊 → `./scripts/dev/quickstart.sh --fresh` 重來。

### Q6. 前端編譯卡很久
首次 `npm install` 要幾分鐘。後續會用 cache。看進度：
```bash
tail -f .dev-logs/npm-install.log
```

### Q7. 我想看 backend log
```bash
tail -f .dev-logs/backend.log
```

### Q8. 我想直接連資料庫
```bash
docker exec -it lock_AI psql -U lock -d lock_AI_data
```

---

## 七、給業主 / PM 看 demo 時的小提示

1. **先確認 Docker Desktop 已開**（鯨魚圖示在工具列）
2. **筆電插電 + 螢幕鏡像 / HDMI 準備好**
3. 開新 terminal 跑 `./scripts/dev/quickstart.sh`，等 1-2 分鐘
4. 打開瀏覽器到 `http://localhost:3000`，用 admin 帳號登入
5. **不要關掉那個 terminal**（關了 = backend/frontend 停）
6. 結束時：terminal 按 `Ctrl+C` → 收尾乾淨

---

## 八、進階用法

### 只改假資料量
```bash
# 預設值
python3 scripts/seed/realistic_demo_seed.py --help
```

可調：`--customers / --technicians / --work-orders / --invoices / --warranty-claims / --disputes / --reconciliations / --inventory / --refunds`

### 跳過假資料（只起空 DB）
```bash
./scripts/dev/quickstart.sh --no-seed
```

### 只起 backend + DB（前端用 production build 跑或不用）
```bash
./scripts/dev/quickstart.sh --backend-only
```

### 看 API 文件
<http://localhost:8001/docs> — Swagger UI 自動生成

---

## 九、檔案位置

| 用途 | 路徑 |
|---|---|
| 一鍵啟動腳本 | `scripts/dev/quickstart.sh` |
| 真實感假資料產生器 | `scripts/seed/realistic_demo_seed.py` |
| 既有 fixture | `SQL/seeds/*.sql` |
| Schema | `SQL/Schema.sql` + `SQL/Schema_*.sql` + `SQL/migrations/*.sql` |
| Backend | `api/main.py`（FastAPI）|
| Frontend | `web/`（Next.js）|
| Log | `.dev-logs/` |
| 環境變數 | `.env`（從 `.env.example` 複製）|

---

## 十、需要幫忙時

- 程式問題 → 看 `.dev-logs/{backend,frontend}.log`
- DB 結構問題 → `docker exec -it lock_AI psql -U lock -d lock_AI_data` 後 `\dt`
- 整體文件 → `docs/system-completion-status.md`（完成度盤點）
- 各頁面狀態 → `web/docs/page-status.md`（給業主版本）

---

*最後更新：2026-06-08*
