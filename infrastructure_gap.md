# agent/ vs agent_skills/ 基礎設施差異對照

## 核心架構

| 能力 | agent/ | agent_skills/ | 備註 |
|------|--------|---------------|------|
| Agent 模式 | 7 個專業 agent + router 分發 | 單一 ReAct agent + 14 SKILL.md | agent_skills 更簡潔 |
| Graph 結構 | 13 node pipeline + 3 conditional edge | `create_react_agent` 黑盒 | 不需遷移 |
| 知識來源 | pgvector RAG (6 collections) + 故障樹 | Markdown SOP (14 files) | 不同路線 |

## 基礎設施層（agent_skills/ 缺少的）

| # | 能力 | agent/ 位置 | agent_skills/ 現況 | 移植難度 |
|---|------|-------------|-------------------|----------|
| 1 | **Safety Gate (L6)** — PII 偵測、危險指令攔截、OCAP 情緒規則、緊急代碼 | `harness/safety/gate.py` | 只有 config 裡的 keyword list | ⭐ 直接搬 |
| 2 | **Tool Governance (L3)** — Pydantic 參數驗證、語意檢查、risk 分級 | `harness/governance/` | 無 | ⭐ 直接搬 |
| 3 | ~~**Audit Storage** — 操作事件持久化（SQLite/PostgreSQL）~~ | `storage/` | ✅ 已搬移至 `agent_skills/storage/`，debounce + app.py 已整合 | ✅ 完成 |
| 4 | ~~**LLM Registry** — 統一 provider 切換 (ollama/gemini/vertexai)~~ | `llms/` registry pattern | ✅ 已搬移至 `agent_skills/llms/` | ✅ 完成 |
| 5 | ~~**Embedding Registry** — 向量模型抽象~~ | `embeddings/` | ✅ 已搬移至 `agent_skills/embeddings/` | ✅ 完成 |
| 6 | ~~**Memory 持久化** — SQLite/PostgreSQL checkpoint~~ | `memory/` registry pattern | ✅ 已搬移至 `agent_skills/memory/`，app.py/main.py 已整合 | ✅ 完成 |
| 7 | ~~**User Profile** — SCD Type 2 用戶事實追蹤~~ | `profiles/manager.py` | ✅ 已搬移至 `agent_skills/profiles/`，config + app.py 已整合 | ✅ 完成 |
| 8 | **Message Bus** — agent 間訊息記錄 | `messaging/bus.py` | 無（單 agent 可能不需要） | ⭐ 直接搬 |
| 9 | **ProblemCard** — 問題追蹤 dataclass + DB 持久化 | `domain/problem_card.py` | 無 | ⭐ 直接搬 |
| 10 | **DiagnosticStateMachine** — 診斷狀態機 | `domain/diagnostic_state_machine.py` | 無 | ⭐ 直接搬 |
| 11 | ~~**Debounce** — LINE 快速連發訊息合併~~ | `core/debounce.py` | ✅ 已搬移至 `agent_skills/core/debounce.py`，app.py 已整合 | ✅ 完成 |
| 12 | ~~**Multimodal** — 圖片/語音/影片→文字（Gemini Flash-Lite）~~ | `core/multimodal.py` | ✅ 已搬移至 `agent_skills/core/multimodal.py`，四路訊息處理 | ✅ 完成 |
| 13 | ~~**Media Storage** — 媒體檔案存儲抽象 (local/gcs/s3)~~ | `core/media_storage/` | ✅ 已搬移至 `agent_skills/core/media_storage/` | ✅ 完成 |
| 14 | **Observability (L7)** — session 指標 + 結構化 trace | `harness/observability/` | 只有 print | ⭐⭐ 需適配 |
| 15 | **Token Budget (L2)** — session token 用量追蹤 + 上限 | `harness/context/budget.py` | 無 | ⭐⭐ 需適配 |
| 16 | **Context Freshness (L2)** — RAG 來源新鮮度評分 | `harness/context/freshness.py` | 無（不用 RAG，暫不需要） | ⭐⭐ 需適配 |
| 17 | **Answer Verification (L5)** — LLM 品質評分 + retry | `harness/feedback/verifier.py` | 無 | ⭐⭐ 需適配 |
| 18 | **Entropy/SOP Generator (L8)** — 新案例偵測 + SOP 草稿生成 | `harness/entropy/` | 無 | ⭐⭐ 需適配 |
| 19 | **Task Decomposer (L1)** — 4 層因果鏈診斷推理 | `harness/task/decomposer.py` | 無 | ⭐⭐⭐ 需大幅適配 |
| 20 | **Knowledge Assets (L1)** — 症狀表/故障分類/故障樹 | `harness/task/taxonomy/` + `knowledge/` | 知識全在 SKILL.md 裡 | ⭐⭐⭐ 架構不同 |

## 業務服務（agent/services/，~14,882 行，零 agent 耦合）

| # | 服務 | 檔案位置 | 用途 |
|---|------|----------|------|
| 21 | **Auth/RBAC** | `services/auth/rbac.py` | RBAC 權限（7 角色） |
| 22 | **Dispatch Matcher** | `services/dispatch/matcher.py` | 技師配對（技能/距離/評分） |
| 23 | **Pricing Engine** | `services/pricing/engine.py` | 報價引擎 |
| 24 | **Warranty Claims** | `services/warranty/claims.py` | 保固查詢 |
| 25 | **Work Order** | `services/work_order/exception.py` | 工單異常處理 |
| 26 | **Technician Rating** | `services/technician/rating.py` | 技師多維評分 |
| 27 | **Complaint CRM** | `services/complaint/lifecycle.py` | 客訴生命週期管理 |
| 28 | **Inventory** | `services/inventory/manager.py` | 庫存管理 |
| 29 | **Finance/Refund** | `services/finance/refund.py` | 退款審批 |
| 30 | **Consent/Signature** | `services/consent/signature.py` | 電子簽名 + 到場確認 |
| 31 | **Dispute Evidence** | `services/dispute/evidence.py` | 爭議舉證包組裝 |
| 32 | **Completion Evidence** | `services/completion/evidence.py` | 完工舉證鏈 |
| 33 | **Data Export** | `services/export/exporter.py` | 資料匯出 |
| 34 | **Brand Data Upload** | `services/brand/data_upload.py` | OEM 資料上傳 |
| 35 | **Realtime Messaging** | `services/messaging/realtime.py` | 即時通訊 + WebSocket |

## 移植難度說明

- ⭐ **直接搬** — 零耦合，複製後改 import 即可
- ⭐⭐ **需適配** — 有 GraphState 或路徑依賴，需 10-50 行重構
- ⭐⭐⭐ **需大幅適配** — 架構假設不同，需重新設計整合方式
