# Diagnostic State Machine Specification

> 診斷推理狀態機 — 管理跨輪次 PDCA 生命週期的狀態轉移規則

---

## 1. 設計動機

`decomposer.py` 處理單輪 LLM 推理，但缺乏跨輪次的狀態管理：
- 「現在做到哪了？」（Plan / Do / Check / Act？）
- 「可以從哪裡到哪裡？」（合法轉移 vs 非法跳躍）
- 「什麼情況下強制中斷？」（Red_Code / 情緒升級 / 3 輪上限）

狀態機解決這三個問題。它是**規則層**（確定性），不是推理層（LLM）。

```
LLM 決定: "我認為現在 hypothesis_formed"
狀態機驗證: "從 VERIFYING 到 HYPOTHESIS_FORMED 是合法轉移嗎？是 → 允許"
Python 強制: "已經 3 輪了但 LLM 還說 need_more_info → 覆寫為 DISPATCH_RECOMMENDED"
```

---

## 2. 狀態定義

10 個狀態，對應四層因果鏈的 PDCA 階段：

```
Phase    State                   說明
─────    ─────                   ────
PLAN     INTAKE                  用戶訊息進入，尚未分析
         SYMPTOM_COLLECTED       症狀已從對話提取，映射為 taxonomy ID
         FAILURE_IDENTIFIED      Failure 類型已識別 (e.g. F-LOCK-001)

DO       HYPOTHESIS_FORMED       FM 假設已生成並排序
         VERIFYING               正在追問驗證問題 (可 loop，max 3 輪)

CHECK    CONCLUSION_READY        資訊充分，可給出結論 + CA

ACT      REMOTE_RESOLVED         遠端解決，用戶確認修復
         DISPATCH_RECOMMENDED    需到府服務
         ESCALATED               轉接真人 (Red_Code / 情緒 / 安全)

TERMINAL CLOSED                  案件結案，ProblemCard 歸檔
```

---

## 3. 狀態轉移規則

### 完整轉移表

| 從 (Source) | 到 (Target) | 觸發條件 |
|---|---|---|
| INTAKE | SYMPTOM_COLLECTED | LLM 提取出 symptom IDs |
| INTAKE | ESCALATED | Red_Code / 情緒觸發 |
| SYMPTOM_COLLECTED | FAILURE_IDENTIFIED | 症狀匹配到 Failure 定義 |
| SYMPTOM_COLLECTED | VERIFYING | 症狀太模糊，需追問 |
| SYMPTOM_COLLECTED | ESCALATED | Red_Code |
| FAILURE_IDENTIFIED | HYPOTHESIS_FORMED | FM 假設生成完成 |
| FAILURE_IDENTIFIED | VERIFYING | 需驗證才能確定 FM |
| FAILURE_IDENTIFIED | ESCALATED | Red_Code |
| HYPOTHESIS_FORMED | VERIFYING | 開始驗證鏈追問 |
| HYPOTHESIS_FORMED | CONCLUSION_READY | 高信心，跳過驗證 |
| HYPOTHESIS_FORMED | DISPATCH_RECOMMENDED | 偵測到派工信號 (品牌錯誤碼) |
| HYPOTHESIS_FORMED | ESCALATED | Red_Code |
| **VERIFYING** | **VERIFYING** | **下一題 (self-loop, max 3 輪)** |
| VERIFYING | HYPOTHESIS_FORMED | 驗證後更新假設 |
| VERIFYING | CONCLUSION_READY | 驗證收斂 |
| VERIFYING | DISPATCH_RECOMMENDED | 3 輪上限 or 派工信號 |
| VERIFYING | ESCALATED | Red_Code / 情緒 |
| CONCLUSION_READY | REMOTE_RESOLVED | 用戶確認修復 |
| CONCLUSION_READY | DISPATCH_RECOMMENDED | 用戶要求到府 |
| CONCLUSION_READY | VERIFYING | 用戶提供新資訊改變診斷 |
| CONCLUSION_READY | ESCALATED | 情緒升級 |
| REMOTE_RESOLVED | CLOSED | 結案 |
| DISPATCH_RECOMMENDED | CLOSED | 派工安排完成 |
| ESCALATED | CLOSED | 真人處理完成 |
| **CLOSED** | **(none)** | **終態，不可轉移** |

### 轉移圖

