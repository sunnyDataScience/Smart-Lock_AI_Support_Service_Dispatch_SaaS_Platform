---
status: superseded
superseded_by: docs_v2/4-exploration/change-requests/CR-0002-refactor-phase1-2.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 重構計畫 — Phase 1-2（V1 上線前後，可平行於前端串接）

- **日期**: 2026-05-06
- **適用期間**: 前端串接期 → V1.0 上線後 4-6 週
- **核心原則**: 不影響前端 contract、不影響使用者行為、可由獨立工程師並行進行
- **配套文件**:
  - 本計畫的問題依據：[code-architecture-review-2026-05-06-1521.md](./code-architecture-review-2026-05-06-1521.md)
  - 議長判決依據：[consistency-matrix-2026-05-06-1521.md](./consistency-matrix-2026-05-06-1521.md)
  - tier1 長期計畫：[refactor-plan-tier1-2026-05-06.md](./refactor-plan-tier1-2026-05-06.md)

---

## Context — 為什麼是現在做

### 時序判斷
- 前端 33 頁開發完，**功能測試與後端串接尚未進行**
- `_audit` 已揭露 CRITICAL 2 + HIGH 6 條設計原則違反
- 這些違反**目前沒有真實使用者**，但**會卡住未來任何擴充**
- 業務優先級：先 V1 上線、再做大重構（tier1 路線見配套文件）

### 並行軌道（與前端串接同步）
```
Track A: 前端串接 + Playwright E2E         ← 用戶主軌
Track B: 後端契約完善（被 A 拉動）         ← 純加法，無侵入
Track C: 後端內部品質（本計畫主角）         ← 與 A/B 完全獨立
Track D: 觀測 + 基建（本計畫主角）          ← 與所有人獨立
```

### 不在本計畫的（屬 tier1）
- 多租戶 RLS、tenant_id 全表化
- ACL / Adapter / Saga / Outbox
- API Gateway / Service Mesh
- Cell-based architecture
- mTLS / SOC2

---

## Phase 1 — Track C：後端內部品質（V1 上線前可全做）

### 預期成果
- 消除 3 大 CLAUDE.md 鐵律違反（silent except、DRY、特殊情況）
- `agent/core/` 模組成形（PG pool、content utils 等共用元件）
- registry pattern 形式統一
- 為 Phase 2（debounce.py 拆分）打地基

### Phase 1 工作項

#### P1-1 ── Silent except 全面修復（CRITICAL）
- **問題**：7 處 `except: pass` 違反 CLAUDE.md「絕不靜默吞噬錯誤」
  - `harness/debounce.py:737-738`、`760-761`
  - `harness/data_correction.py:34-35`
  - `storage/postgres_impl.py:49-50`、`153-154`
  - `profiles/manager.py:22-23`
  - `memory/sqlite_saver.py:22-23`
  - `api/core/db.py:33-34`
- **改法**：每處改為
  ```python
  except Exception as e:
      logger.warning(f"<context>: {e}", exc_info=True)
      # 視情境決定 swallow / re-raise
  ```
- **PR 拆分**：每檔一個 PR（7 個小 PR），便於 review
- **分支命名**：`fix/silent-except-{file}`
- **驗證**：
  ```bash
  rg -n 'except.*:\s*pass$' agent/ api/ | wc -l   # 應為 0
  cd agent && uv run python -m quality.quality_check --no-judge   # 應仍 pass
  ```
- **預估**：每 PR 30-60 分鐘，總計 1-2 工作日
- **依賴**：無
- **風險**：低（純加 log，不改邏輯）

#### P1-2 ── 抽 `agent/core/pg_pool.py`（HIGH，DRY 違反）
- **問題**：3 份 `_ensure_conn()` 重複
  - `agent/profiles/manager.py:10-30`
  - `agent/storage/postgres_impl.py:37-51`
  - `agent/memory/postgres_saver.py:14`
- **改法**：
  ```python
  # agent/core/pg_pool.py
  _CONN_CACHE: dict[str, AsyncConnection] = {}

  async def get_async_conn(name: str, uri: str) -> AsyncConnection:
      """Idempotent connection fetcher with auto-reconnect for CloudSQL."""
      conn = _CONN_CACHE.get(name)
      if conn is None or conn.closed:
          conn = await AsyncConnection.connect(uri, autocommit=True)
          _CONN_CACHE[name] = conn
      return conn
  ```
- **PR 拆分**：
  1. PR1：建 `agent/core/pg_pool.py` + 單元測試
  2. PR2：profiles/manager.py 改用 helper
  3. PR3：storage/postgres_impl.py 改用 helper
  4. PR4：memory/postgres_saver.py 改用 helper
