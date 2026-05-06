# documentation-specialist 報告 — E6x 專案結構指南同步

- **日期**: 2026-05-06 15:21
- **任務**: 將 `docs/02-design/E6x--project-structure-guide.md` 對齊 Wave 2 一致性矩陣（U1-U10, U15-U17）
- **範圍**: 單檔 `docs/02-design/E6x--project-structure-guide.md`（v3.0 → v3.1）

## 結論

### 改了什麼

1. **U1, U2 — uv workspace（新章節 3.1）**：頂層目錄結構新增 `pyproject.toml` / `uv.lock` / `.python-version`；新增「3.1 uv Workspace 結構」小節說明 4 個 pyproject.toml 的職責與選 uv 的三個理由（單一 lock、快速切換、CI 一致性）；明確標註 `pip install -r requirements.txt` 已淘汰，請改用 `uv sync`。
2. **U5-U8 — scripts/ 子目錄分類（新章節 4.10.2）**：移除 line 120 過時的 `agent/scripts/`；新增 `scripts/{dev,env,ci,deploy}/` 分類表並連結回 `scripts/README.md`；補 `tests/smoke/api.sh` 煙測指令範例（含 `ADMIN_EMAIL`/`ADMIN_PASSWORD` 環境變數）。
3. **U9 — 除錯工具路徑（4.10.1 + 附錄 A）**：附錄 A「我想要...」表中所有 `scripts/view_*.py` 改為 `tests/tools/view_*.py`；新增 4 條操作指引（simulate_e2e、clean_data、env 切換、dev-up、Cloud Run 部署、API 煙測）；新增跨平台執行表（Linux/macOS shebang vs pyenv vs uv run vs Windows）。
4. **U15 — harness/ 大改寫（4.3 章）**：頂層目錄樹從 8 層子目錄（task/、context/、governance/、feedback/、safety/、observability/、entropy/）改為 8 個扁平 middleware 檔案（debounce.py、multimodal.py、data_correction.py、line_ui_factory.py、profile_updater.py、memory_manager.py、safety_gate.py、output_validator.py + media_storage/）；4.3 主體改寫為「實際結構 + middleware 觸發順序與成本表 + 設計原則」；標註 H8 audit log 漂在 debounce.py 內部、L4 由 memory/+profiles/ 承擔；附歷史脈絡備註說明 SKILL-based ReAct agent 取代了早期 task_decompose() 方案。
5. **U16 — Gold→SKILL 命名（4.8 章 + 頂層目錄樹）**：4 處 `silver_to_gold/` 改為 `silver_to_skill/`；Medallion 表格新增「Skill (Gold)」層描述產物為 SKILL.md；補命名說明備註解釋為何用 silver_to_skill 而非 silver_to_gold。
6. **U17 — registry pattern 精確化（4.6 章）**：原文僅說「config.toml [llm].provider 切換」是錯誤抽象，已改寫為 4 種變體對照表：LiteLLM 字串前綴路由（llms/）、dict registry（memory/, storage/）、直接 export（embeddings/）；說明各自為何如此選擇。
7. **連帶清理（第 2.5 節 + 附錄 A）**：「可預測性」範例從 `harness/task/problem_card.py` 改為 `agent/skills/data/.../SKILL.md`；附錄 A「新增知識資產」改為 `agent/skills/data/{Brand}/{Model}/SKILL.md`。
8. **frontmatter**：版本 v3.0 → v3.1；最後更新 2026-04-04 → 2026-05-06；補 v3.1 變更摘要 callout。

### Top 3 對比

| # | 修改前 | 修改後 |
|---|--------|--------|
| 1 | `harness/{task,context,governance,feedback,safety,observability,entropy}/` 8 層子目錄結構（包含 task/knowledge/sop/, fault_trees/, OCAP rules 等大量歷史細節） | 8 個扁平檔案（debounce.py 為編排核心、其餘 7 個為被呼叫的純函式或 task）+ middleware 觸發順序與成本表 |
| 2 | `agent/llms/` 描述為「`get_llm(config) factory`」+ 三檔（vertexai_model.py, gemini_model.py, ollama_model.py）+「透過 provider 切換」 | LiteLLM 字串前綴路由（`vertex_ai/gemini-2.5-pro`），不是 dict registry 但同樣 config-driven；對照 memory/ 與 storage/ 是 dict registry、embeddings/ 是直接 export — 3 種變體有不同正當理由 |
| 3 | `silver_to_gold/  # Vector embedding -> pgvector write`（Medallion Gold 層） | `silver_to_skill/  # Classify -> SKILL.md draft -> approve_drafts.py`（Skill (Gold) 層產出 SKILL.md，由 approve_drafts.py 人工審核閘門） |

## 行動項目

- [ ] **跨文件同步檢查**：本檔仍保留少量歷史 V1 設計描述（line 547 V1↔V2 整合點、line 739-810 第 7.3/7.6 節列出的 harness/task/knowledge/ 知識資產、prompts、taxonomy），已由 4.3 章末加註「歷史脈絡」說明取代關係，不再修改。其他 Wave 2 文件如有引用 harness/task/，建議由 documentation-specialist 統一處理。
- [ ] **連結驗證**：4.10.2 中加入 `scripts/README.md` 相對連結 `../../scripts/README.md`，建議下次跑 link checker 驗證。
- [ ] **K1-K7 鐵律未動**：依任務指引保留所有「鐵律」敘述，無變更。

## 影響評估

- **嚴重度**: MEDIUM
- **影響範圍**:
  - 所有閱讀 E6x 的新成員（onboarding 不再被「8 層 harness 子目錄」誤導）
  - 引用 E6x 的下游文件（建議 Wave 2 其他 agent 同步檢查 harness/、silver_to_gold/、scripts/view_*.py 殘留引用）
  - CI 流程文件（scripts/{dev,env,ci,deploy} 分類已成事實，E6x 現為 SSOT 描述之一，與 `scripts/README.md` 互補）
- **無破壞性**: 文件調整不影響任何程式碼或部署流程；frontmatter 版本升至 v3.1 反映實質結構變更。
