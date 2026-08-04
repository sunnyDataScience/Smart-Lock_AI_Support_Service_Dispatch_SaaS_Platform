# TC-NFR-DQ-01 — Python 覆寫不可信 provenance；核可率與誤放率可入報表

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 + 一次性探針（探針腳本不在 repo 內，僅於 scratchpad 執行） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / failure |

判定理由（事實）：TC 判定基準兩項中，「Python 覆寫不可信 provenance」有落點且以探針實測驗證——注入回傳假 `source_type="gdrive"` / `source="attacker-controlled"` 的 fake LLM，輸出仍為 Python 字面的 `source_type="youtube"` / `source="REAL_VIDEO_ID"`（步驟 2）。「核可率…可計算入報表」有落點（`api/services/sop_performance_service.py:94-99` 的 `approval_rate_pct`）；「誤放率」在程式碼中無對應——`誤放` / `misplac` / `false_positive` 三個關鍵字在 `knowledge-pipeline` 與 `api` 的知識相關程式碼零命中（步驟 5），且 NFR-DQ-004 的目標值在正典中即標為 `[待確認]`。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | 可竄改 provenance 與審核抽樣 fixture |
| 步驟 | 令 LLM 回傳假 source/source_type；抽樣核對核可與誤放資料 |
| 預期結果（判定基準） | Python 覆寫不可信 provenance；核可率與誤放率可計算入報表 |
| 路徑類型 | failure |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | NFR-DQ-002、NFR-DQ-004 |
| 屬於哪條旅程腳本 | — |

需求原文（`smartlock-docs/enterprise/05_NFR.md:173`、`:175`）：

```
| NFR-DQ-002 | Provenance 正確性 | silver `source`/`source_type` 由 Python 強制覆寫（防 LLM 幻覺竄改）| pipeline 單元測試 | 營運目標 |
| NFR-DQ-004 | 審核品質 | HITL 為品質防線；核可通過率 / 抽樣誤放率門檻 `[待確認]` | 抽樣人審 | 營運目標 |
```

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| `source_type` 由 Python 覆寫 | `process_youtube.py:107`、`process_video.py:121`、`process_website.py:122`、`process_line.py:132`、`process_gdrive.py:92` | 有落點 |
| `source` 由 Python 覆寫 | `process_youtube.py:108`、`process_video.py:122`、`process_website.py:123`、`process_line.py:133`、`process_gdrive.py:93` | 有落點 |
| 覆寫的值取自 bronze 而非 LLM | `process_youtube.py:86-87` | 有落點 |
| refinery 軌 provenance 全由 Python 組 | `knowledge-pipeline/refinery/refinery/refine.py:105-112` | 有落點 |
| corpus provenance 由 Python 從實檔計算 | `emit_corpus.py:102-116`、`_provenance.py:36-71` | 有落點 |
| provenance 造假可被 gate 擋 | `audit_corpus.py:51-66` | 有落點 |
| HITL 硬 gate（未核可不落地） | `knowledge-pipeline/refinery/refinery/review.py:3-5`、`:89-95` | 有落點 |
| 核可率可計算入報表 | `api/services/sop_performance_service.py:91-99` | 有落點（SOP 草稿軌） |
| 誤放率可計算入報表 | — | **無對應**（步驟 5） |
| pipeline 單元測試（NFR-DQ-002 驗證方式） | — | **無對應**（步驟 6） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| LLM | 回傳 metadata 含假 `source_type` | （不得生效） | provenance 不信任 LLM | `process_youtube.py:105-111` | Python 字面鍵位於 `**item["metadata"]` 之後，覆蓋之 |
| LLM | 回傳假 `source` | （不得生效） | 同上 | `process_youtube.py:108` | 以 bronze 的 `video_id` 覆寫 |
| pipeline | silver → corpus | `ChunkEmitted(provenance)` | bronze 實檔計算 | `emit_corpus.py:102` | `resolve_bronze()` 走檔案系統 + sha256 |
| CI／人工 | 語料稽核 | `AuditPassed` / `Violation(exit 1)` | 5 項檢查 | `audit_corpus.py:33-77` | provenance 缺／漂移／gdrive 進 facts 皆列 violation |
| 審核者 | approve draft | `DraftApproved` → Publisher | HITL 硬 gate | `review.py:89-95` | 樂觀鎖 `WHERE status='pending_review'`，approve 時才呼 Publisher |
| 審核者 | reject draft | `DraftRejected(audit)` | 留 audit | `review.py:111-116` | 狀態轉 `rejected` |
| 營運 | 查核可率 | `ApprovalRateReported` | NFR-DQ-004 | `api/services/sop_performance_service.py:94-96` | `approved / (approved + rejected)` |
| 營運 | 查誤放率 | `MisplacementRateReported` | NFR-DQ-004 | — | **找不到**：無對應欄位、計算或端點 |

