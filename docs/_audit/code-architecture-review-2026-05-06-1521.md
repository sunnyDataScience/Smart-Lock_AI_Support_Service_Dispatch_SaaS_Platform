---
status: superseded
superseded_by: docs_v2/4-exploration/audits/code-architecture-2026-05-06.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Code 架構審查報告

- **產出日期**: 2026-05-06 15:21
- **分支**: `refactor/scripts-and-env-layout`
- **任務脈絡**: 第三方審查 vibe-coded 程式碼，與 docs 對照，依「議長原則」仗裁
- **本次處理範圍**: 僅 docs 同步（13 條 update-docs 已完成）；本報告列出**code 端的重構候選**，不在本次任務修改

---

## 摘要

| 維度 | 健康度 | 主要發現 |
|------|--------|---------|
| 物理模組邊界（agent / api / data / web） | ✅ EXCELLENT | 零跨模組 import，靠 PostgreSQL + HTTP 解耦，與 Cloud Run 雙服務部署一致 |
| Harness 中介層方向性 | ⚠️ DEGRADED | `debounce.py` 集中 H3+H_DC+H_QR+H6+H7.5+H8 編排，2 條反向 import |
| 設計原則遵循（Linus / SOLID / DRY / 不可變） | 🔴 CRITICAL | `agent/harness/debounce.py` 違反 CLAUDE.md 三大鐵律 |
| 設計模式實作（ReAct / Medallion / SCD2 / Registry / Debounce） | ⚠️ MIXED | 5 模式中 2 ✅、3 ⚠️ |
| Docs↔code 微觀機制對應 | ✅ EXCELLENT | 25/25 機制完美對應（H 層命名、步驟順序、技術細節全一致） |

**結論**：物理隔離與微觀機制都很乾淨；問題集中在 `agent/harness/debounce.py`（818 行 god-class，是 vibe-coded 頭號技術債）與「高層架構描述」（已在 docs 同步處理）。

---

## A. CRITICAL — 阻擋級重構候選（建議下次重構分支立即處理）

### A1. `agent/harness/debounce.py` — God Class 拆分
**現狀**：單檔 818 行，承擔 H3 訊息合併 + H_DC 攔截協調 + H_QR 暫存 + H6 呼叫 + H7.5 呼叫 + H8 寫入 + multimodal cleanup + checkpoint cleanup + 8 種狀態機。

**違反**：
- CLAUDE.md「函式 < 50 行、巢狀 ≤4 層」（多處 5 層、`agent_and_reply` >100 行）
- CLAUDE.md「無特殊情況」Linus 第一準則（11 個 elif 狀態機）
- SOLID 單一職責原則（一檔負擔 8 個職責）

**建議拆分**：
```
agent/harness/
├── orchestrator.py     # agent_and_reply 編排（呼叫各 H 層）
├── buffer.py           # BufferStore dataclass + immutable replace
├── quick_reply.py      # H_QR 暫存與品牌詢問狀態機（從 debounce.py:502-644 抽出）
├── debounce.py         # 純 timer-based 訊息合併（縮減為 < 200 行）
└── (其他維持)
```

**嚴重度**：CRITICAL — 目前所有重要修改都要碰這個檔，可讀性與測試覆蓋率受限。

---

### A2. Mutable Global State Race
**位置**：
- `harness/debounce.py:888-907` — `user_buffers[user_id]["items"].append(content)` 對共享 module-level dict 巢狀 mutation，無鎖
- `harness/debounce.py:619, 632` — `_pending_messages[user_id] = {...}` 與 `:611 .pop()`

**違反**：CLAUDE.md「不可變性 (CRITICAL)：永遠建立新物件，絕不修改既有物件」

**Race 場景**：同一 user 在 1.5s buffer window 內快速發送多則訊息，可能：
- buffer 替換 placeholder 與新訊息 append 競爭
- pending_messages pop 與另一 task set 競爭

**建議**：
- 把 buffer / pending_messages 封裝為 `BufferStore` / `PendingStore` 類別
- 用 dataclass + `dataclasses.replace()` 維持不可變
- 或用 `asyncio.Lock` per user 保護（次選）

**嚴重度**：CRITICAL — 高頻使用下可能出現訊息錯亂或 placeholder 殘留

---

### A3. Silent except 7 處
**位置清單**：
- `harness/debounce.py:737-738`、`760-761`
- `harness/data_correction.py:34-35`
- `storage/postgres_impl.py:49-50`、`153-154`
- `profiles/manager.py:22-23`
- `memory/sqlite_saver.py:22-23`
- `api/core/db.py:33-34`

**違反**：CLAUDE.md「絕不靜默吞噬錯誤」

**風險**：DB 連線失敗、conn.close() 失敗、profile 寫入失敗會被默默吞掉，沒有 log 也沒有 metric。生產問題無從追蹤。

