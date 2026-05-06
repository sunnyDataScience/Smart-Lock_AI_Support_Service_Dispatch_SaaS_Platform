# R1 — 分層與模組邊界審查（架構審查官）

- **日期**: 2026-05-06 15:21
- **任務**: 審查 agent/api/data/web 四模組與 harness 中介層的依賴方向、registry pattern、跨模組耦合
- **範圍**: 全專案 import 圖 + docs E3/E6x/E9 + harness-architecture.md
- **嚴重度**: HIGH
- **影響範圍**: docs（E3/E6x/E9 高層架構描述需重寫）、code（harness/debounce.py 重構候選）

## 結論

### 核心發現
1. **物理模組邊界乾淨**：agent ↔ api ↔ data ↔ web 之間零直接 import，靠 PostgreSQL 與 HTTP 解耦，與部署設計（兩個 Cloud Run service）一致
2. **Harness 內部方向性漂移**：debounce.py 是 god-orchestrator（818 行，承擔 H3 + H_DC + H_QR + H6 + H7.5 + H8 編排），其餘 7 個 harness 檔案彼此正交
3. **2 條反向耦合**：
   - `agent/harness/debounce.py:24` 反向 import `agent.get_system_prompt`
   - `agent/skills/tools.py:10` 反向 import `harness.line_ui_factory.match_brand/match_model`
4. **docs 三處嚴重落後**：
   - E6x 描述 `agent/agents/`（7 sub-graphs）、`harness/{task,context,governance,...}/`（L1-L8 子目錄）— **實際不存在**
   - E3 §1.3 / §3.3 同樣繪製 7-agent subgraph + L1-L8 — 與實作差距巨大
   - E9 描述 nginx + docker-compose + alembic — 實際是 Cloud Run + scripts/deploy + 無 alembic
5. **Registry pattern 健康度不一致**：
   - storage/ ✅ 純 dict registry
   - memory/ ⚠️ if/else fast-path + dict registry 混用
   - llms/ ⚠️ 完全沒 registry dict（靠 LiteLLM 字串路由）

### 違例清單
| # | 位置 | 違反什麼 | docs 怎麼說 | 議長判決 |
|---|------|---------|-----------|---------|
| 1 | `agent/skills/tools.py:10` | 領域層反向依賴中介層 | 沒提 | code 重構（不本次） |
| 2 | `agent/harness/debounce.py:24` | harness import agent root | 期望相反 | code 重構（不本次） |
| 3 | `harness/debounce.py` 多職 | H_QR 應獨立檔 | docs 把 H_QR 列為獨立中介層 | code 重構（不本次） |
| 4 | E6x §"agent/agents/"、L1-L8 | docs 描繪不存在的結構 | docs 自身 | **docs 落後 → 重寫** |
| 5 | E3 §1.3/§3.3 同上 | 同 #4 | 同 #4 | **docs 落後 → 重寫** |
| 6 | E9 nginx/compose 描述 | 實際 Cloud Run | docs 自身 | **docs 落後 → 重寫** |
| 7 | llms 無 registry dict | docs 稱「registry」 | CLAUDE.md 用 registry 概述 | 雙輸（docs 描述要精確化） |
| 8 | memory 混 if/else + dict | 同上 | 同上 | code 小瑕（不本次） |

## 行動項目

### 給 Wave 2（本次同步 docs）
- [ ] **E3** §1.3 / §3.3 重寫架構圖：移除 7-agent subgraph，改為 single ReAct + 3 tools + 8 個 harness 中介層（扁平）
- [ ] **E6x** 移除 `agent/agents/`、`harness/{L1-L8}/` 子目錄描述；改為實際的 8 個 harness 平行檔案
- [ ] **E9** 移除 nginx/docker-compose 範本；改為 Cloud Run + scripts/deploy/{agent,api}.sh runbook
- [ ] **CLAUDE.md/E3/E6x** 的 registry 描述精確化：明示 storage = dict registry、memory = 混合、llms = LiteLLM 字串路由（非傳統 registry）

### 給後續 code 重構（不本次）
- [ ] 把 `match_brand/match_model` 從 harness/line_ui_factory.py 抽到 `agent/core/brand_match.py`，斷開 skills→harness 反向
- [ ] `get_system_prompt` 改為由 app.py 在 init() 注入到 harness，斷開 harness→agent 反向
- [ ] 把 H_QR 暫存（_pending_messages）從 debounce.py 抽到 `harness/quick_reply.py`，debounce 只做 buffer 合併
- [ ] memory/__init__.py 統一用 dict registry，移除 if/else fast-path

## 影響評估

- **嚴重度**: HIGH（docs 高層架構描述與實作差距大，新成員依 docs 會迷路）
- **影響範圍**: docs E3 / E6x / E9（重寫架構章節）；code agent/harness/debounce.py（god-class，列入下一輪重構分支）