---

## 逐層走查

### 步驟 1 — 覆寫點的程式碼結構

`knowledge-pipeline/pipeline/bronze_to_silver/process_youtube.py:84-113`：

```python
def process_one_file(llm_func: Callable, bronze_data: dict) -> list[dict]:
    """Process a single bronze YouTube JSON through LLM rewriting."""
    video_id = bronze_data["video_id"]
    url = bronze_data["url"]
    title = bronze_data["title"]
    transcript = bronze_data["transcript"]

    user_prompt = f"影片標題：{title}\n\n逐字稿內容：\n{transcript}"

    chunks = llm_func(user_prompt, SYSTEM_PROMPT, RESPONSE_SCHEMA)

    if not isinstance(chunks, list) or len(chunks) == 0:
        raise ValueError("LLM response is not a non-empty array")

    final_documents = []
    for i, item in enumerate(chunks):
        for field in ("content", "metadata"):
            if field not in item:
                raise ValueError(f"Chunk {i}: missing '{field}'")

        doc = {
            "content": item["content"],
            **item["metadata"],
            "source_type": "youtube",
            "source": video_id,
            "url": url,
            "chunk_index": i + 1,
        }
        final_documents.append(doc)

    return final_documents
```

覆寫機制為 Python dict 字面的鍵順序：`**item["metadata"]`（LLM 產出）展開在前，四個字面鍵在後，後者勝出。`video_id`（`:86`）與 `url`（`:87`）取自 `bronze_data`。

同型結構在其餘 4 個處理器（行號見「逐條驗收條件對照」）。`process_gdrive.py:87-96` 不展開 LLM metadata，只逐鍵取 `brand` / `model` / `content` 三欄。

### 步驟 2 — 探針：注入假 provenance 的 LLM

**此探針腳本不在 repo 內**（位於 scratchpad，未提交、未修改任何 repo 檔案）。輸入為一個回傳假 `source_type` / `source` / `url` / `chunk_index` 的 fake `llm_func`：

```python
def fake_llm(user_prompt, system_prompt, schema):
    return [{
        "content": "假內容",
        "metadata": {
            "brand": "Fake", "model": "X",
            "source_type": "gdrive",          # LLM 謊報
            "source": "attacker-controlled",  # LLM 謊報
            "url": "https://evil.example",
            "chunk_index": 999,
        },
    }]

bronze = {"video_id": "REAL_VIDEO_ID", "url": "https://youtu.be/REAL", "title": "t", "transcript": "x"}
out = process_one_file(fake_llm, bronze)
```

實際輸出：

```json
[
  {
    "content": "假內容",
    "brand": "Fake",
    "model": "X",
    "source_type": "youtube",
    "source": "REAL_VIDEO_ID",
    "url": "https://youtu.be/REAL",
    "chunk_index": 1
  }
]
```

四個 provenance 欄位（`source_type` / `source` / `url` / `chunk_index`）皆為 Python 端的值；LLM 提供的 `brand` / `model` 兩個非 provenance 欄位原樣通過。

### 步驟 3 — 下游：corpus 層的 provenance 由實檔計算

`knowledge-pipeline/pipeline/silver_to_knowledge/emit_corpus.py:97-117`：

```python
    source_type = doc.get("source_type", "unknown")
    source = doc.get("source", "unknown")
    idx = str(doc.get("chunk_index", "0"))
    content = doc.get("content", "")

    bronze_path, bronze_sha = resolve_bronze(source_type, source)
    record = {
        ...
        "provenance": {
            "bronze_path": bronze_path,
            "bronze_sha256": bronze_sha,
            "emitted_at": run_at,
        },
    }
```

