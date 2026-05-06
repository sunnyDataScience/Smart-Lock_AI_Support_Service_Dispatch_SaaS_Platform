# Doc Agent E — WBS / ADR / Pre-flight 同步報告

- **日期**: 2026-05-06 15:21
- **檔案**:
  - `docs/01-define/E2x--wbs-project-schedule.md`（5 處編輯）
  - `docs/01-define/adrs/adr-001-backend-framework.md`（1 處編輯，加註）
  - underscored dirs：無命中、無編輯
- **矩陣條目**: U1-U10（U1 uv 遷移、U7 scripts/ 子目錄、U8 Cloud Run 部署腳本）在指定範圍的命中與處置

## Pre-flight 結果

- `_domain-knowledge/`: **no hits**
- `_gap-analysis/`: **no hits**
- `_meeting-minutes/`: **no hits**
- `_superseded/`: **no hits**

驗證指令：

```
rg -n -i 'pip install -r|conda (create|activate)|requirements\.txt|cd (agent|api|data) && python|scripts/(dev-up|dev-down|use-local|use-gcp|cloud-sql-proxy|deploy|generate-api-types|mock-server|check-operationid-orphans|view_|clean_data|simulate_e2e)' docs/_domain-knowledge docs/_gap-analysis docs/_meeting-minutes docs/_superseded
```

→ 0 行輸出。後續驗證指令（細項拆分後 grep）亦全 0。

結論：**underscored 目錄整體乾淨**，目前不含過時的 pip/conda/requirements.txt 指令、不含舊路徑的 `cd agent && python` 直呼、不含舊版 `scripts/{dev-up,view_,deploy}.sh` 路徑（這些都已是 `scripts/dev/` `tests/tools/` `scripts/deploy/` 等子目錄路徑）。

## 改了什麼

### `docs/01-define/E2x--wbs-project-schedule.md`（5 處）

1. **檔頭（line 11，新增）**：在 Phase 編號說明下方新增「工具鏈基線（2026-05 更新）」註記區塊，宣告 uv workspace + `scripts/` 子目錄結構，並指向 `scripts/README.md`。明確說明本變更不影響 WBS 任務範圍與交付物。
2. **1.1.0.4.2（line 98）**：「Docker 開發環境設定」→ 補上「uv workspace + `scripts/dev/dev-up.sh`」、交付物加上 `scripts/dev/`。
3. **1.1.4.1.1（line 233）**：Phase 4 部署任務「正式環境基礎設施建置（Docker 部署）」→ 改為「Cloud Run + `scripts/deploy/agent.sh` / `scripts/deploy/api.sh`」，反映目前實際部署機制。
4. **1.2.8.3.1（line 381）**：Phase 8 V2.0 部署任務 → 補上「沿用 `scripts/deploy/agent.sh` / `scripts/deploy/api.sh`」。
5. **1.3.3.3（line 437）**：貫穿型「Docker/IaC 設定維護」說明 → 補上「含 uv workspace `pyproject.toml` / `uv.lock`、`scripts/` 部署腳本」。

WBS 結構（Phase 編號、股權、週次、合約對照表）完全不動。

### `docs/01-define/adrs/adr-001-backend-framework.md`（1 處）

- **§5 執行計畫概要（line 100，新增註記）**：在原本「使用 Poetry 管理依賴」之上加一段更新註記區塊，說明 2026-05 遷移到 uv workspace、引用 commit 75c0a21 / e9ef158 與 `scripts/README.md`，明確聲明「本決策未變更框架選擇（仍為 FastAPI + Pydantic + SQLAlchemy 2.0），僅變更套件管理工具」。
- **§5 第 1 項（line 102）**：「使用 Poetry 管理依賴」→ 改為「使用 Poetry 管理依賴（已超越，現用 uv）」，保留歷史脈絡，標記已超越。

ADR 的 §1-§4（背景、選項、決策、後果）、§6（參考）、決策狀態、決策日期完全不動。

## 不改的決策

- **不寫新 ADR**：本次變更為依賴管理工具切換（pip/Poetry → uv），未變更框架選擇與架構決策，故不開新 ADR 編號（避免擾動 ADR-002~006 的引用）。改採 ADR-001 §5 內加註方式，保留決策歷史。
- **歷史敘述不改**：ADR-001 §5 第 1 項保留「Poetry」原文，僅加上「已超越，現用 uv」的標記註記，遵守「ADR 是決策歷史」的原則。
- **superseded 內容不動**：`_superseded/01_smart_lock_prd.md` 為已超越的 PRD，無需處理；pre-flight 也未在其中發現對舊指令的引用。
- **會議紀錄、gap-analysis 不動**：pre-flight 未命中，無待清理項目。

## 後續建議（給 Wave 3 主 agent）

- **D1（LLM registry 形式）是否新 ADR？**：**Defer / 建議後續開新 ADR**。
  - 矩陣條目 D1 涉及 `agent/llms/` 從 dict registry 改為 LiteLLM 字串路由（如 `"vertex_ai/gemini-2.5-pro"`），這是**架構層面的決策變更**（registry pattern 取捨），與本次「套件管理工具切換」性質不同。
  - 建議獨立開立新 ADR（暫名 `adr-007-llm-registry-pattern.md`），記錄：
    1. 為何從 dict registry 切換到 LiteLLM 字串路由
    2. 兩種 pattern 的取捨（型別安全 vs. 多 provider 切換成本）
    3. 與 ADR-003（LangChain 整合）、ADR-006（LLM 模型選擇）的關係
  - 本次任務範圍排除新 ADR 寫作，建議主 agent 在 `docs/_audit/code-architecture-review-{ts}.md` 中列入「待開新 ADR」清單，並指派給負責 Codebase architecture 的 agent。

- **進一步建議（不在本次範圍）**：
  - WBS Phase 9 之後若有「Phase 10 工具鏈現代化」對應任務，可新增 1.2.10 工作包記錄 uv 遷移 + scripts/ 重構，作為 retrospective WBS 補登。本次未動，因該議題尚未在 SOW 範圍內。
  - ADR-005（frontend framework v2）若有類似的 Poetry/pip 字眼，本次未掃描，建議由負責 frontend 的 doc agent 補查。

## 影響評估

- **嚴重度**: LOW
- **影響範圍**:
  - 文件層：WBS 與 ADR-001 的執行細節敘述同步至 2026-05 真實工具鏈狀態
  - 不影響：合約交付物、股權分配、Phase 邊界、ADR 決策實質內容
  - 不影響：任何 code、其他 docs、API spec
- **破壞性**：無
- **後續動作**：建議主 agent 在整合報告中觸發 D1 LLM registry 新 ADR 撰寫任務（獨立 wave 處理）
