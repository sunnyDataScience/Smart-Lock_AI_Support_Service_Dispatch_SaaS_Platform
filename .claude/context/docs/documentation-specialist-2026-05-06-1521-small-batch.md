# documentation-specialist 報告

- **日期**: 2026-05-06 15:21
- **任務**: 同步 4 份設計文件以對齊 consistency-matrix-2026-05-06-1521.md（U3 / U7 / U17 / R3 / R4 / K7 判決）
- **範圍**:
  - `docs/02-design/agent-harness/knowledge-asset-review-checklist.md`
  - `docs/02-design/agent-harness/harness-architecture.md`
  - `docs/02-design/E5x--frontend-information-arch.md`
  - `docs/02-design/specs/README.md`

## 結論

- **knowledge-asset-review-checklist.md（U3）已修**：line 118 的 `cd agent && python3 -c "..."` 已改為從專案根執行的 `uv run python -c "..."`，並更新註解指明 `pyproject.toml` 取代 `requirements.txt`；validation script 內 `Path('harness/task')` 同步改為 `Path('agent/harness/task')` 以匹配新工作目錄。
- **harness-architecture.md 未修（合規）**：本檔為通用 Harness 理論文件（8 層理論框架），全文無 `pip install` / `requirements` / `conda` / `cd agent` / 舊 scripts 路徑命中。`registry` 一詞僅以「Tool Governance 層的通用概念」出現於 §4.3 與 §6 架構圖，**並非** U17 所指的 LLM/memory/storage 註冊機制（那屬 E3 / E6x agent 範疇），故無需精確化。R3 已認證 ReAct/Debounce 描述一致；R4 認證 H 編號對應健康；K7 議長判決 docs 維持 H_QR 為獨立中介層描述（不因 code 漂移而改）。
- **E5x--frontend-information-arch.md（U7）已修**：line 1165 的 `scripts/check-operationid-orphans.sh` 已加 `ci/` 子目錄；同步補上配套三道 CI 閘——`generate-api-types.sh --check`、`mock-server.sh`、`generate-mapping-api-index.sh`（PAGE META → MAPPING.md 雙向繫結），與 specs/README.md §CI 章節對齊。
- **specs/README.md 已修**：Mock Server 段落以 `./scripts/ci/mock-server.sh` 為方式 1 推薦入口，補上 `4010 --errors` 旗標說明（隨機回 4xx/5xx 測前端 error path），降階直接 `npx prism-cli` 為「不建議」備援；docker-compose 段落明確標註「僅供 local 多服務開發；生產環境統一走 Cloud Run」。OpenAPI types 生成段（line 71-73）原本已使用 `./scripts/ci/generate-api-types.sh` 並含 `--check` 說明，無需再修。
- **驗證通過**：四檔對 `pip install -r|conda (create|activate)|cd agent && python3` 與非 `/ci/` 路徑下的 `scripts/(check-operationid|generate-api-types|mock-server|generate-mapping)` 兩條 rg 規則均零命中。

## 行動項目

- [ ] 主 agent 將矩陣項 U3、U7 標為已關閉（在這 4 檔範圍內）；U17 在這批檔案內無命中，由 E3 / E6x agent 接手收尾。
- [ ] 確認 `scripts/ci/generate-mapping-api-index.sh` 實際存在於 repo（本次新增於 E5x §10.5 引用）；若尚未實作，由 deployment-expert 或 ops 補上骨架以避免文檔→現實漂移。
- [ ] 後續若 R3 / R4 重審 harness-architecture.md 中 §4.3 Tool Registry 與專案 LLM/memory/storage registry 的命名衝突，可考慮在 §11「本專案的落地實作」對照表加一行「registry 一詞在本專案的雙重含義」說明（目前不需）。

## 影響評估

- **嚴重度**: LOW
- **影響範圍**:
  - 文件層：4 檔內部一致性，與 specs/README.md、scripts/ci/ 目錄結構、E3/E6x agent registry 描述對齊
  - 開發者體驗：知識資產驗證腳本可直接從專案根 `uv run` 執行，無需再 `cd agent`；前端 CI 閘清單從 1 條擴為 4 條，覆蓋更完整
  - 不影響 code、不影響其他 docs、不變更 5D 結構與章節編號