```mermaid
stateDiagram-v2
    direction TB

    state "PLAN Phase" as plan {
        [*] --> INTAKE
        INTAKE --> SYMPTOM_COLLECTED : symptoms extracted
        SYMPTOM_COLLECTED --> FAILURE_IDENTIFIED : failure matched
    }

    state "DO Phase" as do_phase {
        FAILURE_IDENTIFIED --> HYPOTHESIS_FORMED : FM hypotheses generated
        HYPOTHESIS_FORMED --> VERIFYING : start verification chain
        VERIFYING --> VERIFYING : next question (max 3 rounds)
        VERIFYING --> HYPOTHESIS_FORMED : updated hypothesis
    }

    state "CHECK Phase" as check {
        HYPOTHESIS_FORMED --> CONCLUSION_READY : high confidence
        VERIFYING --> CONCLUSION_READY : verification converged
    }

    state "ACT Phase" as act {
        CONCLUSION_READY --> REMOTE_RESOLVED : user confirms fix
        CONCLUSION_READY --> DISPATCH_RECOMMENDED : user requests on-site
        CONCLUSION_READY --> VERIFYING : new info changes diagnosis
        REMOTE_RESOLVED --> CLOSED
        DISPATCH_RECOMMENDED --> CLOSED
    }

    state "Emergency" as emergency {
        ESCALATED --> CLOSED : human handled
    }

    %% Escalation from any state
    INTAKE --> ESCALATED : Red_Code
    SYMPTOM_COLLECTED --> ESCALATED : Red_Code
    FAILURE_IDENTIFIED --> ESCALATED : Red_Code
    HYPOTHESIS_FORMED --> ESCALATED : dispatch signal
    VERIFYING --> ESCALATED : Red_Code / sentiment / 3-round limit
    VERIFYING --> DISPATCH_RECOMMENDED : 3-round limit
    HYPOTHESIS_FORMED --> DISPATCH_RECOMMENDED : brand error code
    CONCLUSION_READY --> ESCALATED : sentiment escalation
```

### 簡化版（核心路徑）

```mermaid
graph LR
    A[INTAKE] --> B[SYMPTOM_COLLECTED]
    B --> C[FAILURE_IDENTIFIED]
    C --> D[HYPOTHESIS_FORMED]
    D --> E[VERIFYING]
    E -->|loop max 3| E
    E --> F[CONCLUSION_READY]
    F --> G[REMOTE_RESOLVED]
    F --> H[DISPATCH_RECOMMENDED]
    G --> I((CLOSED))
    H --> I

    style A fill:#e1f5fe
    style E fill:#fff3e0
    style F fill:#e8f5e9
    style I fill:#f5f5f5,stroke:#999

    %% Emergency path
    A -.->|Red_Code| J[ESCALATED]
    E -.->|safety/limit| J
    J --> I
    style J fill:#ffebee
```

### 不允許的轉移（守衛規則）

| 規則 | 原因 |
|---|---|
| 任何狀態 → INTAKE | INTAKE 是初始狀態，不可返回 |
| CLOSED → 任何狀態 | 終態不可重開 |
| INTAKE → CONCLUSION_READY | 不能跳過診斷直接下結論 |
| INTAKE → HYPOTHESIS_FORMED | 不能跳過症狀提取 |

---

## 4. 優先順序解析 (resolve_next_state)

當 LLM 輸出 `diagnosis_status` 後，Python 依以下優先順序決定實際轉移：

```mermaid
flowchart TD
    START([LLM output + safety result]) --> P1{P1: Red_Code<br/>or escalation?}
    P1 -->|Yes| ESC[ESCALATED]
    P1 -->|No| P2{P2: Dispatch signal<br/>or LLM=recommend_dispatch?}
    P2 -->|Yes| DISP[DISPATCH_RECOMMENDED]
    P2 -->|No| P3{P3: Verification<br/>round >= 3?}
    P3 -->|Yes & need_more_info| DISP
    P3 -->|No| P4{P4: LLM<br/>diagnosis_status?}
    P4 -->|need_more_info| VER[VERIFYING]
    P4 -->|hypothesis_formed| HYP[HYPOTHESIS_FORMED]
    P4 -->|ready_to_conclude| CON[CONCLUSION_READY]
    P4 -->|recommend_dispatch| DISP
    P4 -->|unknown| DEF[VERIFYING<br/>default]

    style ESC fill:#ffebee,stroke:#c62828
    style DISP fill:#fff3e0,stroke:#e65100
    style VER fill:#e3f2fd,stroke:#1565c0
    style HYP fill:#e8f5e9,stroke:#2e7d32
    style CON fill:#e8f5e9,stroke:#2e7d32
    style DEF fill:#f5f5f5,stroke:#999
```

