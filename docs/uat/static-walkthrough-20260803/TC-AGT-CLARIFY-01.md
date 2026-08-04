# TC-AGT-CLARIFY-01 — Clarify gate：三輪未釐清轉真人、已釐清寫 confirmation、低相似度不假稱命中

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動 agent；實跑 agent 測試套件（330 passed / 5 failed / 12 skipped，5 項失敗全為 Windows symlink 權限，見步驟 6） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `agent/lockcore/skills/locksmith-cs-sop/SKILL.md`、`agent/lockcore/agent/tools/transfer.py`、`agent/lockcore/agent/reply_guard.py`、`agent/lockcore/agent/loop.py:1455-1520`、`agent/rag/rag/{server,store}.py`、`api/services/problem_card_service.py`、`SQL/Schema.sql`、`smartlock-docs/enterprise/04_SRS.md:278/595`、`smartlock-docs/enterprise/14_ADR/ADR-033_轉真人判準_SOP情境式紅線_取代三輪硬計數.md` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | TC 指名的兩個識別碼在程式碼樹**零命中**：`clarification_attempts` 與 `clarification_confirmed_at` 於 `api/`、`agent/`、`SQL/`、`web/` 全樹皆無命中，即 TC 步驟的「連續三輪未釐清」計數器與「已釐清寫 confirmation」欄位皆無實作。此狀態已由正典自我標註：`smartlock-docs/enterprise/04_SRS.md:595` 明載「三輪硬計數廢止（正典讓步於 SOP 演進）」「`clarification_attempts` 計數器 agent/api/DB 皆未實作（欄位為文件孤兒）」，並立 ADR-033（status: active）記錄該演進。現行轉真人判準為 SOP 紅線觸發即轉（`agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 2 點）。第三條判定基準「低相似度不假稱命中案例」有落點：RAG 案例檢索以 SQL 閾值過濾（`agent/rag/rag/store.py:126`），低於閾值回空清單，工具 docstring 明載「空清單 = 無足夠相似案例」（`agent/rag/rag/server.py:69`）。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：已確認問題卡、可控 RAG fixture
- 步驟：連續三輪客戶回覆未釐清，再送已釐清；另注入低相似度案例
- 預期結果（判定基準）：未釐清依規則轉真人；已釐清寫 confirmation；低相似度不假稱命中案例
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-AGT-03｜屬於旅程腳本：—

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| `clarification_attempts` 計數 | — | **找不到**：全樹零命中 |
| 連續三輪未釐清 → 自動轉真人 | — | **找不到**：無輪次計數判定 |
| 未釐清「依規則」轉真人（現行判準） | `agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 2 點 | 有（SOP 紅線，prompt 層） |
| 已釐清寫 `clarification_confirmed_at` | — | **找不到**：全樹零命中 |
| 問題卡確認（最接近的既有狀態轉移） | `api/services/problem_card_service.py:298-330` | 有（`incomplete → confirmed`，人工觸發） |
| 低相似度不回傳案例 | `agent/rag/rag/store.py:126`、`:18` | 有（SQL 閾值過濾） |
| 空結果的語意宣告 | `agent/rag/rag/server.py:49`、`:69` | 有（工具 docstring） |
| 不編造（生成後 guard） | `agent/lockcore/agent/reply_guard.py:28-56`、`agent/lockcore/agent/loop.py:1468-1519` | 有（未溯源型號／價格 regex + regen 1 次 + 轉真人兜底） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 第 1 輪回覆仍未釐清 | `ClarificationAttempted(n=1)` | 計數 | — | **找不到**：無計數器 |
| 客戶 | 第 3 輪仍未釐清 | `EscalatedByRule` | `attempts ≥ 3` | — | **找不到**：無此判定 |
| 客戶 | 觸發紅線（要求真人／金錢／急迫派工／連續兩次不滿） | `TransferredToHuman` | SOP 紅線 | `agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 2 點、`agent/lockcore/agent/tools/transfer.py:132-169` | LLM 呼叫 `transfer_to_human` → 寫 escalation + 回核對表單 |
| 客戶 | 送出已釐清資訊 | `ClarificationConfirmed` | 寫 confirmation | — | **找不到**：無 `clarification_confirmed_at` 欄位 |
| 客服 | 確認問題卡 | `ProblemCardConfirmed` | 狀態機 | `api/services/problem_card_service.py:298-330` | `incomplete → confirmed`，非 confirmed 來源 → 409 `STATE_CONFLICT` |
| agent | 查相似案例（低相似度） | `NoSimilarCases` | 閾值 | `agent/rag/rag/store.py:126` | `AND 1 - (embedding <=> %s::vector) >= %s` → 空清單 |
| agent | 回覆中出現未溯源型號 | `ReplyGuardViolation` | 不編造 | `agent/lockcore/agent/loop.py:1468-1476` | 修正重生 1 次；仍違規 → `TRANSFER_FALLBACK` + 記 escalation |

---

## 逐層走查

### 步驟 1 — TC 指名識別碼的 grep 結果

- **動作**：全程式碼樹搜尋 FR-AGT-03 的兩個欄位
- **預期**：至少一個非零命中
- **實際**：兩者皆零命中

```
git grep -rn "clarification_attempts\|clarification_confirmed_at\|urgency_detected_at" -- api/ agent/ SQL/ web/
（無輸出，exit=1）
```

### 步驟 2 — 正典對此狀態的自我標註

`smartlock-docs/enterprise/04_SRS.md:278`（FR-AGT-03 原文列）

```
| FR-AGT-03 | 三層解決 + Clarify gate | PC confirmed | 案例庫（相似度 ≥ 0.85）→ RAG → AI 主動詢問「問題釐清了嗎？」 | 已釐清寫 `clarification_confirmed_at`；連續 3 次未釐清升級轉真人 | BR-PC-002；UC-005 |
```

`smartlock-docs/enterprise/04_SRS.md:590-595`

```
〔標注 2026-07-22（agent 域 UAT-0720-01 稽核，業主裁決 3-1「正典讓步」；不改寫原文，僅新增本段。詳 [ADR-033](./14_ADR/ADR-033_轉真人判準_SOP情境式紅線_取代三輪硬計數.md)〕

