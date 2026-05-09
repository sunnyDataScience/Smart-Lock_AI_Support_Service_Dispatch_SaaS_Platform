# 整合紀錄：Sunny Weng 5/6-5/8 工作 port 至 Zenobia0000 (`2825cbe`) 基底

**整合日期**：2026-05-09
**整合分支**：`integrate/sunny-onto-zenobia0000-20260508`
**最終 push**：原計畫推到 `Zenobia000/dev` 覆蓋 `0862583`（待 push）
**對應 ADR**：[ADR-008 product-info architecture canonical](../../../docs/01-define/adrs/adr-008-product-info-architecture-canonical.md)

---

## 0. TL;DR — 給「下一個接手的 AI 或人類」

讀完本文件你會知道：

1. 為什麼 dev 在 5/9 被改寫，且為什麼這不是 force-push 的災難而是**團隊拍板的整合**
2. 哪些 Sunny 的工作**有**進來，哪些**沒有**進來
3. 你接續開發時要避開的雷區（不要再搞 architecture revert）

**最簡規則**：

- ✅ 在當前 dev tip 上開新 branch 做你的事
- ✅ 沒事不要動 `agent/skills/`（它已經不存在，以後也不該再存在）
- ✅ 任何「想 cherry-pick Sunny 5/6-5/8 沒被 port 的工作」必須**先在 ADR 補一條論證**才動手
- ❌ 不要因為 git log 看到「restore(agent): skills/ as canonical」這類 commit 就以為架構回退是當前方向

---

## 1. 時序紀錄（5/6 ~ 5/9）

```
2026-05-06
  21:52  Imding1211: merge sync Zenobia0000/dev → Zenobia000/dev (e2d1476)
  22:13  Imding1211: restore agent → Zenobia0000 (4c61508)
  22:14  Imding1211: full alignment → Zenobia0000 dev tip 2825cbe (8ffcb60)
  22:15  Imding1211: clean up tests/unit/core/* (56949eb)
  22:25  Imding1211: 刪除 Zenobia000 上 12 個 refactor/* 遠端分支

  ────────── 20 分鐘後，協作者 Sunny Weng 開始反向操作 ──────────

  22:45  Sunny: 30e5ff1  restore(agent) Phase 1 helper modules from 6c2616c
  22:57  Sunny: merge PR #17 restore/phase1-cherry-pick
  22:58  Sunny: d000238  restore(agent) skills/ as canonical, drop agent_tools/
  23:00  Sunny: merge PR #18 restore/phase1-skills-naming
  23:08  Sunny: 9f136ee  restore Dockerfile multi-stage uv + pyproject.toml
  23:15  Sunny: merge PR #19 restore/phase1-finishing
  00:03  Sunny: 8a2f26b  Phase C+ followups — wire skills, drop product_info（5/7 凌晨）

2026-05-07 ~ 5-08
  Sunny 在「重新引入的 skills/ 架構」上做 137 個 commits：
    - RP2.x 重構（解耦反向 import、except cleanup、scripts 整併）
    - RP3.x 重構（debounce 拆檔 + F2 系列：buffer/quick_reply/orchestrator/...）
    - F-004 / F-008 / F-010 / F-016 / F-019 後端功能
    - web 大量 UI 升級（Modal lib / DateRangePicker / ReportExportModal / dark mode 等）
    - 5/8 16:32 V1.5+ 通知 channel 抽象層

2026-05-09
  00:35  Imding1211：團隊決議以 Zenobia0000 (2825cbe) 架構為主，
         開 integrate/sunny-onto-zenobia0000-20260508 分支整合
  ~04:00 (預估 push) 整合完成、push 至 origin/dev 覆蓋 0862583
```

---

## 2. 整合分支的 8 個 commits（從 `2825cbe` 起）

```
1ae6646 integrate(deps): add structlog + holidays to agent/requirements.txt
65180eb integrate(agent-notifications): port V1.5+ notification channel abstraction
2b4240e integrate(agent-core): port architecture-neutral core/ helpers
b260396 integrate(docs): port Sunny docs (test plan, ADR, BDD, PM align, design specs)
d27c8b9 integrate(infra): port Sunny test infra + CI workflows + scripts reorg
a6a6349 integrate(sql): port Sunny SQL schema additions
d282da8 integrate(api): port Sunny api/ work onto Zenobia0000 base
adcff38 integrate(web): port Sunny 5/6-5/8 web/ work onto Zenobia0000 base
```