`resolve_bronze` 走檔案系統並計算 sha256（`_provenance.py:16-21`、`:50-71`）。若 silver 的 `source` 被竄改成不存在的值，`resolve_bronze` 回 `(None, None)`，該 chunk 進入 `emit_corpus.py:156-159` 的 `missing_bronze` 清單，並在 `audit_corpus.py:57-59` 被列為 violation：

```python
            if not bp or not bs:
                violations.append(f"{where} — provenance 不完整（bronze_path/sha256 缺）")
                continue
```

若 `source` 被改成另一個真實存在的 bronze 檔，sha256 仍會與該檔一致；此路徑的偵測依賴 `audit_corpus.py:62-66` 的「bronze 檔存在且 sha256 相符」，不含「內容是否確實來自該檔」的語義比對。

### 步驟 4 — refinery 軌（問題卡 → draft）的 provenance

`knowledge-pipeline/refinery/refinery/refine.py:103-129`：

```python
    result = generate(_build_prompt(card, transcript), SYSTEM_PROMPT, REFINE_SCHEMA)

    provenance = {
        "problem_card_id": card["id"],
        "conversation_id": card.get("conversation_id"),
        "message_count": len(transcript),
        "spine": _spine_snapshot(card),
        "llm_model": llm_model,
        "refined_at": refined_at,
    }

    drafts: list[dict] = []

    ce = result["case_entry"]
    ce_payload = {"symptom": ce["symptom"], "resolution": ce["resolution"]}
    drafts.append({
        "draft_key": draft_key(card["id"], "case_entry", ce_payload),
        "draft_type": "case_entry",
        "source_problem_card_id": card["id"],
        "source_conversation_id": card.get("conversation_id"),
        ...
        "provenance": provenance,
```

`provenance` 的 6 個值全部取自函式引數或 `card`；LLM 的 `result` 只供應 `title` / `symptom` / `resolution` / `confidence`。檔頭 `refine.py:8`：

```
不得編造:LLM 只能整理卡欄位與逐字稿既有資訊;provenance 記全程溯源。
```

### 步驟 5 — 核可率與誤放率

**HITL gate**，`knowledge-pipeline/refinery/refinery/review.py:3-5`（檔頭）：

```
轉移(僅 pending_review 可動作;HITL 硬 gate:approve 時才呼叫 Publisher):
  pending_review → approved(事實軌落 case_entries;行為軌產 patch artifact)
                 → rejected(留 audit)
```

狀態轉移含樂觀鎖，`review.py:70-86`：

```python
    """pending_review → to_status(樂觀鎖:WHERE status='pending_review')。不 commit。"""
            SET status = %s, review_comment = %s, reviewed_by = %s::uuid,
            ...
            WHERE tenant_id = %s AND id = %s AND status = 'pending_review'
```

**核可率**，`api/services/sop_performance_service.py:7`（檔頭）與 `:91-99`：

```python
  - approval_rate = approved / (approved + rejected)
...
    approved = status_dist["approved"]
    rejected = status_dist["rejected"]
    published = status_dist["published"]
    decided = approved + rejected
    approval_rate = (
        round(100.0 * approved / decided, 2) if decided > 0 else 0.0
    )
```

回傳於 `api/services/sop_performance_service.py:152-155` 的 `rates.approval_rate_pct`，前端消費點 `web/brand-portal/src/app/admin/knowledge-base/sop-performance/page.tsx:14`、`:155`。該指標的資料源為 `sop_drafts` 表（`sop_performance_service.py:61-64`），非 refinery 的 `knowledge_drafts`。

`knowledge-pipeline/refinery/refinery/` 內無比率計算：

```
git grep -rn "approval_rate\|rate" -- knowledge-pipeline/refinery/refinery
knowledge-pipeline/refinery/refinery/intake.py:5:  AND 無「活的」draft（pending_review/approved/rejected/superseded 任一存在即跳過；
knowledge-pipeline/refinery/refinery/llm.py:14:# generate_json(prompt, system_prompt, schema) -> dict
knowledge-pipeline/refinery/refinery/llm.py:15:GenerateJson = Callable[[str, str, dict], dict]
（其餘命中皆為 GenerateJson 型別別名）
```