**關鍵設計**：LLM 的建議可以被 Python 覆寫。例如 LLM 說 `ready_to_conclude` 但 safety gate 偵測到 Red_Code → 強制 ESCALATED。

---

## 5. DiagnosticContext 資料結構

跨輪次持久化在 `GraphState["task"]["diagnostic_fsm"]`：

```python
@dataclass
class DiagnosticContext:
    # 狀態機
    current_state: DiagnosticState      # 當前狀態
    verification_round: int             # 已追問幾輪 (0-3)
    max_verification_rounds: int        # 上限 (default 3)
    state_history: list[str]            # 轉移記錄 (debug + observability)

    # 累積證據 (跨輪次保留)
    extracted_symptoms: list[str]       # 所有已提取的 symptom IDs
    matched_failures: list[str]         # 匹配的 Failure IDs
    hypothesized_fms: list[dict]        # FM 假設 [{fm_id, reasoning, confidence}]
    verification_answers: list[dict]    # 驗證問答 [{round, question, answer}]

    # 旗標
    red_code: bool                      # 緊急狀況
    escalation_required: bool           # 情緒升級
    dispatch_signal_detected: bool      # 品牌錯誤碼觸發派工
```

### 序列化 / 反序列化

```python
# 每輪開始: 從 GraphState 恢復
ctx = DiagnosticContext.from_dict(state["task"].get("diagnostic_fsm", {}))

# 每輪結束: 寫回 GraphState
new_task["diagnostic_fsm"] = ctx.to_dict()
```

---

## 6. 與 decomposer.py 的整合

```mermaid
flowchart TD
    A[每輪對話開始] --> B["1. ctx = DiagnosticContext.from_dict(state)"]
    B --> C{2. Safety check<br/>Red_Code?}
    C -->|Yes| D["force_escalation() → return early"]
    C -->|No| E["3. 組裝 knowledge context<br/>(Tier 1 + Tier 2)"]
    E --> F["4. LLM call → structured JSON"]
    F --> G["5. 驗證 symptom IDs<br/>(validate against taxonomy)"]
    G --> H["6. 更新 ctx 累積證據<br/>(symptoms, failures, FMs)"]
    H --> I["7. resolve_next_state()<br/>(priority: safety > dispatch > limit > LLM)"]
    I --> J{"8. ctx.transition(target)<br/>合法?"}
    J -->|Yes| K["9. ctx.to_dict() → GraphState"]
    J -->|No| L["嘗試中間步驟<br/>HYPOTHESIS → target"]
    L --> K
    K --> M["10. Build diagnostic_context<br/>→ 注入 agent prompt"]
    M --> N[輪次結束]

    style D fill:#ffebee,stroke:#c62828
    style F fill:#e3f2fd,stroke:#1565c0
    style I fill:#fff3e0,stroke:#e65100
```

---

## 7. 範例：完整 4 輪對話的狀態轉移

### Happy Path: 遠端診斷 → 派工

```mermaid
sequenceDiagram
    participant U as User
    participant D as Decomposer
    participant FSM as State Machine
    participant LLM as LLM
    participant A as Agent

    Note over FSM: State: INTAKE

    U->>D: "我的鎖壞了"
    D->>LLM: Tier 1 context + question
    LLM-->>D: symptoms=[], status=need_more_info
    D->>FSM: transition(SYMPTOM_COLLECTED)
    FSM->>FSM: transition(VERIFYING)
    Note over FSM: State: VERIFYING (round 1)
    D->>A: next_action="請描述具體狀況"
    A->>U: "能描述一下是什麼狀況嗎？按指紋沒反應？螢幕不亮？"

    U->>D: "按指紋沒反應，螢幕是亮的"
    D->>LLM: Tier 1+2 context + history
    LLM-->>D: symptoms=[fingerprint_fail], failures=[F-LOCK-001], status=need_more_info
    D->>FSM: transition(HYPOTHESIS_FORMED)
    FSM->>FSM: transition(VERIFYING)
    Note over FSM: State: VERIFYING (round 2)
    D->>A: hypotheses=[FM-ELEC], question="按密碼試試看？"
    A->>U: "可以試試用密碼開鎖嗎？這樣可以幫我判斷問題範圍。"

    U->>D: "密碼可以開"
    D->>LLM: updated context
    LLM-->>D: FM-ELEC confirmed, status=ready_to_conclude
    D->>FSM: transition(CONCLUSION_READY)
    Note over FSM: State: CONCLUSION_READY
    D->>A: conclusion + CA + dispatch recommendation
    A->>U: "指紋模組可能有問題，建議安排技師，目前可用密碼..."

    U->>D: "好，幫我預約"
    D->>FSM: transition(DISPATCH_RECOMMENDED)
    FSM->>FSM: transition(CLOSED)
    Note over FSM: State: CLOSED
    A->>U: "已為您安排技師，預計..."
```

