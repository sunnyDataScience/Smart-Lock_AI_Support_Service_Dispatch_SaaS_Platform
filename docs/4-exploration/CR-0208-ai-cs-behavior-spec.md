---
id: CR-0208
title: AI 客服行為規格——prompt 層與 runtime 確定性層的分界要畫在哪
status: draft
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, Domain model, External integration, Architecture boundary, Test plan]
related: [TC-CS-AI-03, TC-CS-AI-05, TC-CS-AI-06, TC-CS-AI-11, TC-CS-AI-12, TC-AGT-RAG-01, TC-AGT-URG-01, FR-AGT-01, FR-AGT-03, FR-AGT-04, FR-AGT-07, FR-AGT-11, FR-DAT-04, FR-PLT-06, NFR-Sec-006, NFR-Sec-008, NFR-Rel-003, BR-Quote-001, BR-Quote-002, BR-AI-002, BR-AI-004, ADR-010, ADR-025, ADR-030, ADR-032, ADR-033, CR-0097, CR-0135, CR-0148, CR-0152, CR-0166, CR-0167, CR-0179]
---

# CR-0208 — AI 客服行為規格（建卡、話術紅線、RAG 引用、急迫判定）

## 1. 一句話

這 7 支 TC 的共同缺口是「規則寫在 prompt / SKILL.md、runtime 沒有確定性攔截」，
但**兩份都還是 `status: active` 的 ADR 對這件事給出相反指引**——ADR-025 說紅線
「不依賴 prompt」、ADR-033 說轉真人判準的 SSOT 就是 SOP prompt ——所以本 CR 要業主裁決的不是
「要不要補 code」，而是**那條分界線畫在哪**，以及三處正典／實作矛盾怎麼銷案。

---

## 2. 需求追溯

### 2.1 逐支 TC 的正典出處

| TC | 需求 ID | 正典條文（檔案:行號） | 條文是否真的規定了 TC 的判定基準 |
|---|---|---|---|
| TC-CS-AI-03 | FR-AGT-03 / FR-AGT-07 / FR-DAT-04 | `smartlock-docs/enterprise/04_SRS.md:278`、`:282`、`:333` | ⚠️ **部分**。三條 FR 都沒規定「什麼時候**不**建卡」。「僅明確要真人/派工才建卡」只出現在 `20_Test_Cases.md:241` 的判定基準欄 |
| TC-CS-AI-05 | FR-AGT-11 / FR-PLT-06 / NFR-Sec-008 | `04_SRS.md:286`、`:386`、`05_NFR.md:106` | ⚠️ **只對一半**。NFR-Sec-008 全文＝「pass rate ≥ 95%（**block deploy**）｜200 題自動化，每次 deploy｜**合約下限**」。**正典全庫沒有「20 改寫題 ≥ 90%」這條**（見 §2.3-①） |
| TC-CS-AI-06 | FR-AGT-11 | `04_SRS.md:286`；**BR-Quote-001 `:448`**、**BR-Quote-002 `:449`**、BR-AI-004 `:452`；ADR-025 §Decision 話術邊界段 | ✅ **完全對得上，而且比 TC 寫得更明確**。BR-Quote-002 逐字：「Guardrail 三規則（**NTD 數字無修飾語 / 折扣關鍵字 / 保固免費**）→ regen」 |
| TC-CS-AI-11 | FR-AGT-01 | `04_SRS.md:276` | ❌ **正典無此條文**。FR-AGT-01 是「LINE 進線與驗簽」，全文與樣本圖無關。`20_Test_Cases.md:249` 掛的是「FR-AGT-01 / **CR-0179**」——真正的規範只存在於 `agent/config.toml:46-48`（業主 2026-07-23 註記）與 `lockcore/skills/locksmith-cs-sop/SKILL.md:77-81`（prompt） |
| TC-CS-AI-12 | FR-AGT-03 | `04_SRS.md:278`、**`:595` 標注**；**ADR-033 全文** | ✅ 對得上，但**方向與 TC 的隱含期待相反**——ADR-033 §Decision 2 明訂「轉真人判準 SSOT＝`locksmith-cs-sop`」，即 prompt 層就是正解 |
| TC-AGT-RAG-01 | FR-AGT-07 / FR-DAT-04 | `04_SRS.md:282`、`:333`、`:572`；ADR-030；**ADR-010:80** | ⚠️ FR-DAT-04 寫「案例命中門檻 **≥ 0.85**」，ADR-010:80 已勘誤為 **0.70**（見 §2.3-③） |
| TC-AGT-URG-01 | FR-AGT-04 | `04_SRS.md:279`、**`:577` 業主 0721 裁決**；BR-AI-002 `:513`；NFR-Rel-003 `05_NFR.md:73` | ⚠️ FR-AGT-04 驗收欄要求 `urgency_detected_at` 寫入；但同檔 `:577` 已裁決「急件 deterministic timer 維持 SOP，**非缺口**」（見 §6.3） |

> 註：`20_Test_Cases.md` 案例列的 `FR-0028 / FR-0029 / FR-0030` 不是與 `FR-AGT-*` 打架——
> 同檔 `:44` 已定義該欄為「既有 `FR-00xx` 或子系統文件定位，**只保留歷史回查**」，
> 現行主鍵是 `:43` 的 `FR-AGT-*`。此處非衝突，不需裁決。

### 2.2 上位憲章（本 CR 所有判斷的依據）

`smartlock-docs/enterprise/14_ADR/ADR-025_AI話術邊界與永不自轉工單憲章.md`（`status: active`）：

- 話術邊界段：「**Server-side enforce（不依賴 prompt）**」、「Guardrail：偵測 `NTD <number>`
  缺修飾語 → regen；高風險 prefix → regen；token-level price utterance → block + audit」
- Forbidden List 明列 `warranty_liability_judgment`、`legal_safety_promise`、
  `final_price_commitment`；「任何項目移出 Forbidden → **必須開新 ADR + 法務簽字**」
- 人機交接 **7 硬規則**：「任一觸發 → 強制 `transfer_to_human`，**無 LLM judgment 餘地**」，
  判定方式欄寫「關鍵字 + 規則匹配」「情緒分類 ≥ 0.9」
- eval gate：「每次部署前跑 ≥ 200 題 regression eval……**pass < 95% → deploy block**」

### 2.3 三處必須裁決的矛盾（正典本身的問題，不是實作問題）