| 原文 | 裁決與現況 |
|---|---|
| **FR-AGT-03**（§3.1）「連續 3 次未釐清升級轉真人」＋ … | **三輪硬計數廢止（正典讓步於 SOP 演進）**——`locksmith-cs-sop` SKILL.md Step 3 明文不採「問三次仍缺就轉真人」硬規則，缺項情境式一次列齊；轉真人判準＝紅線觸發即轉（明確要求真人／急迫派工／金錢相關／連續兩次不滿）。`transfer_to_human` 唯一出口（FR-AGT-05）與 deterministic 兜底（NFR-Rel-003 案子不蒸發）**不變**。`clarification_attempts` 計數器 agent/api/DB 皆未實作（欄位為文件孤兒）；Clarify gate「問題釐清了嗎」保留為話術原則、非硬性狀態機轉移。 |
```

ADR-033 frontmatter 為 `status: active`（`smartlock-docs/enterprise/14_ADR/ADR-033_轉真人判準_SOP情境式紅線_取代三輪硬計數.md:4`），其 Context 段自述觸發原因：「0720 外部測試（Irene）問『為何沒三輪就轉真人』→ 碼稽核揭露規格正典（FR-AGT-03 三輪硬計數）與現行實作（SOP 情境式紅線）為 Source-of-Truth 衝突」。

TC 步驟寫「連續三輪客戶回覆未釐清，再送已釐清」、判定基準寫「已釐清寫 confirmation」（出處：② 測試案例主表 TC-AGT-CLARIFY-01 列，追溯 FR-AGT-03）／程式碼無此計數器與欄位，且正典已於 `04_SRS.md:595` 與 ADR-033 記錄該行為被 SOP 情境式紅線取代。此處僅並陳，不裁定。

### 步驟 3 — 現行的追問與轉真人判準

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 2 點：

```
2. **明確要求真人 / 金錢相關(報價·費用·退費·發票·付款) / 急迫派工 / 連續不滿**
   → 呼叫 `transfer_to_human`,**不報價、不追問**。**該工具回傳的核對表單請原封不動回覆給客戶,不要改寫**。
