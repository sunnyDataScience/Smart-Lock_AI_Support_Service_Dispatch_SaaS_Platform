# ADR-001: LockCore（fork nanobot）取代自製 LangGraph ReAct

**狀態：** 已接受 | **日期：** 2026-06-04（架構重寫落地）/ 本文件 2026-07-07 補記

---

## 1. 背景與問題

agent 子系統原本是自製架構：**LangGraph 的 ReAct 迴圈 + 自製 skill loader**，加上 Belief-Augmented ReAct（Turn Cycle：belief / calibrate / hypothesize）。這套設計累積了幾個結構性痛點：

- **自製 agent 核心維護成本高**：ReAct 迴圈、skill loader、turn cycle 都是自己寫的，沒有上游社群一起維護 bug 與新功能；每個 edge case（工具重試、上下文壓縮、空回覆恢復）都要自己踩坑。
- **知識庫格式綁死自製結構**：舊架構用 `agent/product_info/{Brand}/{Model}.md` mega-doc，格式是專案專屬的，無法直接搬到其他 agent 框架（Claude Code / Cursor / nanobot）驗證或重用。
- **LLM 供應商各家實作分散**：舊架構要為每家供應商寫 adapter，切換 Gemini / Vertex / Ollama / Claude 成本高。
- **Belief/Turn Cycle 過度工程**：belief / hypothesize / calibrate 三段對客服場景收益不明，卻大幅增加迴圈複雜度與 token 成本。

**問題核心**：如何讓 agent 核心站在成熟開源專案的肩膀上，同時採用可攜的知識格式與統一的供應商層，並砍掉過度工程的推論階段？

> 本 ADR 對應專案 governance：舊架構的 ADR-0008 / ADR-0010 / ADR-0101 已於 2026-06-05 由 ADR-0107（lockcore-supersede-product-info-trio）標為 `superseded`。本文件為 agent 子系統文件集內對此決策的技術記錄。

---

## 2. 考量的選項

### 選項 A：LockCore —— fork 自 HKUDS/nanobot 的最小核心

| 面向 | 評估 |
|------|------|
| **核心成熟度** | nanobot 有成熟的 tool-using 迴圈、context governance（microcompact / tool-result budget / snip history）、有界重試（empty-retry / length-recovery / injection）|
| **可攜知識格式** | 直接採 Agent Skills 標準（SKILL.md + references），可複製到 Claude Code / Cursor 驗證 |
| **控制權** | fork 而非依賴 → 可自由改造（注入 per-user 記憶、砍工具、換供應商）|
| **維護** | 上游 bug fix / 新功能需**手動 cherry-pick**；範圍限 AgentLoop 遞移 closure（~77 模組）|
| **缺點** | fork 維護成本（無自動同步）；帶進部分客服未用的 nanobot 模組（cron/pairing/webui closure）|

### 選項 B：以套件依賴方式引入 nanobot（不 fork）

| 面向 | 評估 |
|------|------|
| **維護** | 上游更新自動跟隨（pip upgrade）|
| **控制權** | **無法深改核心**：per-user 記憶注入、SAVE 接 record_turn、Dream 拔 write_file 等改動需要改 `ContextBuilder` / `AgentLoop` 內部，依賴方式做不到 |
| **缺點** | 客服所需的深度改造（記憶、白名單、供應商瘦身）撞上上游 API 邊界；版本升級可能破壞改動 |

### 選項 C：維持自製 LangGraph ReAct + Belief Turn Cycle

| 面向 | 評估 |
|------|------|
| **成熟度** | 已運作但 edge case 靠自己踩 |
| **可攜性** | 知識格式綁死專案；無法跨框架驗證 |
| **複雜度** | Belief/Turn Cycle 過度工程，token 成本高、收益不明 |
| **缺點** | 長期維護負擔最重；社群紅利為零 |

---

## 3. 決策

**選擇：選項 A —— LockCore（fork 自 HKUDS/nanobot 的最小核心）**

核心理由是「**站在成熟核心上，同時保留深改自由**」：

- 只複製 `AgentLoop` 的**遞移 import closure**（~77 模組 + templates + tools 全目錄），涵蓋 `agent / utils / providers / config / command / session / bus`；**未**複製 channels（上游）/ api / heartbeat / webui。來源 commit `ac8bef76`，MIT 授權（`lockcore/LICENSE`）。
- 套件由 `nanobot` 更名為 `lockcore`（所有 `.py` 內 import 與執行期字串一併改），避免與上游混淆；persona 模板改為「鎖市 LockSmart 客服助理」（`templates/SOUL.md`）。
- **深改點**：`ContextBuilder` 改為可注入 per-user `MemoryManager`（BUILD 注入 # Customer Memory）；`AgentLoop._state_save` 接 `record_turn`（SAVE 寫回記憶）；`Dream` 拔掉 WriteFileTool（防多用戶客服污染共用 skill）。
- **砍掉 Belief/Turn Cycle**：`belief.py` / `calibrate.py` / `hypothesize.py` / `turn_cycle.py` 全刪；改用 nanobot 原生 Turn 狀態機（RESTORE→…→DONE）。