**① TC-CS-AI-05 的「改寫題 ≥ 90%」在正典無依據。**
`05_NFR.md:106`（NFR-Sec-008，標記為**合約下限**）與 ADR-025 的 eval gate 段都只寫
「200 題、≥95%」。`grep "0\.90"` 在 `agent/scripts/forbidden_eval.py` /
`run_forbidden_gate.py` 零命中；專案唯一的 `0.90` 在 `agent/scripts/sentiment_eval.py:27`，
是負面情緒辨識門檻，與改寫題無關。**這條門檻的唯一來源就是 TC 判定基準自己。**

**② ADR-025 與 ADR-033 對「轉真人判定該不該 deterministic」相反，兩者皆 `status: active`。**

- ADR-025：7 硬規則「**無 LLM judgment 餘地**」，急件用「關鍵字 + 規則匹配」、怒客用「情緒分類 ≥ 0.9」
- ADR-033（2026-07-22 業主裁決）：「**轉真人判準 SSOT＝`locksmith-cs-sop`**（SKILL.md ＋
  `references/handoff-and-dispatch.md`）：①明確要求真人 ②急迫派工 ③金錢相關 ④連續兩次不滿」

ADR-033 只明文廢止了 ADR-025 第 7 條（3+ 次未解決 / 三輪硬計數），**沒有處理第 1、2 條
（急件、怒客）的「deterministic」屬性**。ADR-033 的 relates 欄把 ADR-025 稱為「上位原則」，
但 Decision 2 實際上把判定權交還給 prompt。這個未收斂的邊界，正是 TC-CS-AI-12 與
TC-AGT-URG-01 兩支 TC 被判「部分實作」的根因。

**③ RAG 相似度門檻三方不一致，其中一方是**餵給 LLM 的字串**。**

| 來源 | 值 | 檔案:行號 |
|---|---|---|
| 04_SRS FR-DAT-04（未標注） | ≥ 0.85 | `smartlock-docs/enterprise/04_SRS.md:333` |
| ADR-010 勘誤（as-built，已標注） | **0.70** | `smartlock-docs/enterprise/14_ADR/ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md:80` |
| 實作常數 | 0.70 | `agent/rag/rag/store.py:18` |
| **MCP 工具 docstring（進 LLM context）** | ≥ 0.85 | `agent/rag/rag/server.py:61` |
| 模組 docstring | ≥ 0.85 | `agent/rag/rag/store.py:6`、`:105` |

ADR-010:80 已把 0.70 記為 as-built（CR-0148 實測：multilingual-002 下真改寫 sim≈0.743，
0.85 恆不命中）。**但 `server.py:61` 是 MCP 工具的 docstring，會直接進 LLM 的工具描述**——
模型被告知「只回相似度 ≥ 0.85 的高信心案例」，實際拿到的是 ≥ 0.70。這不是註解過期，
是**對模型的錯誤信心宣稱**。

---

## 3. 歷史成因（為什麼會變成「一半 runtime 一半 prompt」）

不是疏漏，是兩條治理路線在不同時間各自推進、從未交會：

| 時間 | 事件 | 推向哪一層 |
|---|---|---|
| 2026-07-10 | **ADR-025** 立憲：紅線「不依賴 prompt」、server-side enforce | → runtime |
| 2026-07-10 | ADR-025 §Status 附註自承兩缺口，其一為「生成後 guard 未接 agent loop（僅 CI 層）」→ 立 CR-0152 | → runtime |
| 2026-07-10 | **CR-0135**：200 題 corpus + CI gate + nightly live 落地 | → 離線 eval |
| 2026-07-12 | **CR-0166 R0**：K8 `warranty_free` 失守校正 → 加 `claimed_transfer_violation` | → runtime |
| 2026-07-22 | **ADR-033**（業主裁決）：三輪硬計數廢止，轉真人判準 SSOT 交回 SOP | → **prompt** |
| 2026-07-23 | 業主定 photo-guide 品牌專屬規則，寫進 `config.toml` 註解與 SKILL.md | → prompt |
| 2026-07-27 | reply_guard 補中文數字價格分支、`_KNOWN_MODELS` 精確清單 | → runtime |
| 2026-08-02 | escalation spool 耐久性補強（原本 5xx 一次就永久遺失） | → runtime |

`agent/lockcore/agent/reply_guard.py:1-10` 的檔頭自述得很清楚：
「憲章要求『不依賴 prompt』：價格 utterance 與未溯源型號屬確定性 regex 判定」——
**它只實作了憲章三規則裡的第一條**。折扣、保固免費那兩條，2026-07-10 立憲至今沒人補，
而 `locksmith-cs-sop/SKILL.md:47-50` 的 v1.4.0 版本註記自承是「K8 warranty_free 失守校正」——
**這條紅線曾經實際失守過，補的是 prompt，不是 code。**

---

## 4. 現況證據（逐條複驗，皆為本次實讀）

### 4.1 runtime 現有的確定性層（做到的部分）

| 守線 | 檔案:行號 | 覆蓋 |
|---|---|---|
| 價格 utterance（含中文數字） | `agent/lockcore/agent/reply_guard.py:20-24`、`:124-126` | ✅ BR-Quote-002 第 1 條 |
| 未溯源型號（29 個已知型號精確比對） | `reply_guard.py:38-53`（`_KNOWN_MODELS`，實數 **29** 個非文件所稱 27）、`:124` 起 | ✅ 不編造型號 |
| 說了沒做（宣稱已轉接但未呼叫工具） | `reply_guard.py:72-88`、`:140-142` | ✅ NFR-Rel-003 |
| 違規處置鏈 | `loop.py:1469`（guard_violations）→ `:1477`（CORRECTIVE_INSTRUCTION 重生一次）→ `:1503`（複驗）→ `:1508-1516`（寫 escalation）→ `:1519`（`TRANSFER_FALLBACK`） | ✅ |
| escalation reason 必填 | `agent/lockcore/agent/tools/transfer.py:62`（`required=["reason"]`）、`user_memory/escalation.py:51`（`reason TEXT NOT NULL`） | ✅ TC-CS-AI-06 第 3 條 |
| 話術兜底（CR-0097） | `channels/line_gateway.py:609-644`（`_DEFINITIVE_HANDOFF_MARKERS` 等四組判定） | ✅ |
| photo-guide 未知 key / 殘尾剝除 | `line_gateway.py:258-285`（`_swap` 回空字串 + WARNING）、`:252-255`（`_PHOTO_GUIDE_PARTIAL_RE`） | ✅ TC-CS-AI-11 後三條 |
| RAG 租戶 default-deny | `agent/rag/rag/store.py:29-34`（未設 `RAG_TENANT_ID` 直接 `RuntimeError`）、`server.py:80`（啟動前先驗） | ✅ 且 `tid` 取自 env 非工具參數，LLM 無從指定他租戶 |
| RAG 查詢必帶 tenant | `store.py:89`（manual）、`:120`（case） | ✅ |
| MCP fail-soft 不中斷 turn | `agent/lockcore/agent/tools/mcp.py:212-216`（逾時回字串不 raise）、`agent/config.toml:68` `tool_timeout = 20` | ✅ |
| escalation 冪等（重試只留一筆） | `api/services/problem_card_service.py:1026-1039`（sha256 鍵 + 24h 視窗）、`:975-980`（`status IS DISTINCT FROM 'escalated'`） | ✅ TC-AGT-URG-01 第 3 條 |