**建議**：每筆都改為：
```python
except Exception as e:
    logger.warning(f"<context>: {e}", exc_info=True)
    # 或往上拋
```

**嚴重度**：CRITICAL — 違反鐵律 + 生產可觀測性致命傷

---

## B. HIGH — 第二優先重構

### B1. PostgreSQL `_ensure_conn` 三份重複（DRY 違反）
**位置**：
- `agent/profiles/manager.py:10-30`
- `agent/storage/postgres_impl.py:37-51`
- `agent/memory/postgres_saver.py:14`

三處幾乎一字不差（含 `autocommit=True` + reconnect 邏輯 + global conn cache）。

**建議**：抽出 `agent/core/pg_pool.py`：
```python
async def get_async_conn(name: str) -> AsyncConnection: ...
```
並把三個模組改為呼叫 helper。CloudSQL 連線管理集中後，bug 修一次處處生效。

---

### B2. `_extract_text` 四份重複（DRY 違反）
**位置**：
- `harness/debounce.py:66`、`harness/debounce.py:124`
- `harness/memory_manager.py:19`
- `quality/quality_check.py:404`

**建議**：抽 `agent/core/content_utils.py`：
```python
def extract_text(content: str | list[dict]) -> str: ...
```

---

### B3. `harness/debounce.py:24` 反向 import
**違例**：`from agent import get_system_prompt` — harness 中介層 import agent root，違反「中介層 → core 單向」。

**建議**：把 `get_system_prompt` 改為由 `app.py` 在 init() 注入給 harness：
```python
# app.py
debounce.set_system_prompt_provider(get_system_prompt)
```

---

### B4. `agent/skills/tools.py:10` 反向 import
**違例**：`from harness.line_ui_factory import match_brand, match_model, get_brand_models` — 領域層 import 中介層。

**建議**：把 `match_brand` / `match_model` 抽到 `agent/core/brand_match.py`，兩邊都從 core import。

---

### B5. content block schema 不一致
**位置**：`harness/debounce.py:75-203` `_normalize_*` 系列 — content block 同時是 `str` 和 `dict`（`{"type": ...}`），typing 不一致導致大量 `isinstance` 分支。

**建議**：在邊界（webhook 入口）就 normalize 為單一 schema（`Block` dataclass），內部就不必判斷。

---

### B6. `harness/debounce.py` 11 elif 狀態機
**違例**：CLAUDE.md Linus 第一準則「好代碼沒有特殊情況」

**位置**：`_quick_reply_intercept` 中「品牌已知/型號已知/型號=其他/型號自輸/品牌未知」5 種狀態，加上其他分支共 11 條 elif。

**建議**：建立 `BrandModelState` enum 或 state-machine dispatch table，扁平化 if/elif。

---

## C. MEDIUM — 設計模式漂移

### C1. `user_facts` schema 漂在 runtime
**位置**：`agent/profiles/manager.py:43-53` 的 `CREATE TABLE IF NOT EXISTS user_facts`。

**問題**：`SQL/Schema_harness_migration.sql` **完全沒有** user_facts 表定義（grep 無命中），表只在 runtime 動態建立。

**風險**：
- 部署到新環境若還沒有任何 facts 寫入，table 不存在
- Schema 變更無版本管理
- 與其他表（audit_logs / data_corrections）不一致

**建議**：把 CREATE TABLE 從 manager.py 抽到 `SQL/Schema_harness_migration.sql`，runtime 只負責 INSERT/UPDATE/SELECT。

---

### C2. Registry pattern 形式不一致
- `storage/__init__.py`：✅ 純 dict registry
- `memory/__init__.py`：⚠️ if/else fast-path (`"memory"`) + dict registry 混用
- `llms/__init__.py`：❌ 沒 dict registry，靠 LiteLLM 字串前綴路由（`vertex_ai/...`）

**docs 已修正（U17）**：精確化為三段描述。

**code 端建議**：
- memory/__init__.py 移除 if/else fast-path，統一走 dict registry
- 評估是否替 llms/ 加上 dict registry（vs 維持 LiteLLM 字串路由）— 設計權衡，**建議寫專屬 ADR**（暫名 `adr-007-llm-registry-pattern.md`）

---

### C3. `harness/debounce.py` 多職拆 H_QR
**問題**：`_pending_messages` 暫存與 `_quick_reply_intercept` 邏輯漂在 debounce.py，docs 把 H_QR 列為獨立中介層。

**建議**：抽 `harness/quick_reply.py`，與 `line_ui_factory.py` 配合（factory 產 LINE UI 物件、quick_reply 管狀態）。

---

## D. LOW — 命名 / 細節

### D1. Skill 物件 in-place 屬性賦值
**位置**：`agent/skills/__init__.py:122-124` `skill.brands = brands; skill.models = models`