整合規模：**320 檔變更，+34237 / -5289 行**。

---

## 3. 哪些 Sunny 工作**有**進來

### 3.1 web/（102 檔）

- A1 404/500/global-error pages + offline banner
- A2 Modal/Drawer/Toast library（Radix UI）
- A3 DateRangePicker + dashboard/reports wiring
- A4 handover chat composer + sendChatMessage UI
- A5 exportAuditEvents CSV modal
- F-004 manualAssign UI / F-008 scope-change 同意頁
- F-010 reschedule UI / F-016 SLA Soft alert banner / F-019 RBAC 動態
- ReportExportModal + 4 page wires + V1.1 PDF radio
- Dark mode（light/dark/system + ThemeProvider + ThemeToggle）
- 客戶 admin 表單 + 消費者追蹤頁（`/pool`, `/my-orders`）

### 3.2 api/（47 檔）

- F-004 manualAssign dispatcher RBAC + 客服繞過 audit log
- F-008 HMAC token + scope_change_service
- F-010 改約/延遲 3 ops + LINE Push 真實串接
- F-016 SLA Soft alert（Q5=B 拍板）
- F-019 RBAC 動態調整
- exportReport PDF（reportlab）+ accounting report_type
- exportAuditEvents endpoint
- sendChatMessage handover endpoint

### 3.3 SQL/（6 檔）

- `Schema_rbac_dynamic.sql`、`Schema_media.sql`、`Schema_tech_schedule.sql`、`Schema_work_order_events.sql` 等

### 3.4 tests/、scripts/、.github/（59 檔）

- Playwright e2e config + dep + tests/fixtures/factories
- tests/contract OpenAPI fuzz + AsyncAPI envelope validators
- CI workflows（test-suite / reverse-import-lint / bare-except-lint）
- scripts/setup → scripts/dev 整併、scripts/ → scripts/ci 整併
- Makefile 統一入口

### 3.5 docs/（55 檔）

- E7x test plan and readiness roadmap
- ADR-007 LLM registry pattern
- BDD scenarios sync + PM Q1-Q10 alignment
- §4 cross-doc gaps 補完

### 3.6 agent/notifications/ 全 10 檔

- `ChannelAdapter` ABC + registry + router + bootstrap
- adapters/{line, sms, email, fcm}.py（LINE 真實，其他 V1.5+/V2.0+ stub）
- `agent/app.py` startup 加 `register_default_channels()` 在 `line_bot.init` 之後

### 3.7 agent/core/ 4 個架構中立 helper

- `logging_config.py`（structlog）— 被 notifications/ 5 檔引用
- `content_utils.py`（`extract_text`）— 被 tests/unit/core 引用
- `pg_pool.py`（`_ensure_conn`）— 被 tests/unit/core 引用
- `workday.py`（工作日計算）— 被 tests/unit/core 引用

### 3.8 agent/requirements.txt

新增 `structlog` + `holidays` 兩個依賴。

---

## 4. 哪些 Sunny 工作**沒有**進來（「why not」說明）

### 4.1 架構回退本身（10 個 commits）— **不採納**

- `30e5ff1, 358d848, b70b0e5, d000238, 84e9f4e, 91b73e3, 9f136ee, 360d372, 8a2f26b, 513c830`
- 這些 commits 把 `agent/skills/` 從 `6c2616c` 拉回，刪除了 `agent_tools/` 與 `product_info/`
- 違反 [ADR-008](../../../docs/01-define/adrs/adr-008-product-info-architecture-canonical.md)，全數捨棄

### 4.2 RP2.x 重構部分（保留版面，但實際結構不同）

| Sunny 工作 | 整合分支處置 |
|---|---|
| RP2.2 `core/brand_match.py` 解耦 | **不採納** — `2825cbe` 的 `harness/line_ui_factory` 已內含 brand state，引入會雙寫 |
| RP2.3 debounce 移除反向 import | 自然成立 — `2825cbe` 的 debounce 本來就沒這個反向 import |
| RP2.6 except Exception 收斂（46 處）| **未套用** — 留為後續清理任務 |

### 4.3 RP3 harness modularization（全部不 port）

