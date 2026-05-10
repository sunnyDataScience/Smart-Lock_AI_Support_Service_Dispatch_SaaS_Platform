---
status: superseded
superseded_by: docs_v2/4-exploration/agent-harness-v2/layering-rules.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Agent 模組分層規則與 CI 守護（ADR-style）

**版本**：v1.0（2026-05-07）
**對應 PR**：#23（RP2.2）/ #24（RP2.3）/ #25（RP2.6）/ #28（lint guards）
**狀態**：Active — dev tip `01fe197+` 起執行

---

## 1. 為何需要分層規則

`agent/` 樹是 LINE Bot 服務的 hot-path，在 v1.3.x 系列演進中累積了反向耦合：

- `skills/tools.py` import `harness/line_ui_factory`（leaf 層 → 上層）
- `harness/debounce.py` import `agent.py`（middleware 層 → 編排層）
- `harness` / `quality` / `data/pipeline` 散落 50+ 處 `except Exception`，吞掉 typo 與 programming bug

**後果**：pydeps 圖出現 cycle，未來 RP2.1 拆 `harness/debounce.py`（god-class）會被卡住；新人進來看不懂為何 leaf 模組要去 import middleware。

---

## 2. 目標分層（Clean Architecture）

```
            ┌─────────────────┐
            │     app.py       │  ← FastAPI 入口、依賴注入點
            └────────┬─────────┘
                     │ uses
            ┌────────▼─────────┐
            │     agent.py     │  ← LangGraph build / system_prompt 持有
            └────────┬─────────┘
                     │ uses
   ┌─────────────────┼─────────────────┐
   │                 │                 │
┌──▼───────┐  ┌──────▼─────┐   ┌───────▼───────┐
│ harness/ │  │  skills/   │   │  profiles/    │
│ memory/  │  │            │   │  storage/     │
│  ...     │  │            │   │  ...          │
└──┬───────┘  └──────┬─────┘   └───────┬───────┘
   │                 │                 │
   └─────────────────┼─────────────────┘
                     │ all use
            ┌────────▼─────────┐
            │     core/        │  ← leaf：config / brand_match / content_utils /
            │                  │     logging_config / pg_pool / tracing
            └──────────────────┘
```

**規則**：箭頭只能往下指，**不可反向**。

---

## 3. 三條硬性 lint 規則

### 規則 1：`skills/` 不可 `from harness`/`import harness`

**Why**：skills 是 leaf 層，只負責 tools 註冊與 SKILL.md 載入。需要的工具（如 `match_brand`）應該從更底層的 `core` 取，不是從 middleware 取。

**修正方法**：把共享 helper 下沉到 `core/`。

**過往違規**：`skills/tools.py:10 from harness.line_ui_factory import match_brand` → PR #23 修為 `from core.brand_match import match_brand`。

### 規則 2：`core/` 不可 `from harness`/`from skills`/`import harness`/`import skills`

**Why**：core 是真正的 leaf，不能依賴任何上層。如果 core 需要 harness 的功能，那是「用錯地方」— 該功能應該本身就在 core，或該被搬下來。

**修正方法**：把功能下沉，或把它重新定位為 harness 的私有 helper。

**過往違規**：無（一直保持乾淨，本規則純預防性）。

### 規則 3：`harness/` 不可 `from agent`/`import agent`（頂層 module）

**Why**：harness 是 middleware，不能反向依賴編排層 `agent.py`。需要 agent 的東西（如 `system_prompt`），應該由 `app.py` startup 注入。

**修正方法**：在被需要功能對應的 `harness.X.init()` 加 callable 參數，由 `app.py` 啟動時把 agent 模組的函式或物件傳進去。

**過往違規**：`harness/debounce.py:31 from agent import get_system_prompt` → PR #24 修為：

```python
# debounce.py
_get_system_prompt = lambda: ""

def init(..., system_prompt_getter=None):
    global _get_system_prompt
    if system_prompt_getter is not None:
        _get_system_prompt = system_prompt_getter
```

```python
# app.py startup
from agent import build_agent, get_system_prompt
debounce.init(..., system_prompt_getter=get_system_prompt)
```

---

## 4. 第四條規則：production hot-path 禁 bare `except Exception`

### 為何

`except Exception` 會吞掉 `NameError` / `AttributeError` / `TypeError` 等 programming bug，typo 不會在 dev 期間被抓到。production 真正需要的是：

- **DB I/O 失敗** → graceful 降級
- **LLM call 失敗** → retry / fallback
- **JSON 解析失敗** → 默認值

programming bug 應該直接拋出，讓 dev / test 抓到。