### 4.2 缺口（逐條有行號）

| # | 缺口 | 證據 | 對應 TC |
|---|---|---|---|
| G1 | **BR-Quote-002 三規則只實作 1/3**：`guard_violations` 只有 price / unsourced_model / claimed_transfer，無「折扣關鍵字」「保固免費」 | `reply_guard.py:143-153`（全文 11 行，三個 `out.append`） | TC-CS-AI-06 |
| G2 | 無對應測試：`tests/test_reply_guard.py` 13 個測試全在 price / model / claimed_transfer 三類 | `agent/tests/test_reply_guard.py:15-76` | TC-CS-AI-06 |
| G3 | **rotating 20 題題庫檔不存在**：`agent/evals/` 只有 `forbidden_corpus.json`（200 題，實測分類 40/30/30/30/30/20/20 完全符合配額）與 `sentiment_corpus.json` | `ls agent/evals/` | TC-CS-AI-05 |
| G4 | **rotating 重疊檢查是死碼**：`run_forbidden_gate.py:30` 呼叫 `validate_corpus_structure(corpus)` **沒傳 rotating**，`forbidden_eval.py:108-111` 的 `if rotating:` 分支在 CI 從未執行 | `run_forbidden_gate.py:30`、`forbidden_eval.py:108` | TC-CS-AI-05 |
| G5 | **gate 沒接在 deploy 路徑上**：`grep run_forbidden_gate scripts/deploy/*.sh .github/workflows/cloud-run-deploy.yml` 零命中 | 同左 | TC-CS-AI-05 |
| G6 | **改 agent 行為不觸發 gate**：workflow push paths 只列 5 項，**不含 `agent/lockcore/**`** | `.github/workflows/forbidden-eval-gate.yml:10-15` | TC-CS-AI-05 |
| G7 | **photo-guide 無 runtime 品牌 gate**：`_swap` 只查 key 是否在 `guide_map`，模型對非 Chatlock 客戶輸出 `chatlock-pre-install` 就夾圖 | `line_gateway.py:270-278` | TC-CS-AI-11 |
| G8 | SKILL.md:78「一則回覆**至多一個**標記」vs runtime 上限 4 | `SKILL.md:78` vs `line_gateway.py:255`（`_PHOTO_GUIDE_MAX = 4`） | TC-CS-AI-11 |
| G9 | **「連續兩次不滿」無跨輪計數器**；情緒判定結果只流向 persist payload | `line_gateway.py:1177-1188`；下游 `api/services/conversation_service.py:329-336`（`label ∈ {negative, very_negative}` → 寫 `sentiment_alerts` + 通知，**不轉真人、不靜音 AI、不建卡**，且觸發點是**單次**負面） | TC-CS-AI-12 |
| G10 | **4xx 一律視為終局 → 可恢復的失敗被永久吃掉**：`_post_escalation` 對 400-499 `return True  # 視為終局，不再佔用 spool`；而 `api/routers/internal_ingest.py:54-58` 的 tenant 解析失敗（`AGENT_TENANT_ID` 未設）正是回 **400** | `line_gateway.py:457-463`、`internal_ingest.py:54-58` | TC-AGT-URG-01 |
| G11 | **spool 是容器本機檔**，Cloud Run 實例回收即整批遺失 | `line_gateway.py:374-376`（`ESCALATION_SPOOL_PATH` 預設 `data/escalation_spool.jsonl`） | TC-AGT-URG-01 |
| G12 | `urgency_detected_at` 全樹零命中（FR-AGT-04 驗收欄要求） | `grep -rn urgency_detected_at api/ agent/ SQL/ web/` 無輸出 | TC-AGT-URG-01 |
| G13 | **RAG 無跨租戶 / timeout 測試**：`agent/rag/tests/` 只有 `test_store_unit.py` + `test_mcp_integration.py`（後者需 pgvector），無雙租戶 fixture、無 timeout stub | `ls agent/rag/tests/` | TC-AGT-RAG-01 |
| G14 | `search_manual` 無相似度門檻，只有 `ORDER BY ... LIMIT`；語意不相關的 chunk 仍進 top_k | `store.py:84-97`（對照 `:126` case 檢索有門檻） | TC-AGT-RAG-01 |
| G15 | **MCP 工具 docstring 對 LLM 宣稱 ≥0.85，實際 0.70** | `server.py:61` vs `store.py:18` | TC-AGT-RAG-01 |
| G16 | **TC-CS-AI-03 的測資本身不成立**：`references/` 只有 6 個品牌（`_common` / 3E / Chatlock / Dormakaba / Kaadas / Milre / Philips），`SKILL.md:3,:7` 的 `brands` 也只列這 6 家，**`grep -rli yale agent/lockcore/skills/` 零命中** | `ls agent/lockcore/skills/locksmith-product-knowledge/references/` | TC-CS-AI-03 |
| G17 | reply_guard 路徑會在**純知識問答**中建卡：幻覺型號 → `unsourced_model` → regen 仍違規 → `loop.py:1508-1516` 寫 escalation → `_forward_escalation_safe` 旁路建 draft 卡 | `loop.py:1508-1516` + `line_gateway.py:572-577` | TC-CS-AI-03 |
| G18 | **無「誤攔率 < 1%」的量測集**（NFR-Sec-006 要求 100 題正常對話）：`agent/evals/` 無正常對話集，僅 `tests/test_reply_guard_blindspots.py` 有零星反例 | `ls agent/evals/` | 影響 G1 的落地驗收 |

---

## 5. 程式碼現狀：分界線目前實際畫在哪

```
                         客戶訊息
                             │
              ┌──────────────┴──────────────┐
              │   prompt / SKILL.md 層       │   ← 轉真人四條件、連續兩次不滿、缺項一次列齊、
              │   （ADR-033 裁定為 SSOT）     │      photo-guide 品牌規則、RAG 降級後轉人、
              └──────────────┬──────────────┘      折扣/免費保固不承諾
                             │ LLM 自由裁量
                             ▼
              ┌─────────────────────────────┐
              │  runtime 確定性層 reply_guard │   ← 只有 3 條：price_utterance /
              │  （ADR-025 裁定不依賴 prompt）│      unsourced_model / claimed_transfer
              └──────────────┬──────────────┘
                             │
              ┌──────────────┴──────────────┐
              │  gateway 兜底 + 旁路 + spool  │   ← 說了沒做兜底、photo-guide 剝除、
              └──────────────┬──────────────┘      escalation 轉發（4xx 吃掉、本機 spool）
                             ▼
                        API / DB（冪等）
```

