# ADR-P013: Agent Configuration Studio（品牌自服務調校診斷系統）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state 理想態 v2）· §3.4 安全護欄待業主確認 |
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 關聯 | [[ADR-P009]]（配置層自服務化）· [[ADR-004]]（RAG 權限）· [[ADR-P008]]（prompt 屬編排）· [[ADR-P001]]（知識 HITL）· [[ADR-P003]]（RBAC）|

## 1. 背景與問題

現況診斷系統配置（skill / 知識 / prompt）為 FDE 專屬。業主要把三件事開放成**品牌方前端自服務**：
1. **Skill Registry**：品牌可在前端**匯入 + 修改** skill。
2. **RAG 知識庫權限管理**：前端決定**哪些 DB / 語料可開放檢索**。
3. **系統提示詞（system prompt）**：前端可修改調整。

核心張力：**自服務賦權 vs 安全/品質**——品牌改 prompt/skill 可能移除 escalation/domain-safety 或注入問題指令，直接影響真實客戶對話。

## 2. 考量的選項

- **A：維持 FDE 專屬**（不開放）— 安全，但品牌無法自主迭代、FDE 成瓶頸。
- **B：全開放前端編輯**（無護欄）— 賦權最大，但安全/品質失控。
- **C：Agent Configuration Studio（分層保護 + 版本化 + RBAC + 選配 HITL）** — 自服務但受治理。

## 3. 決策

採 **選項 C**。統整為 **Agent Configuration Studio**（品牌 dispatch web 的自服務調校介面）+ 集中 **Agent Config Registry** + 治理。

### 3.1 Skill Registry
- **集中可匯入 skill 庫**（Agent Skills 標準 SKILL.md，版本化）+ **per-brand 啟用集**。
- 品牌前端：從庫**匯入** skill、**編輯**其**客製層**（見 §3.4）；tenant-scoped。
- 對齊 [[ADR-004]]：skill = 行為驅動；受保護的 `locksmith-cs-sop`(domain-safety) 品牌不可破壞。

### 3.2 RAG 知識庫權限管理
- **RAG Source Registry**：可檢索語料/DB 目錄（品牌自有 `manual_chunks`/`case_entries`、共享產業語料…）。
- 品牌前端：設定**該 agent 可檢索哪些語料**（開/關、優先序）。
- **強制點**：權限於 **MCP-RAG 查詢時 enforce**（[[ADR-004]]）——`WHERE tenant_id` + 語料 ACL，**跨租戶隔離平台鎖死、品牌不可 override**；品牌只在**自身允許範圍內**開關。

### 3.3 系統提示詞管理
- **per-brand system prompt 版本化**（屬 Model Orchestration 編排配方，[[ADR-P008]]）。
- 品牌前端編輯**客製層**；版本化 + **回滾** + OPIK eval（改動前後比對，[[ADR-P002]]）。

### 3.4 🛑 安全護欄（分層保護，待業主確認）
> **prompt 與 skill 採「受保護層 + 客製層」兩層合成：**
> - **受保護層（平台鎖死，品牌不可移除/override）**：escalation 規則、domain-safety（不編造/轉真人）、合規語氣、租戶/資料邊界。
> - **客製層（品牌可編輯）**：品牌語氣、產品重點、FAQ、開場白。
> - 合成順序保證受保護層恆生效（等同 [[ADR-004]] §3.1「RAG 弱檢索由 cs-sop domain-safety 兜底」的同一原則）。
> - **高風險改動**（動到接近受保護邊界）→ 選配 **HITL 審核**（複用 refinery/[[ADR-P011]] 骨架）。

### 3.5 治理
- **RBAC**：誰能編輯 = Casdoor 租戶 Admin 角色（[[ADR-P003]]/[[ADR-P006]]）。
- **版本化 + 回滾 + 稽核**：所有配置變更留版本與 audit。
- **eval gate**：prompt/skill 改動經 OPIK eval，回歸不過可擋/告警。

## 4. 後果

**正面**：品牌自主快速迭代客服（減 FDE 瓶頸）；skill/知識/prompt 成 first-class 可管理資產；與 registry/版本化/HITL 既有模式自洽。
**負面/風險**：**自服務擴大攻擊面 + 品質風險**——靠分層保護 + eval gate + 版本回滾 + audit + 選配 HITL 緩解；prompt injection 經配置 → 輸入驗證 + 受保護層前置。
**影響範圍**：新增 Agent Config Registry（集中）+ Agent Studio UI（品牌 web）+ agent runtime 載入 per-brand 配置；[[ADR-004]] MCP-RAG 加語料 ACL；[[ADR-P008]] prompt 分層；[[ADR-P009]] 配置層由「FDE 專屬」→「FDE + 品牌自服務」。
**重新評估觸發**：品牌濫用/事故頻發 → 收緊為「改動一律 HITL」；或 skill 生態成熟 → 開放跨品牌 skill 市集。

## 5. 執行計畫

1. Agent Config Registry（skill 庫 + RAG 源目錄 + prompt 範本，版本化）。
2. prompt/skill **受保護層 + 客製層**合成機制（agent runtime）。
3. MCP-RAG 查詢加**語料 ACL**（[[ADR-004]]）。
4. Agent Studio UI（品牌 dispatch web；匯入/編輯/開關/版本/回滾）。
5. RBAC（Casdoor 租戶 Admin）+ audit + OPIK eval gate + 選配 HITL。

## 6. 選用影響區段

- **架構**：新增 Agent Config Registry + Studio；配置層自服務化。
- **安全**：分層保護（受保護層不可 override）+ RAG 語料 ACL + eval gate + audit；**§3.4 待確認**。
- **配置**：skill/RAG 權限/prompt 皆版本化 per-brand 資產。
- **前端**：品牌 web 新增 Agent Studio surface。