### 強制範圍

```
agent/{harness,quality}/   # production hot-path
api/services/              # business logic
data/pipeline/             # ETL（雖然失敗可恢復，但仍應分型別）
```

**不掃**：`scripts/`（一次性 CLI，過寬可接受）、`core/`（best-effort cleanup 多半是合理的）。

### 標準型別 tuple

```python
# DB I/O
except (psycopg.Error, OSError, RuntimeError) as e:

# LLM / HTTP call
except (RuntimeError, ValueError, TimeoutError, ConnectionError) as e:

# JSON parse
except (json.JSONDecodeError, ValueError, TypeError):

# JWT decode (jose)
except JWTError:

# 用戶程式碼防禦（state read 等）
except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError):
```

### 例外標記

`# noqa: BLE001` 寫在違反行行尾。**必填理由註解** 在前後行說明為什麼故意吞。

範例（已存在於 codebase）：

```python
except Exception:  # noqa: BLE001
    logger.exception("ws publish refund.decision failed (non-fatal)")
```

---

## 5. CI 守護（lint workflow 三劍客）

| Workflow | 範圍 | 例外標記 | 對應 PR |
|----------|------|----------|--------|
| `db-conn-lint.yml` | `agent/**` 禁直接 `AsyncConnection.connect()` | `# allow-direct-conn` | （v1.22.x 既有） |
| `reverse-import-lint.yml` | `agent/{skills,core,harness}` 三條反向規則 | `# allow-rev-import` | #28 |
| `bare-except-lint.yml` | `agent/{harness,quality}` + `api/services` + `data/pipeline` | `# noqa: BLE001` | #28 |

均為純 bash + grep，無 Python 依賴。違規時 CI 紅燈含建議修法。

---

## 6. 例外處理流程

新增違規（非預防性的「真的需要反向 import / 真的需要 wide except」），步驟：

1. **先試替代方案**：dependency injection / 下沉 helper / typed tuple
2. **真不行才寫 noqa**：必須附 1 行註解說明 *為何* 故意違反
3. **PR 描述加說明**：為何這個違反是必要的，未來什麼條件下可以收掉

每個 noqa 都是技術債的書面承諾。Reviewer 看到 noqa 應該問：「這個 case 沒有不違反規則的方法嗎？」

---

## 7. 與 RP2.1 的關係

**為何先做 RP2.2 / 2.3**：RP2.1 要把 `harness/debounce.py` 拆成 4-5 個 module（`BufferStore` / `quick_reply` / `orchestrator` / `debounce`）。如果開拆時還有反向 import，每個新 module 都要繼承這些 cycle，越拆越糾纏。

**現況**：dev tip `01fe197+` 兩條反向 import 為零，三個 lint 守護就位。RP2.1 啟動時可以放心拆。

**RP2.4 / 2.5 為何不在這一輪**：兩者技術上可在 RP2.1 之前做，但會在 `debounce.py` 內動修，之後 RP2.1 拆分時會被搬移，造成 churn。等 RP2.1 把它們拆出來再做，省一輪重工。

---

## 8. 可選：未來導入更全面的工具

- **`ruff`** rule `BLE001`（blind-except）/ `TID252`（banned imports）：可取代當前 shell-based lint，但需先評估其他 ruff 規則是否會大量警告
- **`pydeps`** 自動生成依賴圖：`uv add --dev pydeps && uv run pydeps agent/ --max-bacon=2 --noshow -o .reports/pydeps.svg`
- **`import-linter`**：用 contract 定義分層規則，比 grep 更精確（可區分 `from agent` vs `from agent.X`）

導入時序：等規則 1-4 跑半年後若無新需求再評估，避免過度工程。

---

## 9. 當前依賴快照（dev tip `01fe197+`）

由 `agent/` 樹的 import 自動擷取（top-level layer → top-level layer）：

```
skills     → core
harness    → core, skills
quality    → core, harness, llms, skills
agent.py   → core, skills
app.py     → core, harness, llms, memory, profiles, storage
```

✅ 三條分層規則全綠：
- `skills → harness`：無
- `core → harness/skills`：無
- `harness → agent`：無

> 提示：`harness → skills` 是允許的（middleware 知道有哪些 tools，正向依賴）。
> `app.py` 多向 fan-out 也合理（app 是 composition root，要組所有依賴）。

---

## 10. 版本紀錄

| 日期 | 版本 | 變更 |
|------|------|------|
| 2026-05-07 | v1.0 | 初版 — 收斂 PR #23/#24/#25/#28 為一份 ADR，附當前依賴快照 |