**觀察**：確定性層的三條規則有一個共同特徵——**都是「檢查 AI 說了什麼」（輸出面）**，
而不是「決定 AI 該做什麼」（進線判定面）。這其實已經是一條可用的分界線，只是從來沒有人
把它寫成裁決。ADR-025 與 ADR-033 的衝突，就是因為兩份文件都在講「轉真人」，但一份在講
輸出面（說了已轉接就必須真的轉）、一份在講判定面（什麼情況該轉）。

---

## 6. 影響評估

### 6.1 Rewrite vs Refactor 九維打分

| 維度 | 分 | 理由（含證據） |
|---|---|---|
| 產品目標是否改變？ | **0** | 沒變。7 支 TC 全在既有 FR-AGT-* 範圍內，無新產品假設 |
| 核心 User Flow 是否改變？ | **1** | 新增分支：折扣/保固 guard 命中 → regen → 轉真人（既有 `loop.py:1469-1519` 鏈路加一個判定項）；photo-guide 加品牌條件。主流程不動 |
| Domain Model 是否改變？ | **1** | 新增概念：跨輪負面計數（若做 D6）、escalation 耐久載體、`urgency_detected_at`。皆為新增，核心概念（escalation / problem_card）不改 |
| API Contract 是否大量破壞？ | **0** | 少量：`internal_ingest` tenant 解析失敗的 HTTP 狀態碼語意（400→5xx）一處 |
| DB Schema 是否需重建？ | **1** | migration 可處理：outbox 表或 `urgency_detected_at` 欄位，皆為 additive |
| 模組邊界是否錯誤？ | **1** | 有些混亂：①ADR-025 vs ADR-033 對 prompt/runtime 分界未收斂 ②「agent 不直接寫庫」的分層與 escalation 耐久性需求正面衝突（G11） |
| 測試是否可信？ | **1** | 部分可信：agent 全套 330 passed，但 rotating gate 是死碼（G4）、gate 未接 deploy（G5）、RAG 跨租戶/timeout 零覆蓋（G13）、折扣/保固零覆蓋（G2）、誤攔率無量測集（G18）。**「CI 綠」目前不代表紅線守得住** |
| 文件是否可信？ | **1** | 部分過期：RAG 門檻三方不一致（§2.3-③）、SKILL.md:78 vs MAX=4（G8）、`_KNOWN_MODELS` 文件寫 27 實為 29、FR-AGT-01 掛了一條它沒規定的判定基準（TC-CS-AI-11） |
| 團隊/AI 是否還理解系統？ | **0** | 理解。走查文件引用的行號本次逐條複驗，僅 3 處 ±1 行偏移；ADR/CR 記錄完整到能還原每個設計的動機 |
| **總分** | **6** | |

### 6.2 行動建議：**改文件 + 局部重構（CIA + 一次性實作）**

6 分落在 0–6 區間**上緣**，這點必須講清楚：

- 6 分裡有 **3 分（模組邊界 / 測試 / 文件）來自同一件事**——prompt 與 runtime 的分界從未被
  裁決。D1 + D2 一旦定案，這 3 分會同時往下掉。
- 反過來，**如果 D1 選 (c)「全面 deterministic」，模組邊界與 Domain Model 各再 +1 → 8 分，
  進入「架構重審 + 模組拆分」區間**（要引入政策引擎、跨輪狀態機、per-brand 可配置規則）。
  這不是恐嚇——ADR-033 §Consequences 自己就寫了：「若未來要量測 AI 釐清效率或防 gaming
  需求升級，**需另開 ADR 實作確定性計數器**」。
- 所以本 CR 的分數不是固定的，**它是 D1 的函數**。這是本節最重要的結論。

### 6.3 哪些必須是確定性 code gate、哪些留 prompt 可接受

這是本組 7 支 TC 的核心判斷。分界依據：**「錯了之後能不能用一句話收回」**。

**必須 deterministic（涉及金額 / 承諾 / 合約紅線，錯了就是法律或賠償問題）**

| 項目 | 為什麼不能留 prompt | 現況 |
|---|---|---|
| 金額 utterance | BR-Quote-001「🔴 永禁」＋ ADR-025 明文 server-side enforce | ✅ 已有 |
| **折扣關鍵字** | BR-Quote-002 逐字列為三規則之一；ADR-025 Forbidden `final_price_commitment` | ❌ **缺（G1）** |
| **保固免費 / 賠償承諾** | BR-Quote-002 逐字列為三規則之一；ADR-025 Forbidden `warranty_liability_judgment`；**且 `SKILL.md:50` 自承 v1.4.0 是「K8 warranty_free 失守校正」——這條實際失守過** | ❌ **缺（G1）** |
| 說了沒做（案子蒸發） | NFR-Rel-003「100% 進後台問題卡」是營運目標且有客訴前例 | ✅ 已有 |
| **轉真人紀錄的耐久性** | 客人已經收到「已為您轉接」＝承諾已作出；紀錄丟了就是**對客戶說謊**。這比「是否該轉」更硬 | ❌ **缺（G10、G11）** |
| RAG 租戶隔離 | 跨租戶資料外洩 | ✅ 已有（env 取 tenant，LLM 無從指定） |

**留 prompt 層是可接受的（判斷性、情境性，錯了下一輪能修正）**

| 項目 | 理由 |
|---|---|
| 轉真人四條件的判定 | **ADR-033 §Decision 2 已裁決 SSOT＝cs-sop**。這是業主 2026-07-22 的決定，不是缺陷 |
| 「連續兩次不滿」 | 同上；且 `templates/SOUL.md:14` 逐字「不採『一次只問一條、問三次再轉真人』的硬規則」。硬加計數器會與既有設計哲學正面衝突 |
| 缺項一次列齊 | 純體驗，無合約風險；ADR-033 §Decision 3 已降級為話術原則 |
| RAG timeout 後降級轉人 | 最危險的後果（編造型號）已由 `unsourced_model` guard 擋住；再加一條「工具失敗必轉人」會大幅推高誤轉率 |
| 急件四類 intent 判定 | **`04_SRS.md:577` 業主 0721 已裁決「維持 SOP，非缺口」** |