**誤放率**：

```
git grep -rn "誤放\|false_positive\|misplac" -- knowledge-pipeline api web/brand-portal/src
knowledge-pipeline/refinery/refinery/entitlement.py:45:    except Exception:  # noqa: BLE001 — DB 失敗 → fail-closed（不誤放未開通租戶）
web/brand-portal/src/lib/appMode.ts:79:    // (2026-07-05 業主裁決:消除 3000 與 3002 landing 重複 + 品牌後台入口誤放師父 CTA)。
```

兩處命中皆為註解中的其他語意用法，非誤放率指標。

TC 判定基準寫「核可率與誤放率可計算入報表」（出處：`smartlock-docs/enterprise/20_Test_Cases.md` TC-NFR-DQ-01 列）／程式碼有核可率（來源為 `sop_drafts`），無誤放率的欄位、計算或端點；NFR-DQ-004 在 `05_NFR.md:175` 的目標值本身標為 `[待確認]`。此處僅並陳，不裁定。

### 步驟 6 — pipeline 單元測試

NFR-DQ-002 的驗證方式為「pipeline 單元測試」。`knowledge-pipeline/pipeline/` 下無測試檔：

```
find knowledge-pipeline -name "test*" -o -name "tests" -type d
./refinery/tests
./refinery/tests/test_entitlement.py
./refinery/tests/test_intake_component.py
./refinery/tests/test_observability.py
./refinery/tests/test_oidc_auth.py
./refinery/tests/test_refine_unit.py
./refinery/tests/test_review_service.py
```

6 個測試檔全在 `refinery` 子專案，涵蓋 entitlement / intake / observability / oidc / refine / review；`pipeline/bronze_to_silver/` 與 `pipeline/silver_to_knowledge/` 無對應測試。

---

## 既有測試證據

實跑語料稽核（涵蓋 provenance 完整性與 bronze 未漂移）：

```
cd knowledge-pipeline && python -m pipeline.silver_to_knowledge.audit_corpus
✅ 稽核通過：facts=862 behavior=0，provenance 完整、bronze 未漂移、紅線無違規
```

`knowledge-pipeline/pipeline/` 無對應 pytest；`refinery/tests/test_refine_unit.py` 為 refine 軌的單元測試（本次未執行，該子專案有獨立 `pyproject.toml`）。

`api/` 側對應核可率的測試：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0164_family_review_gate.py tests/test_sop_performance.py \
  -p winloop_plugin -q
9 passed in 0.95s
```

其中 `api/tests/test_sop_performance.py:77-78`：

```python
    # approval_rate = 10/(10+2) = 83.33%
    assert result["rates"]["approval_rate_pct"] == 83.33
```

---

## 事實結論

1. `source_type` / `source` 的覆寫機制為 Python dict 字面鍵順序，5 個 bronze→silver 處理器一致。
2. 探針實測：注入謊報 `source_type="gdrive"` / `source="attacker-controlled"` 的 fake LLM，輸出仍為 `"youtube"` / `"REAL_VIDEO_ID"`；LLM 提供的非 provenance 欄位（brand/model）原樣通過。
3. corpus 層的 `bronze_path` / `bronze_sha256` 由 `resolve_bronze()` 走檔案系統實算，非 LLM 提供。
4. provenance 缺失或 bronze sha256 漂移會被 `audit_corpus.py` 列為 violation 並以 exit 1 阻斷。
5. refinery 軌的 `provenance` 6 個鍵全部由 Python 從 `card` 與函式引數組成。
6. HITL 為硬 gate：`review.py` 的狀態轉移帶 `WHERE status='pending_review'` 樂觀鎖，approve 時才呼 Publisher。
7. 核可率 `approval_rate_pct` 存在於 `api/services/sop_performance_service.py`，資料源為 `sop_drafts`；refinery 的 `knowledge_drafts` 無比率計算。
8. 誤放率在 `knowledge-pipeline`、`api`、`web/brand-portal/src` 三處皆零命中；NFR-DQ-004 的門檻值在正典中標為 `[待確認]`。
9. `knowledge-pipeline/pipeline/` 無單元測試檔；6 個測試檔全在 `refinery` 子專案。