- **分支命名**：`refactor/pg-pool-extraction`（或 4 個子分支 squash）
- **驗證**：
  ```bash
  cd agent && uv run pytest tests/unit/core/test_pg_pool.py
  cd agent && uv run python -m quality.quality_check --no-judge
  curl http://localhost:8000/health   # 應仍回 200
  ```
- **預估**：1-2 工作日
- **依賴**：無
- **風險**：中（連線管理是熱路徑，要驗證 CloudSQL 重連行為）

#### P1-3 ── 抽 `agent/core/content_utils.py`（HIGH，DRY 違反）
- **問題**：4 份 `_extract_text` 重複
  - `harness/debounce.py:66`、`harness/debounce.py:124`
  - `harness/memory_manager.py:19`
  - `quality/quality_check.py:404`
- **改法**：抽出 `extract_text(content: str | list[dict]) -> str`，所有呼叫點 import
- **PR 拆分**：1 個 PR（量小、邏輯單純）
- **分支命名**：`refactor/content-utils-extraction`
- **驗證**：
  ```bash
  cd agent && uv run pytest tests/unit/core/test_content_utils.py
  cd agent && uv run python -m quality.quality_check
  ```
- **預估**：半個工作日
- **依賴**：無
- **風險**：低

#### P1-4 ── `user_facts` schema 從 runtime 抽到 SQL 檔（MEDIUM）
- **問題**：`profiles/manager.py:43-53` 動態建表，`SQL/Schema_harness_migration.sql` 沒這個 table 定義
- **改法**：
  1. 把 `CREATE TABLE user_facts` 加進 `SQL/Schema_harness_migration.sql`
  2. `profiles/manager.py` 改為**只 INSERT/UPDATE/SELECT**，不 CREATE
  3. 部署腳本確保新環境會跑 migration
- **PR 拆分**：1 個 PR
- **分支命名**：`refactor/user-facts-schema-to-sql`
- **驗證**：
  ```bash
  # 在乾淨 docker DB 跑 migration，確認 table 存在
  ./scripts/dev/dev-up.sh
  psql -U lock -d lock_AI_data -c '\d user_facts'   # 應有所有欄位
  cd agent && uv run python -m quality.quality_check --no-judge
  ```
- **預估**：半個工作日
- **依賴**：無
- **風險**：低（部署時要記得跑 migration；可先跑 `IF NOT EXISTS` 兼容）

#### P1-5 ── `memory/__init__.py` 統一 dict registry（MEDIUM）
- **問題**：if/else fast-path（`"memory"` 走特例）+ dict registry 混用
- **改法**：把 in-process MemorySaver 包成 `build_memory_saver()`，註冊進 `MEMORY_REGISTRY`，移除 if/else
- **PR 拆分**：1 個 PR
- **分支命名**：`refactor/memory-registry-unification`
- **驗證**：
  ```bash
  cd agent && uv run python main.py   # CLI 仍可啟動
  cd agent && uv run python -m quality.quality_check --no-judge
  ```
- **預估**：半個工作日
- **依賴**：無
- **風險**：低

#### P1-6 ── `agent/skills/__init__.py` Skill immutable 化（LOW）
- **問題**：`skill.brands = brands; skill.models = models` in-place 屬性賦值（line 122-124）
- **改法**：在 `Skill(...)` 建構時就傳入 brands/models，移除事後賦值
- **PR 拆分**：1 個 PR（量極小）
- **分支命名**：`refactor/skill-immutable`
- **驗證**：
  ```bash
  cd agent && uv run python main.py
  cd agent && uv run python -m quality.quality_check
  ```
- **預估**：1 小時
- **依賴**：無
- **風險**：極低

---

## Phase 1 ── Track D：觀測 + 基建（V1 上線前可全做）

### 預期成果
- 結構化日誌覆蓋全鏈路
- OpenTelemetry trace 啟用（不送出，先 collect）
- Cost attribution per-skill 細化
- Dockerfile 升級到 multi-stage uv（docs 範本已寫好）

### Phase 1 Track D 工作項

#### P1-D1 ── 結構化日誌（structlog）
- **目的**：替換零散的 `print` / `logger.info`，加入 `tenant_id` / `user_id` / `request_id` context
- **範圍**：先做 `agent/app.py` + `agent/harness/debounce.py` 兩個熱路徑
- **改法**：
  ```python
  import structlog
  log = structlog.get_logger()
  log.info("agent_invoked", user_id=uid, skill="ts-door-stuck")
  ```
- **PR**：2 個（先建 logger config、再替換）
- **預估**：1-2 工作日
- **風險**：低
- **依賴**：無
- **加分**：未來 OpenTelemetry trace 可直接從 structlog context 拿 fields

#### P1-D2 ── OpenTelemetry tracing middleware（先 collect 不送出）
- **目的**：為 V1 上線後接 Cloud Trace / Datadog 預留接口
- **改法**：
  - 加 `opentelemetry-instrumentation-fastapi`
  - exporter 設為 `ConsoleSpanExporter`（先看 log，不送外部）
  - tag：`http.method` / `http.route` / `user_id`