**介於中間、建議做但不是紅線**

| 項目 | 判斷 |
|---|---|
| photo-guide 品牌 gate（G7） | 不是金額紅線，但「丟錯品牌的圖 → 客戶量錯 → 安裝失敗」有實害，且**業主 2026-07-23 已在 `config.toml:46-48` 白紙黑字寫過**。加上材料現成（`line_gateway.py:708-710` `_KNOWN_BRANDS`、`:715` `_extract_brand_model`），成本近零 → **建議做** |

### 6.4 誠實分流：查證後認為**不該修**或應降級的部分

> 這一節是為了不讓本 CR 為了填滿而編造工作項。

| 項目 | 判斷 | 理由 |
|---|---|---|
| TC-CS-AI-12 的「四條件無程式判定」 | **不該當缺陷** | ADR-033 §Decision 2 明文裁決 prompt 層為 SSOT。走查文件把它列為「部分實作」在事實上正確，但**規格意圖上是符合的** |
| TC-CS-AI-12 的「不因固定輪數誤轉」 | **本來就一致** | SKILL.md:70 與 SOUL.md:14 反向明文禁止，程式無輪數邏輯。此條應判「一致」 |
| TC-CS-AI-12 的「連續兩次不滿計數器」 | **建議不做行為閘控** | 見 §6.3。若業主要，ADR-033 已預告需另開 ADR；建議先做「只記錄不閘控」的稽核計數 |
| TC-AGT-URG-01 的「agent 判急件四類」「5 分鐘 timer」 | **已裁決非缺口** | `04_SRS.md:577` 白紙黑字，**不應再列為待補**。走查文件步驟 1 有引到這句但沒帶進判定 |
| TC-AGT-URG-01 的 `urgency_detected_at` | **建議走文件面** | 時序資訊實際存在——`agent.escalation.created_at`（`SQL/migrations/033-agent-memory-schema.sql:55`）＋ draft 卡 `created_at` 可完整還原。這是**欄位名與載體對不上**，硬加欄位只會多一份要維護的重複資料。除非業主要 SLA 儀表板 |
| TC-CS-AI-03 的「AI 以 skill references 回答」 | **測資問題，非 code 缺口** | Yale 不在知識庫 6 品牌內（G16），這條判定基準對此用例**不可能成立**。改 code 也救不了——要嘛改測資，要嘛先有 Yale 的 bronze 語料（內容工程） |
| TC-CS-AI-05 的「改寫題 ≥ 90%」 | **門檻本身待確認** | §2.3-① —— 正典無此條文。可能是 TC 撰寫時的自創，需業主確認是不是真的合約線 |
| TC-AGT-RAG-01 的「租戶隔離」 | **判「一致」而非部分實作** | `tid` 取自 env 非工具參數 + 啟動前先驗（`server.py:80`），LLM 無管道指定他租戶。走查文件的「部分實作」成立點只在 timeout 降級與測試覆蓋，不在隔離本身 |

### 6.5 上線風險（若什麼都不做）

| 風險 | 嚴重度 | 依據 |
|---|---|---|
| AI 承諾「免費幫您保固到明年」，runtime 完全不攔 | **P1** | G1；SKILL.md:50 自承這條失守過；ADR-025 估算單次客訴成本 NTD 30k 量級 |
| 轉真人紀錄永久遺失，客人已被告知「已轉接」 | **P1** | G10（可恢復的 400 被吃掉）+ G11（Cloud Run 回收整批丟）；正是業主 2026-08-01 親眼看到的畫面 |
| NFR-Sec-008 是**合約下限**，但「block deploy」名不副實 | **P1** | G5、G6——deploy 腳本零命中，改 `agent/lockcore/**` 甚至不觸發 CI |
| 非 Chatlock 客戶收到 Chatlock 測量圖 → 量錯 → 安裝爭議 | P2 | G7；業主 0723 已預警 |
| LLM 以為案例都是 ≥0.85 高信心，實際 0.70 | P2 | G15 |
| 純知識問答產生後台草擬卡噪音 | P2 | G17 |

---

## 7. 可行路徑（各項的落地成本）

| # | 工作項 | 觸及檔案 | 規模 | 觸發 CIA 面向 |
|---|---|---|---|---|
| P1 | reply_guard 加 `promise_utterance`（折扣 / 免費保固 / 賠償承諾） | `reply_guard.py`（+`_PROMISE_RE`、`guard_violations` 加一行、`CORRECTIVE_INSTRUCTION` 補一句）、`tests/test_reply_guard.py` | 小（單檔） | User/Business flow、Test plan |
| P2 | 誤攔率量測集（NFR-Sec-006 <1%） | 新增 `agent/evals/normal_corpus.json`（100 題正常對話）+ runner | 中 | Test plan |
| P3 | rotating 20 題 + 90% 門檻 + runner 兩段 gate | `agent/evals/forbidden_rotating.json`（新）、`forbidden_eval.py`、`run_forbidden_gate.py`、`tests/test_cr_0081_forbidden_eval.py` | 中（跨數檔） | Test plan |
| P4 | gate 接 deploy：workflow paths + `agent.sh` pre-flight | `.github/workflows/forbidden-eval-gate.yml:10-15`、`scripts/deploy/agent.sh` | 小 | Test plan |
| P5 | photo-guide 品牌 gate | `line_gateway.py`（`_extract_photo_guides` 加 brand hint 參數，呼叫端 `_run_merged_turn` 以 `_extract_brand_model` 推得）、`tests/test_photo_guide.py` | 小（單檔） | User/Business flow、Test plan |
| P6 | escalation 4xx 分流 | `line_gateway.py:457-463`；**須同步改既有測試** `tests/test_escalation_spool_durability.py:117`（`test_4xx_is_terminal_and_not_retried` 刻意釘住現行契約） | 小 | External integration |
| P7 | `internal_ingest` tenant 解析失敗改 5xx | `api/routers/internal_ingest.py:54-58`、`api/openapi.yaml` | 小 | API contract |
| P8 | spool 改耐久載體 | `line_gateway.py:374-512`；GCS 或 DB outbox | 中～大 | Architecture boundary、External integration（DB outbox 另加 DB schema） |
| P9 | RAG 測試補齊（跨租戶 + timeout） | `agent/rag/tests/`（雙租戶 pgvector fixture）、`agent/tests/`（timeout stub） | 中 | Test plan |
| P10 | RAG docstring / 正典門檻對齊 | `rag/rag/server.py:61`、`store.py:6,:105`；`04_SRS.md:333` **加標注（不改寫）** | 極小 | —（文件） |
| P11 | SKILL.md:78 與 `_PHOTO_GUIDE_MAX` 對齊 | 二選一 | 極小 | —（文件/常數） |
| P12 | TC-CS-AI-03 測資改站內品牌 | `20_Test_Cases.md:241`（**業主正典，只可標注**）＋走查文件 | 極小 | —（文件） |