主要 tradeoffs：
- 接受 fork 維護成本（手動 cherry-pick 上游），換取深改自由與社群成熟度。
- 接受帶進客服未用的 closure 模組（cron/pairing/webui），換取 import closure 完整可運作。

---

## 4. 後果

### 正面收益

- **核心穩定度**：tool-using 迴圈、context governance、有界重試皆來自成熟上游，不必自己踩 edge case。
- **知識可攜**：Agent Skills 標準讓 skill 複製到 Claude Code / Cursor / nanobot 直接可用（可攜性驗證成本降低）。
- **深改到位**：per-user 記憶、工具白名單、供應商瘦身都能落地。
- **複雜度下降**：砍掉 Belief/Turn Cycle，迴圈更簡單、token 成本降低。

### 負面風險

- **fork 維護成本**：上游 bug fix / 安全 patch 需手動 cherry-pick，無自動追蹤（P3/13 E-05）。
- **closure 殘留**：`cron/` `pairing/` `apps/cli` `webui_turns.py` 等客服未用模組進入 fork（擴大攻擊面與維護面，P4/08 §3.3）。
- **bus vs 同步歧義**：帶進 `bus/queue.py` 但 LINE 路徑走同步 `_process_message`，mid-turn 注入 / auto-compact 未生效（P1 §9 R-04）。

### 影響範圍

- `agent/lockcore/` 整包（新核心）；舊 `agent/app.py` / `agent.py` / `harness/` / `policy.py` / `belief.py` 等已刪。
- 知識庫：`agent/product_info/` mega-doc → `lockcore/skills/*/references/`。
- 供應商層：見 ADR-002。
- 知識格式：見 ADR-003。

### 重新評估觸發條件

- 上游 nanobot 停止維護或授權變更。
- fork 維護成本（cherry-pick 頻率 / 衝突）超過自製核心的預期成本。
- 客服需求超出 nanobot 核心能力邊界，須大幅改造導致 fork 與上游徹底分岔。

---

## 5. 執行計畫

1. **Vendoring**：從 nanobot commit `ac8bef76` 複製 AgentLoop 遞移 closure；補齊 templates（FileSystemLoader 讀，非 .py）與 tools 整目錄。
2. **更名**：`nanobot.*` → `lockcore.*`（import + 執行期字串）；persona 改鎖市客服。
3. **深改**：`ContextBuilder` 注入 MemoryManager；`AgentLoop._state_save` 接 record_turn；`Dream` 拔 write_file。
4. **砍工具**：`AgentLoop._register_default_tools` 全註冊後 unregister `CS_TOOL_ALLOWLIST` 外工具。
5. **刪舊架構**：ReAct / harness / belief / turn_cycle / product_info mega-doc。
6. **測試**：建 `agent/tests/`（e2e mock turn / skill loaded / tool allowlist / 記憶隔離 …）。
7. **文件**：`lockcore/VENDOR.md` 記出處、範圍、本地改動；governance 立 ADR-0107。

---

## 6. 選用影響區段（Optional Impact Sections）

> 本決策顯著改變架構邊界與依賴，故填 6.1 / 6.3 / 6.5；資料模型改動見 ADR-003，效能未實質量測故略。

### 6.1 架構圖影響（Architecture Impact）

- **Container 邊界**：agent 由「多模組自製架構」收斂為「單一 LockCore 進程」（P1/05 §2 Container 清單）。
- **進入點**：`app.py`（舊 webhook `/webhook`）→ `scripts/line_gateway.py`（`POST /callback`）。
- **同步更新**：P1/05 §3 L2、§4 L3；平台 L1（agent 節點描述）。

### 6.3 依賴清單影響（Dependency Impact）

- **移除**：LangGraph、自製 skill loader、belief/turn_cycle 相關依賴。
- **新增**：LockCore closure（含 nanobot 原生 deps）；供應商層改 litellm（見 ADR-002）。
- **授權**：nanobot MIT（`lockcore/LICENSE`）；來源 commit `ac8bef76`（`VENDOR.md`）。
- **同步更新**：`agent/pyproject.toml`、P4/08 §3.3 closure 清單。

### 6.5 安全態勢影響（Security Impact）

- **正面**：工具白名單成為沙箱邊界；Dream 拔 write_file 防 skill 污染。
- **負面**：fork 帶進客服未用模組（攻擊面）；上游安全 patch 需手動 cherry-pick（延遲風險）。
- **同步更新**：P3/13 A-01 / C-10 / D-01 / E-05。

---

*ADR-001 結尾 — agent 子系統 / 2026-07-07*