### Red_Code 中斷範例

```mermaid
sequenceDiagram
    participant U as User
    participant SG as Safety Gate
    participant D as Decomposer
    participant FSM as State Machine
    participant A as Agent

    Note over FSM: State: INTAKE

    U->>SG: "我被鎖在外面，小孩在裡面，爐子還開著"
    SG-->>SG: red_code=true (OCAP-EMERGENCY-001)

    SG->>D: safety_result.red_code=true
    D->>FSM: force_escalation("red_code")
    Note over FSM: State: ESCALATED (forced)

    D->>A: 跳過正常診斷流程
    A->>U: 1. 提供備用鑰匙指引
    A->>U: 2. 建議撥打 119 消防局
    Note over A: 同時啟動緊急派工 (SLA 2hr)
```

---

## 8. 測試覆蓋

23 個單元測試驗證：

| 測試類別 | 數量 | 驗證內容 |
|---|---|---|
| 基本轉移 | 5 | 合法/非法轉移、force_escalation、CLOSED 終態 |
| 驗證循環 | 3 | VERIFYING self-loop、VERIFYING→CONCLUSION、VERIFYING→DISPATCH |
| 完整流程 | 3 | Happy path (remote resolved)、Dispatch path、Escalation from any state |
| 序列化 | 3 | Round-trip、from empty dict、from None |
| resolve_next_state | 6 | Red_Code override、dispatch signal、round limit、LLM mapping、unknown default |
| 轉移圖完整性 | 3 | 所有狀態有定義、CLOSED 無出邊、INTAKE 不可達 |

---

## 9. 與其他模組的關係

```mermaid
graph TD
    SG[safety_gate.py] -->|safety_result<br/>red_code, escalation| DEC[decomposer.py]
    DSM[diagnostic_state_machine.py] -->|DiagnosticContext<br/>resolve_next_state| DEC
    KL[knowledge_loader.py] -->|Tier 1 + Tier 2<br/>context strings| DEC
    PR[diagnostic_reasoning.md] -->|prompt template| DEC

    DEC -->|structured JSON| LLM[LLM Call]
    LLM -->|diagnosis_status<br/>symptoms, FM hypotheses| DEC

    DEC -->|"state['task']['diagnostic_fsm']"| GS[GraphState]
    DEC -->|diagnostic_context JSON| AP[Agent Prompt Injection]

    GS -->|next turn restore| DEC

    PC[problem_card.py] -->|ProblemCard fields| DEC

    style DEC fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style DSM fill:#fff3e0,stroke:#e65100
    style SG fill:#ffebee,stroke:#c62828
    style LLM fill:#f3e5f5,stroke:#7b1fa2
    style KL fill:#e8f5e9,stroke:#2e7d32
```

---

## 10. 文件索引

| 檔案 | 角色 |
|---|---|
| `harness/task/diagnostic_state_machine.py` | 狀態定義 + 轉移規則 + DiagnosticContext + resolve_next_state |
| `harness/task/decomposer.py` | 驅動狀態機的 orchestrator (load → LLM → transition → serialize) |
| `harness/task/knowledge_loader.py` | 知識資產載入 + 序列化 |
| `harness/task/prompts/diagnostic_reasoning.md` | LLM 診斷推理 prompt |
| `harness/task/problem_card.py` | ProblemCard 資料結構 |
| `tests/unit/test_diagnostic_state_machine.py` | 23 個狀態機測試 |
| `docs/agent-harness-refactor/diagnostic-intelligence-architecture.md` | 整體診斷架構 (上層文件) |