```

同檔 Step 3「必抓資訊 & 追問原則(**情境式問答,非 rule-based**)」：

```
- **缺資料時,把該情境所有缺的關鍵項目「一次列給客人」**(條列、簡短、易回);不要每次只問一條再等回覆,也不要用「問三次仍缺就轉真人」這種硬規則。
```

同檔 Step 1 前的「單一進線鐵律」：

```
> ⛔ **單一進線鐵律(先記)**:`transfer_to_human` 是**唯一**能把案子送進後台(問題卡→客服→工單→派師傅)
> 的工具。**轉真人與派工都走它。**
```

工具實作 `agent/lockcore/agent/tools/transfer.py:132-169`，執行時寫 escalation（`:154-162`）並回傳模板（`:169`）。

該工具無輪次判定：全檔對 `attempt` / `count` / `round` 零命中。

### 步驟 4 — 「已釐清」在程式碼中最接近的狀態轉移

`api/services/problem_card_service.py:298-315`

```python
async def confirm_card(*, tenant_id: str, pc_id: str) -> dict:
    """incomplete → confirmed。對齊 OpenAPI draft → confirmed。

    CR-0132 Gate①（進料閘，15_SDS §4.6）：M18 config `problemcard_policy.gate1_enforce`
    開啟時，confirm 前必過 §4.6 必填集（contact_phone/brand/model/failure_mode/
    triage_tier＋L3 location）——未過 → 422 INTAKE_GATE_UNMET。預設 off（沿用
    CR-0042 convert 閘行為）；前端補齊分流欄位 UI 上線後由業主開啟。
    """
    ...
    current = await _fetch_status_for_update(pc_id, tenant_id)
    if current not in _CONFIRM_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot confirm problem card in status '{current}'; expected 'incomplete'",
            409,
        )
```

該轉移由客服人員經認證端點觸發，非 agent 自動；`problem_cards` 表無 clarification 相關欄位（`SQL/Schema.sql` 內 `clarification` 零命中）。

### 步驟 5 — 低相似度不假稱命中案例

閾值定義 `agent/rag/rag/store.py:15-18`

```python
# ADR-010 原訂 0.85 係按 text-embedding-004 設想;CR-0124 換 multilingual-002 後
# 實測(CR-0148,2026-07-10):語意明確相符的中文改寫查詢 sim≈0.74 → 0.85 恆不命中。
# 門檻綁模型須隨模型校正:env 可調,預設 0.70(高於雜訊、涵蓋真改寫)。
CASE_SIMILARITY_THRESHOLD = float(os.getenv("RAG_CASE_SIM_THRESHOLD", "0.70"))
```

過濾在 SQL 層 `agent/rag/rag/store.py:114-134`：

```sql
            SELECT id::text AS id, brand, model,
                   problem_description AS symptom, solution AS resolution,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM case_entries
            WHERE tenant_id = %s
              AND embedding IS NOT NULL
              AND is_active
              AND deleted_at IS NULL
              AND (%s::varchar IS NULL OR brand = %s OR brand = 'general')
              AND (%s::varchar IS NULL OR model = %s OR model = 'general')
              AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
```

工具契約 `agent/rag/rag/server.py:58-69`：

```python
@mcp.tool()
def search_similar_cases(symptom: str, brand: str | None = None,
                         model: str | None = None) -> list[dict]:
    """以症狀描述檢索歷史案例（症狀 → 解法），只回相似度 ≥ 0.85 的高信心案例。
    ...
    Returns:
        高相似案例（symptom/resolution/similarity）；空清單 = 無足夠相似案例。
    """
