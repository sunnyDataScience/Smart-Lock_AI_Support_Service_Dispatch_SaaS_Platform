---
id: XCT-0001
title: Cross-Context Ownership Surface（Chatbot ↔ ERP 跨藍圖契約）
tier: 2
status: accepted
last-synced-with: dccfc0019fa897a3e5b37c4ae1130e6240190d6b
sync-source: doc
synced-at: 2026-05-16
source:
  - "docs/_archive/blueprints/AI鎖匠聊天機器人與工單同步藍圖_v2.xlsx#sheet-11"
source-paths:
  - agent/profiles/
  - agent/harness/pc_creator.py
  - api/services/problem_card_service.py
  - api/services/work_order_service.py
related:
  - "./events/EVT-0001-domain-event-catalog.md"
  - "../1-decisions/module-boundary/ARCH-0002-module-boundary-agent.md"
  - "../1-decisions/module-boundary/ARCH-0003-module-boundary-api.md"
  - "./state-machines/SM-0001-work-order.md"
---

# Cross-Context Ownership Surface

> 把「誰擁有」「誰可寫」「衝突怎辦」一次釘死。本表是 chatbot 與 ERP 工單兩邊都會碰的物件的權威清單；違反本表的寫入路徑必須先開 ADR。

## 1. 權威表

| 邊界 / 物件 | 欄位 | 擁有者藍圖 | 讀取者 | 寫入時機 | 驗證規則 | Source of Truth | 衝突解決規則 |
|---|---|---|---|---|---|---|---|
| User | `line_user_id` | Chatbot | Sync, ERP | 首次進線 | unique per tenant | Chatbot (LINE) | First-write wins |
| User | `phone` | Chatbot (capture) → ERP (master) | Both | Quick Reply / Handoff form / 後台補 | E.164 / TW pattern | **ERP（使用者主檔）** | ERP wins；Chatbot 更新需經 `update_user_info` + audit |
| User | `address` | Chatbot (capture) → ERP (master) | Both | Handoff form / 後台 / `convert_to_wo` body | non-empty for WO；district resolvable | **ERP** | `convert_to_wo` body 可 override（audit 留底）|
| ProblemCard | `brand` / `model` / `symptom` | Chatbot | Sync, ERP | AI 建單 | brand in master；symptom ≥ min length | **Chatbot（建立時）** | Chatbot 寫入；客服可修正 → audit |
| ProblemCard | `status`（draft / incomplete / confirmed / resolved）| ERP (state machine) | Chatbot (read), Sync | API call only | state transition 合法 | **ERP** | ERP wins always |
| ProblemCard | `media_urls` | Chatbot + 客服 | Sync, ERP | 媒體上傳 | url 有效 + 儲存策略 | **ERP（持久化）** | append-only |
| WorkOrder | all fields | ERP | Chatbot (read only) | `convert_to_wo` / 派工 / 完工 | 依 state machine | **ERP** | ERP-only writes；AI 禁寫 |
| Conversation Audit | raw text / tool calls | Chatbot | Audit, AI Ops, BI | 每 turn | PII 加密 at rest | **Chatbot（raw）+ ERP（mirror summary）** | Chatbot wins for raw；ERP 只存 summary |
| Skill / SOP version | `skill_id` + version | Chatbot (Skill Registry) | ERP (M20 AI Ops) | Knowledge Owner approve | version monotonic | **Chatbot** | Chatbot wins；ERP 顯示 read-only |
| Eval Set | test cases | Chatbot (AI QA) | ERP M20 read | 每次改版 | 覆蓋率 ≥ 目標 | **Chatbot** | Chatbot wins |
| Pricing rules | skill 中是否引用價格 | ERP M04 / M18 | Chatbot read（via skill or API）| 主管核准 | version + effective_date | **ERP** | ERP wins；Chatbot 不可硬編碼 |
| RBAC / Role | role + permission | ERP M17 | Chatbot（tenant/policy）| Admin 設定 | policy YAML | **ERP** | ERP wins |

## 2. 規則摘要

- **ERP wins for master data**：phone / address / WO / pricing / RBAC。Chatbot 只能 capture，最終以 ERP 為準。
- **Chatbot wins for conversational artifacts**：raw audit、ProblemCard 起單欄位、skill registry。ERP 只 mirror summary。
- **狀態機由 ERP 獨佔**：`status` 欄位（PC / WO）一律走 API 轉換；Chatbot 直接寫 status 永遠拒收。
- **跨租戶讀寫一律拒**：所有 row 都帶 `tenant_id`；違反者直接 404，不回 403（避免 enumeration）。

## 3. 變更治理

- 改本表 = 開 CIA（per `change-governance.md`）。
- 新增物件欄位 = 必須先在這張表加 row，再進 code。
- 「ERP wins」改成「Chatbot wins」（或反過來）= 必須新 ADR + 客服主管 + Tech Lead 雙簽。

## 4. See also

- 原始藍圖：sheet「11 Cross-Blueprint Contract Surface」
- [`EVT-0001`](./events/EVT-0001-domain-event-catalog.md) — 跨 context 同步的事件清單
- [`module-boundary/agent`](../1-decisions/module-boundary/ARCH-0002-module-boundary-agent.md) / [`module-boundary/api`](../1-decisions/module-boundary/ARCH-0003-module-boundary-api.md)