- **PR**：1 個
- **預估**：半個工作日
- **風險**：低（默認 sampler 是 always_off，不影響效能）

#### P1-D3 ── Opik cost attribution per-skill
- **目的**：未來 tier1 計費基礎；現在先收集數據
- **改法**：在 `agent/skills/tools.py` 的 `load_skill` 內加 Opik tag：`skill_name=...`
- **PR**：1 個
- **預估**：半個工作日
- **風險**：低
- **依賴**：Opik 環境變數已設

#### P1-D4 ── Dockerfile 升級為 multi-stage uv build
- **目的**：減小 image size、加速 CI build、`uv.lock` 釘版可重現
- **範圍**：`agent/Dockerfile` + `api/Dockerfile`
- **範本**：見 `docs/04-deliver/E9--deployment-and-operations-guide.md` §7.3
- **PR**：1 個
- **預估**：半個工作日
- **驗證**：
  ```bash
  docker build -t agent-test agent/
  docker run --rm agent-test uvicorn --version   # 確認執行環境正確
  # CI 上跑 build 確認時間縮短
  ```
- **風險**：低（部署管線會自動跑新 build）

#### P1-D5 ── Health endpoint 擴充
- **目的**：上線後的 `/health` 要能準確反映各 backend 狀態
- **改法**：補 LLM ping、checkpoint backend ping、media storage ping
- **PR**：1 個
- **預估**：半個工作日
- **風險**：低

---

## Phase 2 — V1 上線後（W5+，等真實流量出來）

### 觸發條件（必須全滿足才開始）
1. ✅ V1 上線且穩定運行 2 週以上
2. ✅ Phase 1 全部完成（silent except 清乾淨、core/ 模組成形、observability 收 baseline）
3. ✅ Playwright E2E 覆蓋率 ≥ 80% 主路徑
4. ✅ LINE flow E2E（debounce 行為、multimodal、Quick Reply）有自動化測試
5. ✅ 真實使用者流量 baseline 量測完成（QPS、p50/p95 latency、debounce 觸發頻率）

### Phase 2 工作項（依優先序）

#### P2-1 ── `agent/harness/debounce.py` 拆分（CRITICAL，最大重構）
- **問題**：818 行 god class，承擔 H3 + H_DC + H_QR + H6 + H7.5 + H8 編排
- **目標結構**：
  ```
  agent/harness/
  ├── orchestrator.py     # agent_and_reply 編排核心（≤150 行）
  ├── buffer.py           # BufferStore dataclass + immutable replace（≤100 行）
  ├── quick_reply.py      # H_QR 暫存與品牌詢問狀態機（≤200 行）
  ├── debounce.py         # 純 timer-based 訊息合併（≤100 行）
  ├── (其他 H 中介層維持不動)
  ```
- **拆分順序**（每步驟一個 PR、每步驟必須完整 E2E 通過）：
  1. **PR1**：抽 `BufferStore` 類別（封裝 `user_buffers` 與 `_pending_messages`），debounce.py 改用 BufferStore；本 PR 不改外部行為
  2. **PR2**：抽 `harness/quick_reply.py`，把 `_quick_reply_intercept` + `_pending_messages` 邏輯搬出
  3. **PR3**：抽 `harness/orchestrator.py`，把 `agent_and_reply` 編排搬出
  4. **PR4**：debounce.py 縮減為純 timer 合併
- **分支命名**：`refactor/harness-debounce-decomposition`（4 個子 PR squash 入主分支）
- **驗證**（每 PR 必跑）：
  ```bash
  # E2E 測試
  cd agent && uv run pytest tests/e2e/test_line_flow.py
  # quality check 對照 baseline（不能退步）
  cd agent && uv run python -m quality.quality_check
  # 模擬器
  uv run tests/tools/simulate_e2e.py --scenarios all
  ```
- **預估**：5-8 工作日（最大重構）
- **依賴**：P1-1（silent except）、P1-2（pg_pool）、Track A 的 E2E 覆蓋率
- **風險**：高（核心訊息流，任何 bug 直接影響使用者）；緩解：每 PR 都有 E2E + quality_check + 灰度發布

#### P2-2 ── Skill 系統反向耦合修復（HIGH）
- **問題**：`agent/skills/tools.py:10` 反向 import `harness.line_ui_factory`
- **改法**：把 `match_brand` / `match_model` 抽到 `agent/core/brand_match.py`，skills 與 harness 都從 core import
- **PR**：1 個
- **分支**：`refactor/skill-harness-decoupling`
- **預估**：1 工作日
- **依賴**：P2-1（debounce 拆分後 line_ui_factory 邊界更清楚）