**⚠️ 實作陷阱（P11 與任何動 SKILL.md 的工作項都會踩到）**：
依 **ADR-032 / CR-0167**，skill 的日常迭代 SSOT 已移到品牌庫 `saas.skill_revision`，由
`lockcore/agent/skill_sync.py` 60s 輪詢物化到 `workspace/skills/`，**workspace 版優先於
builtin**。改 `lockcore/skills/` 底下的 SKILL.md **只改到出廠範本**——若 prod 已有
workspace 版本，改了不會生效。必須同時在品牌後台「知識庫 > AI 技能」分頁編輯並發佈。

**Architecture Lock 提醒**：以上所有 agent 側改動都落在 `agent/lockcore/` 內
（`reply_guard.py` / `loop.py` / `channels/line_gateway.py`），未新建 agent 核心、未新增
內建工具、未繞過 `LiteLLMProvider`。P1 不新增工具（只加 guard 判定），不動
`CS_TOOL_ALLOWLIST`。

---

## 8. 🛑 Human Decisions Required

> 每題請只回「D<n> 選 <字母>」即可；有補充再加一行。

### D1：prompt 層與 runtime 確定性層的分界要畫在哪？（**本 CR 主決策，其餘多數決策依賴它**）

- **(a) 輸出面 deterministic、判定面留 SOP** —— 把 BR-Quote-002 三規則補齊（加折扣、免費
  保固/賠償承諾），其餘（轉真人四條件、連續不滿、缺項列齊、RAG 降級）維持 prompt。
  代價：新增一條 regex 判定，誤攔風險（例：「保固說明」被當成「保固承諾」）；需先建誤攔量測集（P2）。
- **(b) 維持現狀** —— 折扣/保固只靠 prompt + nightly live eval。
  代價：紅線在 runtime 上是空的；`SKILL.md:50` 記錄它曾實際失守；ADR-025 的
  「不依賴 prompt」形同具文。
- **(c) 全面 deterministic** —— 連轉真人四條件、連續兩次不滿都做確定性偵測。
  代價：與 ADR-033 §Decision 2 正面牴觸、與 `SOUL.md:14` 設計哲學衝突；§6.1 打分將升至 8 分
  （進入「架構重審 + 模組拆分」），需政策引擎與跨輪狀態機，跨 sprint。

**我的建議：(a)。** 理由三條：①BR-Quote-002 是**逐字列出三規則**的明文條文，補齊是回到
既有規格而非新增需求；②折扣/保固屬「輸出面」，判定材料就在回覆字串裡，不需要新狀態；
③(c) 要推翻業主自己 20 天前的裁決（ADR-033），沒有新事證支持這麼做。

---

### D2：ADR-025 與 ADR-033 的衝突（§2.3-②）怎麼銷案？

- **(a) 新開 ADR-034 明訂分層** —— 「輸出面（AI 說了什麼）＝ deterministic guard；
  進線判定面（何時該轉人）＝ SOP prompt」，並在 ADR-025 加標注指向它。
  代價：一份 ADR 的撰寫與簽核時間。
- **(b) 只在 ADR-025 加標注指向 ADR-033**，不新開。
  代價：ADR-025 的 7 硬規則第 1、2 條（急件、怒客）的 deterministic 屬性仍懸空，下次還會撞到。
- **(c) 不處理。**
  代價：下一個讀這兩份 ADR 的人（含 AI）會各引一份、得出相反結論——這正是
  `change-governance.md` 定義的 AI slop 根源。

**我的建議：(a)。** 這條分界線是 D1 之後所有實作的引用來源；沒有它，P1、P5、P6 每一項都會
在 code review 時重新吵一次「這該不該進 code」。

---

### D3：TC-CS-AI-05 的「改寫題 ≥ 90%」是真的合約線嗎？（§2.3-①：正典全庫無此條文）

- **(a) 補做並 block** —— 建 20 題 rotating 題庫 + 90% 門檻 + runner 兩段 gate，未達即擋部署。
  代價：用一條沒有出現在 NFR-Sec-008 / ADR-025 的門檻擋上線。
- **(b) 降 TC 判定基準** —— 對齊 NFR-Sec-008（200 題 ≥95%），移除 `forbidden_eval.py:108-111`
  的 rotating 死碼。代價：失去偵測「模型對 200 題過擬合」的手段。
- **(c) 折衷：建題庫、跑、只報數不 block** —— 兩個月後看實際分佈再定門檻，屆時補進 NFR。
  代價：這段期間 rotating 不具閘門效力（但至少不是死碼）。

**我的建議：(c)。** rotating 的價值（偵測 corpus 過擬合）是真的，但 90% 這條線目前**沒有任何
人簽過**。先報數、有資料再定門檻，比先擋再回頭調安全。無論選哪個，G4 的死碼都該修。

---

### D4：forbidden gate 要不要真的接上 deploy 路徑？

- **(a) 兩件都補** —— workflow push paths 加 `agent/lockcore/**`（G6）＋
  `scripts/deploy/agent.sh` pre-flight 加一步 dry gate（G5）。
  代價：deploy 多 5–10 秒（dry 不打 LLM）。
- **(b) 只補 paths。** 代價：本機／手動 deploy 仍完全繞過。
- **(c) 不動** —— 認為 nightly live 已足夠。
  代價：NFR-Sec-008 是**合約下限**且逐字寫「每次 deploy」，現況與條文不符。

**我的建議：(a)。** 這是本 CR 裡投入產出比最高的一項——兩處各改幾行，就讓一條合約下限從
「名義存在」變成「真的擋得住」。

---

### D5：photo-guide 要不要加 runtime 品牌 gate？抽不到品牌時的預設行為？

- **(a) 加 gate，抽不到品牌 → 不夾圖（保守）。**
  代價：客人偶爾少收到一張本來該收到的圖（可用文字引導補）。
- **(b) 加 gate，抽不到品牌 → 仍夾圖（信任 LLM 的品牌判斷）。**
  代價：品牌抽取失敗時風險與現況相同。
- **(c) 不加，維持 prompt 層。** 代價：業主 0723 已預警的「丟錯品牌的圖會誤導客戶量錯」無防線。

**我的建議：(a)。** 傷害不對稱——「丟錯圖」比「不丟圖」嚴重得多，而材料現成
（`line_gateway.py:708-710` 的 `_KNOWN_BRANDS` 與 `:715` 的 `_extract_brand_model` 都是
deterministic 且已在兜底路徑實戰使用）。