- `agent/harness/{buffer, quick_reply, orchestrator, skills_prefix, brand_resolver, validator_pipeline, checkpoint_cleanup, agent_audit}.py`
- 這些都是 Sunny 在「重新引入的 skills/」架構上做的拆檔優化
- `2825cbe` 的 product_info 平面架構不需要這些 wrapper（debounce.py 在 2825cbe 是 240 行，本來就乾淨）
- 強行 port 會造成 ImportError（相依 `skills/tools` / `core/blocks` 等）

### 4.4 不採納的 helper

- `agent/core/blocks.py` — 只 RP3 harness 拆分用
- `agent/core/brand_match.py` — 雙寫風險
- `agent/core/tracing.py` — 只 Sunny 版 app.py 使用
- `agent/pyproject.toml` — 採用 `requirements.txt` 路線
- `agent/Dockerfile` (multi-stage uv) — 採用單階段 pip 路線

### 4.5 F-* features 的 agent/ 端

F-004 / F-008 / F-010 / F-016 / F-019 commit 標 `feat(api,agent)` 但實際**只動 api/**，agent/ 端無改動需要 port。

---

## 5. 驗證紀錄（2026-05-09）

### 5.1 結構驗證

```
✓ agent/agent_tools/      (架構正典)
✓ agent/product_info/     (41 份 mega-doc, 7 brands)
✓ agent/notifications/    (V1.5 prep, port 自 Sunny)
✓ agent/core/logging_config.py / content_utils.py / pg_pool.py / workday.py
✓ agent/requirements.txt  (含 structlog + holidays)
✗ agent/skills/           (不存在，符合)
✗ agent/pyproject.toml    (不存在，符合)
```

### 5.2 import 健康度

```bash
$ grep -rn "^from skills\|^import skills" agent/ --include="*.py" | grep -v __pycache__
# 0 hits
```

### 5.3 quality_check（67 案例 / `--no-judge`）

```
Total:   67
Pass:    62  (93%)  ← 達標 ≥ 90%
Partial: 4   (6%)
Fail:    1   (1%)   ← E-8 預約安裝（用詞偏差，非邏輯錯）
Error:   0   (0%)   ← 無 import / runtime error
```

### 5.4 web e2e（28 個主要管理頁）

```
28/28 全部 200，無 uncaught error，無 5xx
```

---

## 6. 給接手者的具體指引

### 6.1 你想新增功能

```bash
git checkout dev      # 確認在最新 dev tip
git pull              # 取最新
git checkout -b feat/your-feature dev
# 開始你的工作
```

agent/ 內新增程式碼時：

```python
from agent_tools.tools import load_product_info, update_user_info, transfer_to_human
from product_info import all_docs, filter_loadable
# ✓ 正確

# from skills import ...    # ❌ 違反 ADR-008
# from skills.tools import ...   # ❌ 違反 ADR-008
```

### 6.2 你想新增產品知識

撰寫一份新的 `agent/product_info/{Brand}/{Model}.md`，請參考 [product_info_authoring_guide.md](product_info_authoring_guide.md)。

**禁止**重新建立 `agent/skills/data/{Brand}/{Model}/skill-name/SKILL.md`。

### 6.3 你想吸收 Sunny 5/8 沒 port 進來的工作（如 RP3 模組化）

- 先讀 [ADR-008 §3 「為何不接受 skills/ 重新引入」](../../../docs/01-define/adrs/adr-008-product-info-architecture-canonical.md)
- 在 PR 中論證「對 product_info 架構的具體效益」（量化）
- 提出新 ADR-009 取代 ADR-008（若你的論證成立）
- **不要直接 force-push 改回去**

### 6.4 你交給 AI 助手做事前

- 把 [CLAUDE.md](../../../CLAUDE.md) 的「Architecture Lock」段（將於本次更新加入）跟本文件一起作為 context
- 明確告訴 AI：「使用 `product_info/` + `agent_tools/`，禁止引入 `skills/`」
- AI 看到舊 commit log 提到 skills 不要被誤導

---

## 7. 復原途徑（萬一決議錯了）

如果未來證實「skills/ 架構真的比較好」，可從以下任一點回復：

- `0862583` — Sunny 整合前最終 dev tip（含他完整 skills/ + RP3 工作）
- `2825cbe` — 本次整合基底（純 product_info / 無 Sunny 後續工作）
- `Zenobia0000` 倉庫的 dev — 永久備份的純 Zenobia0000 架構快照

reflog 與遠端 ref 都還在，**不是不可逆**。但反復震盪有重大成本，請慎重。