```

TC 前置的 FR-AGT-03 與 SRS `04_SRS.md:278` 寫「案例庫（相似度 **≥ 0.85**）」、`server.py:61` docstring 亦寫「≥ 0.85」／實際生效門檻為 `store.py:18` 的 `RAG_CASE_SIM_THRESHOLD` 預設 `0.70`。此處僅並陳，不裁定。

生成後的不編造守線在 agent loop 出口，`agent/lockcore/agent/reply_guard.py:1-8`：

```python
"""生成後回覆 guard（ADR-025 server-side enforce／CR-0152）。

憲章要求「不依賴 prompt」：價格 utterance（金額數字未轉真人就出口）與
未溯源型號（客戶沒提過的具體型號代碼＝幻覺訊號）屬確定性 regex 判定，
在 loop 出口攔截——修正重生 1 次，仍違規改走轉真人話術＋記 escalation
（業主裁決 2026-07-10）。
```

接線點 `agent/lockcore/agent/loop.py:1468-1475`：

```python
        escalated = "transfer_to_human" in (tools_used or [])
        violations = guard_violations(
            final_content or "", customer_text, escalated=escalated
        )
        if not violations:
            return final_content, tools_used, all_msgs

        logger.warning("[reply-guard] 違規 {} → 修正重生 1 次", violations)
```

regen 仍違規的終局 `agent/lockcore/agent/loop.py:1506-1519`：

```python
        # regen 仍違規 → server-generated 轉真人話術＋記 escalation（可稽核）
        logger.error("[reply-guard] regen 仍違規 {} → 轉真人話術", violations)
        if self._escalation_store is not None and ctx.msg.sender_id:
            try:
                self._escalation_store.log(
                    self._memory_tenant,
                    ctx.msg.sender_id,
                    "reply_guard:" + ";".join(violations),
                    False,
                    {"turn_id": ctx.turn_id},
                )
```

### 步驟 6 — 執行既有測試

```
cd agent && python -m pytest tests/ -q
5 failed, 330 passed, 12 skipped in 8.24s
```

5 項失敗全在 `tests/test_skill_sync.py`，成因為 Windows 建立 symlink 需特殊權限：

```
E   OSError: [WinError 1314] 用戶端沒有這項特殊權限。: '.skills-v1' -> '…\\skills.tmp'
lockcore\agent\skill_sync.py:210: OSError
```

對應程式碼 `agent/lockcore/agent/skill_sync.py:205-211`：

```python
    @staticmethod
    def _atomic_symlink(target_dir: Path, link_path: Path) -> None:
        tmp_link = link_path.parent / (link_path.name + ".tmp")
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()
        os.symlink(target_dir.name, tmp_link)  # 相對 symlink（同層）
        os.replace(tmp_link, link_path)        # 原子換裝
```

此為執行環境（Windows 未開啟開發者模式／未授予 `SeCreateSymbolicLinkPrivilege`）所致，與本 TC 走查對象無關。

`git grep -rni "clarif" -- agent/tests api/tests` 零命中，即無對應既有測試。

---

## 既有測試證據

- agent 測試套件：330 passed / 5 failed（Windows symlink 權限）/ 12 skipped。
- 無對應既有測試涵蓋 Clarify gate 三輪計數與 `clarification_confirmed_at`——兩者在程式碼中不存在。
- RAG 相似度閾值的既有測試在 `agent/rag/tests/`（`test_mcp_integration.py`），需 pgvector 環境。

---

## 觀測到的其他事實

1. **`transfer_to_human` 的 `is_explicit` 僅供稽核、不作 gating**：`agent/lockcore/agent/tools/transfer.py:1-12`

```python
2. 偵測當前 user input 是否含「顯式要求真人 / 金錢」關鍵字(is_explicit,僅供稽核)。
...
不做 gating(由 system prompt 教 LLM「先試查產品資料」),不做防詐 guard(嘴上說轉沒 call)。
```

關鍵詞清單在 `:27-36`（含「轉真人」「報價」「退費」等 30 餘項）。

2. **「連續兩次不滿」為 SOP 文字判準，不是程式計數**：`agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 2 點的「連續不滿」由 LLM 判讀；程式端的情緒判定在 `agent/lockcore/agent/sentiment.py`，其 `:6-8` 自述「純函式介面（吃 provider + text，回結構化結果），無 I/O 副作用；寫庫/通知由呼叫端…負責」，未回傳連續次數。

3. **reply_guard 的型號清單為人工維護**：`agent/lockcore/agent/reply_guard.py:35-38` 註解要求與 `references/{Brand}/*.md` 同步，並由 `agent/tests/test_reply_guard_model_list.py` 比對漂移。

4. **`04_SRS.md:278` 的「PC confirmed」為 FR-AGT-03 的前置條件**，而問題卡 confirm 由客服端點觸發（`api/services/problem_card_service.py:298`）；agent 唯一寫入通道最多建 draft 卡（`api/routers/internal_ingest.py:16`）。
</content>