**建議**：在建構時就傳入 brands/models（`Skill(name=..., brands=...)`），保持 immutable。

### D2. broad `except Exception` 過寬（HIGH 級但屬於 LOW 重構優先）
- `harness/debounce.py` 5 處
- `data/pipeline/silver_to_skill/_merger.py` 3 處
- `api/services/auth_service.py:91, 122, 133`

**建議**：逐筆收斂為具體 exception type（`asyncpg.OperationalError`、`json.JSONDecodeError` 等）。

---

## E. 待開新 ADR 清單

| 提案 | 理由 |
|------|------|
| `adr-007-llm-registry-pattern.md` | 決定 llms/ 是否補 dict registry，或正式承認「LiteLLM 字串路由 = registry 替代方案」 |
| `adr-008-harness-layer-boundaries.md`（選擇性） | 把 8 個 H 中介層的職責 / 方向性 / 拆分準則正式化（debounce.py 拆分時的依據） |

---

## F. 重構建議順序

```
Phase 1（CRITICAL，下個分支）：
├─ A3 Silent except 7 處（修一次就清乾淨，影響最大）
├─ A2 Mutable global state（封裝 BufferStore + PendingStore）
└─ A1 debounce.py 拆 4 個檔（最大拆分工程）

Phase 2（HIGH，第二輪）：
├─ B1 抽 pg_pool.py
├─ B2 抽 content_utils.py
├─ B3 / B4 修反向 import
├─ B5 content block schema 統一
└─ B6 11 elif → state machine

Phase 3（MEDIUM，第三輪）：
├─ C1 user_facts schema 抽到 SQL 檔
├─ C2 memory registry 統一 + ADR-007
└─ C3 抽 quick_reply.py

Phase 4（LOW，順手做）：
├─ D1 Skill 物件 immutable
└─ D2 except 收斂
```

---

## G. 議長判決總表

| 主題 | docs 說法 | code 現況 | 議長判決 | 本次處理 |
|------|-----------|----------|---------|---------|
| 不可變性鐵律 | CLAUDE.md CRITICAL | debounce.py 大量 mutation | docs 勝（保留） | docs 不動 / code 列入 A2 |
| 函式長度與巢狀 | CLAUDE.md ≤50 / ≤4 | debounce.py 違反 | docs 勝（保留） | docs 不動 / code 列入 A1 |
| Silent except | CLAUDE.md 鐵律 | 7 處違反 | docs 勝（保留） | docs 不動 / code 列入 A3 |
| Linus 無特殊情況 | CLAUDE.md 第一準則 | 11 elif | docs 勝（保留） | docs 不動 / code 列入 B6 |
| Harness→agent 反向 | docs 隱含禁止 | debounce.py:24 | docs 勝（保留） | docs 不動 / code 列入 B3 |
| Skills→harness 反向 | docs 隱含禁止 | tools.py:10 | docs 勝（保留） | docs 不動 / code 列入 B4 |
| H_QR 獨立中介層 | docs 列為獨立 H | 漂在 debounce.py | docs 勝（保留） | docs 不動 / code 列入 C3 |
| 安裝依賴指令 | 舊：pip install | 新：uv sync | code 勝 | docs 已同步（U1） |
| Scripts 路徑 | 舊：scripts/dev-up.sh | 新：scripts/dev/dev-up.sh | code 勝 | docs 已同步（U5-U8） |
| 部署平台 | 舊：nginx + compose | 新：Cloud Run | code 勝 | docs 已同步（U11） |
| Dockerfile | 舊：pip install | 新：multi-stage uv | code 勝 | docs 已同步（U12） |
| 7 sub-graph 架構 | docs：7 個 sub-agent | code：single ReAct | code 勝（reality） | docs 已同步 + 保留 Vision callout（U14） |
| Harness L1-L8 子目錄 | docs：8 子目錄 | code：8 扁平檔 | code 勝（reality） | docs 已同步（U15） |
| Medallion 命名 | docs：silver_to_gold | code：silver_to_skill | code 勝 | docs 已同步（U16） |
| Registry pattern 描述 | docs：概化 | code：三種變體不一 | docs 過度概化 | docs 已精確化（U17） |
| LLM registry 形式 | docs：concept | code：LiteLLM 字串 | 雙輸 | docs 已精確化 / 待 ADR-007 |

---

## 影響評估

- **嚴重度**: CRITICAL（A 級 3 條 + HIGH 6 條集中在 debounce.py）
- **影響範圍**:
  - 阻擋級：debounce.py 重構是後續任何中介層擴充的前置
  - 觀測級：silent except 修完前，生產 DB 異常無從診斷
  - 設計級：ADR-007 LLM registry 形式決定後，code 端修法才能落地
- **建議**：開新分支 `refactor/harness-debounce-decomposition`，完成 Phase 1 後再回主線