---

### D6：escalation 的 4xx 終局策略（G10：可恢復的失敗被永久吃掉）

- **(a) agent 端細分 4xx** —— 只有明確的 payload 格式錯（422）視為終局，其餘 4xx（含 tenant
  解析失敗的 400）落 spool 重試。代價：需同步改既有測試
  `tests/test_escalation_spool_durability.py:117`，那支測試是**刻意**釘住現行契約的。
- **(b) 全部 4xx 落 spool** —— 靠 spool 上限自然丟棄。代價：真壞掉的 payload 會反覆重試佔位。
- **(c) API 端改語意** —— `internal_ingest.py:54-58` 的 tenant 解析失敗改回 5xx
  （`AGENT_TENANT_ID` 未設是**伺服端配置錯誤**，不是 client 的 payload 錯）。
  代價：動 API 錯誤碼＝ API contract 變更，需同步 `api/openapi.yaml`。
- **(d) 不處理。** 代價：客人已被告知「已為您轉接」，紀錄卻可能永久消失。

**我的建議：(a) + (c) 並行。** (c) 是語意的正本清源——回 400 說「這是你 client 的錯」本身就
判斷錯了；(a) 是防禦，因為 agent 不該假設所有 4xx 都是自己的錯。兩者互不取代。

---

### D7：escalation spool 的耐久載體（G11：Cloud Run 實例回收即整批遺失）

- **(a) 維持容器本機檔** —— 靠 `[ESCALATION_ALERT]` ERROR 告警 + 人工救。
  代價：告警要有人看；實例回收時 spool 內容連告警都來不及發。
- **(b) 改 GCS 物件** —— 只換 spool 的儲存後端，語意不變，不動「agent 不直接寫庫」的分層。
  代價：新增 GCS 相依 + service account IAM；每次 flush 多一次網路 I/O。
- **(c) 改 DB outbox 表** —— agent 直接寫庫。
  代價：**牴觸既有分層**（`agent/lockcore/agent/sentiment.py:1-8` 明文「寫庫/通知由呼叫端
  負責，維持 architecture lock（agent 不直接寫庫）」），須另開 ADR。

> **(d)「走 api 的 outbox 端點」邏輯上不成立**，特此點明：spool 存在的前提就是 API 不可用，
> 再把 spool 寄託於 API 是循環相依。

**我的建議：(b)。** 這是唯一同時解決耐久性又不破壞分層的選項。若業主認為 GCS 相依過重，
退而求其次選 (a) 也可接受——但那必須配套「有人真的在看 `[ESCALATION_ALERT]`」的營運承諾，
否則是紙上防線。

---

### D8：RAG 相似度門檻的三方不一致（§2.3-③）

- **(a) 以 ADR-010:80 為準** —— 修 `server.py:61` / `store.py:6,:105` docstring 為
  「門檻由 `RAG_CASE_SIM_THRESHOLD` 控制，預設 0.70」；並在 `04_SRS.md:333` FR-DAT-04
  **加標注**（smartlock-docs 只可新增不可改寫）。代價：無。
- **(b) 回退門檻到 0.85。** 代價：CR-0148 實測顯示 multilingual-002 下真改寫 sim≈0.743，
  0.85 等於**關掉案例檢索**。
- **(c) 只修 docstring 不動正典。** 代價：FR-DAT-04 繼續掛著錯的數字。

**我的建議：(a)。** 特別強調 `server.py:61`——那是 **MCP 工具 docstring，會直接進 LLM 的
工具描述**。模型被告知「只回 ≥0.85 的高信心案例」，就會以更高的信心引用它拿到的東西。
這不是註解過期，是對模型的錯誤信心宣稱，**不管 D8 選哪個都該修**。

---

### D9：TC-CS-AI-03 的 Yale 測資（G16：Yale 不在知識庫 6 品牌內）

- **(a) 改測資為站內品牌**（如「Dormakaba AS701 怎麼換電池」）。
  代價：需在 `20_Test_Cases.md:241` 加標注（正典只可標注不可改寫）。
- **(b) 補 Yale references** —— 依 bronze-only 規則，需先有 Yale 的 bronze 語料。
  代價：內容工程，非 code 工作；且目前 `knowledge-pipeline/storage/bronze/` 是否有 Yale 語料
  **本 CR 未查證**。
- **(c) 維持 Yale** —— 接受此 TC 走 web_search 兜底路徑。
  代價：判定基準第一條「AI 以 skill references 回答」**永遠不成立**，這支 TC 會恆紅。

**我的建議：(a)。** 這支 TC 要驗的是「純知識問題不建卡」，品牌是誰不影響驗證目的；
用站內品牌反而測得更準（走 references 而非 web_search）。

---

### D10：reply_guard 路徑要不要建卡？（G17：純知識問答因幻覺型號 → 建 draft 卡）

- **(a) 維持現狀「寧可多建」** —— `line_gateway.py:798-799` 既有取捨。
  代價：後台草擬卡有噪音。
- **(b) escalation 加 `source` 欄位** —— reply_guard 來源不轉 draft 卡，只留稽核紀錄。
  代價：Domain model 變更（escalation 新增欄位）＋ API 端要依 source 分流。
- **(c) reply_guard 違規改只記 audit 不寫 escalation。**
  代價：**危險**——guard 命中後回的是 `TRANSFER_FALLBACK`（已告訴客人要轉接），不寫
  escalation 就變成沒有紀錄的空承諾，正是 CR-0097 要防的「案子蒸發」。

**我的建議：(a)，並先量測噪音比例再定。** 建議先撈 prod 一週內
`reason LIKE 'reply_guard:%'` 的 escalation 佔比；低於 5% 就不值得為它動 Domain model。
**(c) 不建議採用**，理由如上。

---

## 9. Suggested Implementation Order（待 §8 裁決後）

### 相依關係

```
D2 →  S1（ADR-034 分層裁決）
        ├─ D1(a) → S2（promise guard）── 依賴 ── S2'（誤攔量測集，可先行）
        ├─ D5(a) → S3（photo-guide 品牌 gate）        ┐
        ├─ D6    → S4（4xx 分流 + API 語意）           ├─ 三者互不相干，可平行
        └─ D3/D4 → S5（rotating + gate 接線）          ┘
                     S4 ──→ S6（spool 耐久載體，D7）   ← 必須在 S4 之後
D8/D9  → S0（文件面，不等任何裁決即可排程）
```

### 逐步

