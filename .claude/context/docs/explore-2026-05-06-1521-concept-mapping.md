# R4 — Code↔docs 概念對應地圖

- **日期**: 2026-05-06 15:21
- **任務**: 建立 docs 機制描述 ↔ code 實作的概念層級對應
- **範圍**: CLAUDE.md, harness-architecture.md, E6, E3 中提到的所有 H 層機制
- **嚴重度**: LOW
- **影響範圍**: 無（25/25 機制完全對應）

## 結論

### 統計
- ✅ **一致**: 25/25 (100%)
- ⚠️ **漂移**: 0
- ❌ **缺一**: 0

### 對應表（核心交付）
所有 25 個重點機制（涵蓋入口層、緩衝層、攔截層、執行層、驗證層、清理層、審計層、技能系統、用戶資料、背景任務）在 docs ↔ code 的：
- **用詞**完全對齊（H6 = safety_gate.py、H_DC = data_correction.py、H_QR = line_ui_factory.py）
- **步驟順序**完全對齊（CLAUDE.md Request Processing Flow 與 debounce.agent_and_reply() 執行序一致）
- **技術細節**完全對齊（buffer_wait 1.5s、SCD2 CTE、Skill 兩階段載入）

### 完整對應清單
| 機制 | docs 來源 | code 位置 |
|------|----------|----------|
| LINE webhook | CLAUDE.md:132 | agent/app.py:@app.post("/webhook") |
| Sticker 直接回應 | CLAUDE.md:133-134 | agent/app.py:245-249 |
| 多模態 media_pending | CLAUDE.md:134-135 | agent/app.py:252-274, debounce.py:268-269 |
| Debounce buffer (H3) | CLAUDE.md:138-139 | harness/debounce.py:867-908 |
| 安全閘 H6 | CLAUDE.md:140 | harness/safety_gate.py |
| #資料修正 H_DC | CLAUDE.md:141-142 | harness/data_correction.py:98-147 |
| Quick Reply H_QR | CLAUDE.md:143-144 | harness/debounce.py:502-644 + line_ui_factory.py |
| Profile updater H4 | CLAUDE.md:145 | harness/profile_updater.py:146-220 |
| Memory compression H5 | CLAUDE.md:159 | harness/memory_manager.py:65-174 |
| Output validator H7.5 | CLAUDE.md:153 | harness/output_validator.py:79-143 |
| Audit log H8 | CLAUDE.md:155-156 | harness/debounce.py:474-499 |
| Skill 兩階段載入 | CLAUDE.md:174-175 | skills/__init__.py:104-128 + debounce.py:308-309 |
| Brand gate | CLAUDE.md:231 | skills/tools.py:102-114 |
| update_user_info | CLAUDE.md:241-242 | skills/tools.py:159-239 |
| Checkpoint cleanup 多模態 | CLAUDE.md:204-206 | harness/debounce.py:404-416 |
| Checkpoint cleanup tool_calls | CLAUDE.md:204-206 | harness/debounce.py:419-471 |
| SCD2 facts | CLAUDE.md:246 | profiles/manager.py:129-149 |
| Profile fact extraction | CLAUDE.md:248 | harness/profile_updater.py:166-200 |
| Health endpoint | app.py:185-206 | agent/app.py:185-206 |
| Auto-reconnect | CLAUDE.md:270 | profiles/manager.py:10-30 |
| Skill 動態注入 | CLAUDE.md:149 | harness/debounce.py:308-309 |
| Profile 注入 | CLAUDE.md:149-150 | harness/debounce.py:301-339 |
| Memory 摘要注入 | CLAUDE.md:150 | harness/debounce.py:318-322 |
| 品牌自動推論 | CLAUDE.md:148 | harness/debounce.py:284-298 |
| Multimodal 背景下載 | CLAUDE.md:134-135 | agent/app.py:303-317 |

## 行動項目

### 給 Wave 2
- [ ] **無 docs 改動需要**（微觀機制層全部對應）
- [ ] R1 R3 提到的「高層架構描述漂移」（multi-agent / L1-L8 / Gold→SKILL）才是真正要改的範圍

### 警示給未來
- 新增 H 中介層時，必須同步 CLAUDE.md「Harness middleware layers」表
- 新增 tool 或 skill 時，必須同步 CLAUDE.md Tools 表

## 影響評估

- **嚴重度**: LOW（無漂移）
- **影響範圍**: 證明微觀機制的 docs↔code 對應健康度極佳，確認本次同步主戰場是高層架構描述（E3/E6x/E9）而非細節