#### P2-3 ── Harness → agent 反向耦合修復（HIGH）
- **問題**：`harness/debounce.py:24 from agent import get_system_prompt`
- **改法**：`get_system_prompt` 改由 `app.py` 在 init() 注入（DI 模式）
- **PR**：1 個
- **分支**：`refactor/harness-agent-decoupling`
- **預估**：1 工作日
- **依賴**：P2-1

#### P2-4 ── 11 elif 狀態機 → table-driven dispatch（MEDIUM）
- **問題**：`debounce.py` `_quick_reply_intercept` 11 條 elif（爛品味）
- **改法**：建 `BrandModelState` enum + state-machine dispatch table
- **PR**：1 個
- **分支**：`refactor/quick-reply-state-machine`
- **預估**：1-2 工作日
- **依賴**：P2-1（quick_reply.py 已抽出）

#### P2-5 ── content block schema 統一（MEDIUM）
- **問題**：`harness/debounce.py:75-203` `_normalize_*` 大量 isinstance 分支
- **改法**：在 webhook 入口就 normalize 為 `Block` dataclass，內部不再判斷 type
- **PR**：1-2 個（先建 Block dataclass、再替換）
- **分支**：`refactor/content-block-normalization`
- **預估**：2-3 工作日
- **依賴**：P2-1

#### P2-6 ── except Exception 收斂為具體型別（LOW）
- **範圍**：harness、data pipeline、auth_service 共 11 處
- **改法**：逐筆改為 `asyncpg.OperationalError` / `json.JSONDecodeError` 等具體型別
- **PR**：3-4 個（按模組分）
- **預估**：2 工作日
- **依賴**：P1-1（silent except 已加 log，知道實際抓到什麼異常）

---

## 風險矩陣

| 工作項 | 風險 | 緩解 |
|------|------|------|
| Phase 1 全部 | 低 | 純內部、有 quality_check 把關 |
| P1-2 pg_pool | 中 | 在乾淨 docker DB 驗證 + CloudSQL 連線測試 |
| P1-D4 Dockerfile | 中 | 先在 staging Cloud Run 部署驗證 |
| P2-1 debounce 拆分 | 高 | 必須有 E2E 覆蓋；每 PR 灰度（先 5% 流量） |
| P2-2 / P2-3 反向耦合修復 | 中 | 完整 import graph 檢查（`pydeps` 工具） |

---

## 不做的事（明確邊界）

- ❌ 不加 `tenant_id` 到任何表（屬 tier1）
- ❌ 不上 PostgreSQL RLS（屬 tier1）
- ❌ 不引入 Saga / Outbox（屬 tier1）
- ❌ 不換 LLM provider 架構（要 A/B 框架先）
- ❌ 不上 service mesh（單服務沒必要）
- ❌ 不寫新 ADR（只在 Phase 2 結束後評估是否需要 ADR-007 LLM registry）

---

## 完工驗收

### Phase 1 完成標準
- [ ] `rg -n 'except.*:\s*pass$' agent/ api/` 回傳 0 行
- [ ] `agent/core/` 包含 pg_pool.py、content_utils.py 兩個共用模組
- [ ] `SQL/Schema_harness_migration.sql` 含 user_facts 完整 schema
- [ ] `memory/__init__.py` 無 if/else fast-path
- [ ] structlog 在 app.py + debounce.py 可見
- [ ] OpenTelemetry middleware 啟用（ConsoleExporter）
- [ ] Dockerfile multi-stage uv build 上 staging 驗證通過
- [ ] quality_check baseline 不退步

### Phase 2 完成標準
- [ ] `agent/harness/debounce.py` ≤ 200 行
- [ ] `harness/orchestrator.py` / `buffer.py` / `quick_reply.py` 各自獨立、職責單一
- [ ] 無反向 import（`pydeps` 圖可視化驗證）
- [ ] 11 elif 狀態機改為 dispatch table
- [ ] content block 統一為 Block dataclass
- [ ] Phase 1+2 全程 E2E 不退步、quality_check 不退步

---

## 工作量估計

| Phase | 工作量 | 工程師數 | 月曆時間 |
|-------|------|--------|--------|
| Phase 1 Track C | 5-7 工作日 | 1 人 | 1.5 週 |
| Phase 1 Track D | 4-5 工作日 | 1 人 | 1 週 |
| Phase 1 合計（並行） | 約 7-8 工作日 | 1 人 | 2 週 |
| Phase 2 | 14-19 工作日 | 1 人 | 4-5 週 |
| **Phase 1+2 總計** | **21-27 工作日** | **1 人** | **6-7 週** |

> 與前端串接（Track A）並行：Track C/D 完全獨立，A 軌的時間表不會被 Phase 1 拖累；Phase 2 必須等 A 軌完成 + V1 上線後啟動。