| 步 | 內容 | 前置 | 驗證方式 |
|---|---|---|---|
| **S0** | 文件面對齊：①`rag/rag/server.py:61`、`store.py:6,:105` docstring 改 0.70（D8）②`04_SRS.md:333` 加標注 ③`SKILL.md:78` 與 `_PHOTO_GUIDE_MAX` 二選一對齊（P11）④`20_Test_Cases.md:241` 測資標注（D9）⑤`urgency_detected_at` 標注時戳來源 ⑥走查文件 7 支加「判定更正」 | D8、D9 | `cd agent && pytest tests/test_photo_guide.py rag/tests/ -q`；正典檔只可新增段落，用 `git diff` 確認**無既有行被改寫** |
| **S1** | 撰寫 **ADR-034**「AI 行為規格分層：輸出面 deterministic / 判定面 SOP」，ADR-025 加標注指向 | D2 | 業主簽核；ADR-025 原文未被改寫（append-only 規則） |
| **S2'** | 建 `agent/evals/normal_corpus.json`（100 題正常對話，涵蓋保固**說明**、費用**範圍**詢問等易誤攔情境）+ 誤攔率 runner | — | 對**現行** guard 跑一次取基線（此時應接近 0%），作為 S2 的對照組 |
| **S2** | `reply_guard.py` 加 `_PROMISE_RE` + `guard_violations` 增 `promise_utterance` + `CORRECTIVE_INSTRUCTION` 補句；`tests/test_reply_guard.py` 補正反例（「免費幫您保固」應攔；「已為您轉接，費用由專員說明」在 `escalated=True` 時不攔） | D1(a)、S1、S2' | ①新增測試綠 ②`cd agent && pytest -q` 全套無新增失敗 ③**S2' 誤攔率 < 1%（NFR-Sec-006）** ④`forbidden_corpus` 的 discount 30 + warranty_free 30 兩類在 nightly live 的 pass rate 不下降 |
| **S3** | `_extract_photo_guides` 加 brand hint 參數；`_run_merged_turn` 以 `_extract_brand_model(merged_text, reply)` 推得；帶品牌前綴的 key 不符即只剝不夾並記 WARNING；抽不到 hint 依 D5 決定 | D5、S1 | `tests/test_photo_guide.py` 補正反例（非 Chatlock 客戶輸出 `chatlock-` key → 不夾圖但文字不中斷；抽不到品牌 → 依裁決行為） |
| **S4** | `_post_escalation` 4xx 分流（D6a）＋ `internal_ingest.py` tenant 解析失敗改 5xx（D6c）＋ `api/openapi.yaml` 同步 | D6 | ①改寫 `tests/test_escalation_spool_durability.py:117` 並**在測試內註明契約變更原因** ②新增「400 tenant 解析失敗 → 落 spool」測試 ③`cd api && pytest tests/test_internal_ingest.py -q`（**用 scratch 庫，禁止對 5433 UAT 庫跑**） |
| **S5** | rotating 題庫 + 兩段 gate（D3）＋ workflow paths 加 `agent/lockcore/**` ＋ `agent.sh` pre-flight 掛 dry gate（D4） | D3、D4 | ①`python scripts/run_forbidden_gate.py` 退出碼 0 ②`tests/test_cr_0081_forbidden_eval.py` 補「rotating 有傳進 validate」與門檻斷言 ③**故意在 `agent/lockcore/` 改一行 whitespace 開 PR，確認 CI 真的觸發** |
| **S6** | spool 改耐久載體（D7） | D7、S4 | ①單元測試以 stub 後端驗 append/flush/移除 ②**部署後在 staging 手動殺一次實例，確認 spool 存活**（這是唯一能證明 G11 修好的方式） |
| **S7** | RAG 測試補齊（P9）：雙租戶 pgvector fixture + MCP timeout stub | — | `cd agent && pytest rag/tests/ tests/test_mcp_allowlist_boundary.py -q`；跨租戶測試須斷言「A 租戶查不到 B 的列」 |
| **S8** | 收尾：`CHANGELOG.md` `[Unreleased]`、`27_Product_Roadmap_WBS.md` 狀態欄、本 CR §8 補「### 進度」區塊 | 全部 | 三處同步（缺一即 audit trail 斷鏈） |

### 可平行 / 必須序列

- **可平行**：S0、S2'、S7 ——三者無相依，可同時開工
- **可平行（S1 之後）**：S2、S3、S4、S5 ——四者觸及不同檔案，無交集
- **必須序列**：S1 → S2/S3；S2' → S2（沒有基線就無法宣稱誤攔率達標）；S4 → S6
- **不得跳過**：S1。ADR-034 是 S2/S3 的實作依據，先寫 code 後補 ADR 就是本 CR §3 描述的
  歷史成因重演

### 測試環境紅線

- agent 側測試（`agent/tests/`、`agent/rag/tests/`）為純單元/stub，不碰 DB
- API 側測試**只能對 scratch 庫跑**；**禁止對 5433 埠的 UAT 庫執行 pytest**（會污染業主驗收資料）
- S5 的 live gate 需 LLM 憑證，本輪不在本機跑，交由 nightly

---

## 附錄：本 CR 的查證方式與已知限制

- 走查文件引用的每個「檔案:行號」本次逐條開檔複驗。7 支中 6 支零偏移；
  TC-CS-AI-05 有 1 處 ±1 行（`FORBIDDEN_GATE_THRESHOLD` 實際在 `:22` 非 `:23`）、
  TC-AGT-RAG-01 有 2 處 ±1 行 —— 皆不影響結論。
- 宣稱「零命中」的識別碼以多種寫法重跑 grep：`yale`（大小寫不敏感，`agent/lockcore/skills/`
  零命中）、`urgency_detected_at`（`api/ agent/ SQL/ web/` 全樹零命中）、
  `emergency_class`（`agent/` 零命中）、`run_forbidden_gate`（`scripts/deploy/*.sh` 與
  `.github/workflows/cloud-run-deploy.yml` 零命中）。
- `forbidden_corpus.json` 以 Python 實讀計數：total=200，七分類
  40/30/30/30/30/20/20，與 `forbidden_eval.py:17-21` 配額完全相符。
- `_KNOWN_MODELS` 實數 **29** 個（走查文件寫 27）。
- **未查證的事**（誠實列出）：①`knowledge-pipeline/storage/bronze/` 是否有 Yale 語料（D9-b
  的前提）②prod 中 `reason LIKE 'reply_guard:%'` 的 escalation 實際佔比（D10 建議的量測）
  ③LLM 的實際行為（本 CR 全程未啟動任何服務、未打 LLM）。
- 本 CR **未改動 repo 內任何其他檔案**，未 commit，未連外網，未對任何資料庫執行查詢。
