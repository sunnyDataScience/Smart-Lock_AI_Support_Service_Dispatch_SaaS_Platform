# TC-COMPLIANCE-08 — references provenance（bronze-only、PDF 僅引 URL、Python 強制覆寫）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補實跑 `audit_corpus` 與語料統計，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

判定理由（事實）：TC 判定基準三項在 **語料軌（`knowledge-pipeline/storage/corpus/`）** 全部有機器可查核的落點——bronze-only 由 `audit_corpus.py:52-53` 的紅線檢查擋、PDF/gdrive 內容不落地由 `emit_corpus.py:118-122` 保證、provenance 由 Python 字面覆寫（`process_youtube.py:105-111` 等 5 個處理器）。實跑 `audit_corpus` 通過，862 筆 facts 全數帶 bronze_path + sha256、19 筆 gdrive 全數 `text` 缺席。但 TC 字面指名的 **`references`**（`agent/lockcore/skills/locksmith-product-knowledge/references/`）是另一份人工撰寫的檔案樹，其內容不由 `emit_corpus` 產出、不帶 `provenance` 欄位、也不在 `audit_corpus` 的掃描範圍內（`CORPUS_DIR` 指向 `storage/corpus`，`audit_corpus.py:23`）——該樹只有 PDF 僅引 URL 一項可被靜態確認（步驟 5）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 11. 合規案例（TC-COMPLIANCE） |
| 前置 | （未列） |
| 步驟 | 檢查 references provenance |
| 預期結果（判定基準） | 內容嚴格源自 bronze 層；PDF 來源僅 URL 引用；provenance 由 Python 強制覆寫（不信任 LLM 產生） |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-AGT-07、FR-DAT-01、FR-REF-01、FR-REF-04、NFR-DQ-001、NFR-DQ-003 |
| 屬於哪條旅程腳本 | SC-15 |

需求原文（`smartlock-docs/enterprise/05_NFR.md:172`）：「NFR-DQ-001｜知識來源可信度｜100% 源自 bronze（bronze-only sourcing）；PDF 只引 URL 不抄內容｜Publisher 灌注前 source 白名單校驗 + 抽查｜合約下限（知識正確性紅線）」。
同檔 `:174`：「NFR-DQ-003｜Pipeline 冪等｜重跑同一 bronze 不產生重複 silver 知識點｜重跑比對測試｜營運目標」。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 語料 chunk 帶 bronze_path + sha256 | `knowledge-pipeline/pipeline/silver_to_knowledge/emit_corpus.py:112-116` | 有落點 |
| bronze 檔存在且未漂移（sha256 比對） | `knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:55-66` | 有落點 |
| gdrive 內容不入 facts（紅線） | `audit_corpus.py:51-53`、`emit_corpus.py:44-50`、`:118-122` | 有落點 |
| PDF 僅引 URL | `emit_corpus.py:122`（語料軌）；`references/Dormakaba/AS701.md:127-131`（skill 軌） | 有落點 |
| provenance 由 Python 覆寫 | `process_youtube.py:105-111`、`process_video.py:119-122`、`process_website.py:120-123`、`process_line.py:130-133`、`process_gdrive.py:87-96` | 有落點 |
| pipeline 冪等（同內容不重複） | `_provenance.py:24-27`、`emit_corpus.py:145-147` | 有落點 |
| `references/` 樹帶 provenance | — | **無對應**（步驟 5） |
| `references/` 樹在自動稽核範圍內 | — | **無對應**（`audit_corpus.py:23` 只掃 `storage/corpus`） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| pipeline | bronze → silver（LLM 改寫） | `SilverDocEmitted` | provenance 不信任 LLM | `process_youtube.py:105-111` | dict 字面 `source_type`/`source` 置於 `**item["metadata"]` **之後**，覆蓋 LLM 產出 |
| pipeline | silver → corpus | `ChunkEmitted(provenance)` | 每 chunk 可回溯 bronze | `emit_corpus.py:102-117` | `resolve_bronze()` 回 (相對路徑, sha256) 寫入 `provenance` |
| pipeline | gdrive 來源 chunk | `ChunkQuarantined(no text)` | bronze-only 紅線 | `emit_corpus.py:44-50`、`:118-122` | `include_content=False`，改寫 `text_omitted_reason` |
| CI／人工 | 跑語料稽核 | `CorpusAuditPassed` / `Violation` | 5 項檢查任一違規 exit 1 | `audit_corpus.py:33-77` | provenance 完整、bronze 未漂移、facts 無 gdrive、基本欄位、id 唯一 |
| pipeline | 重跑同一 bronze | （不產生重複） | 冪等 | `_provenance.py:24-27`、`emit_corpus.py:145-147` | 確定性 `chunk_id`（sha256 前 16 碼）+ `seen_ids` 去重 |
| 人工 | 撰寫 skill references | `ReferenceAuthored` | bronze-only | — | **找不到**：無程式化校驗，`references/` 不在 audit 範圍 |

---

## 逐層走查

### 步驟 1 — Python 強制覆寫 provenance（bronze → silver）

`knowledge-pipeline/pipeline/bronze_to_silver/process_youtube.py:94-111`：

```python
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
```

`source_type` / `source` / `url` / `chunk_index` 四個鍵位於 `**item["metadata"]`（LLM 產出）之後，Python dict 字面的後者覆蓋前者——LLM 即使在 `metadata` 中回傳假的 `source` 或 `source_type`，最終 doc 仍為 Python 端的字面值。`video_id` 與 `url` 取自 bronze JSON（`process_youtube.py:86-87`），非 LLM。

同型結構在其餘 4 個處理器：

```
git grep -n "\*\*item\|source_type\":\|\"source\":" -- knowledge-pipeline/pipeline/bronze_to_silver
process_gdrive.py:92:        "source_type": "gdrive",
process_gdrive.py:93:        "source": file_id,
process_line.py:131:            **item["metadata"],
process_line.py:132:            "source_type": "line_chat",
process_line.py:133:            "source": session_id,
process_video.py:120:            **item["metadata"],
process_video.py:121:            "source_type": "video",
process_video.py:122:            "source": filepath.name,
process_website.py:121:            **item["metadata"],
process_website.py:122:            "source_type": "website",
process_website.py:123:            "source": filepath.name,
```

`process_gdrive.py:87-96` 未用 `**` 展開，改為逐鍵取值，LLM 只提供 `brand` / `model` / `content` 三欄：

```python
    doc = {
        "content": f"{result['content']}\n連結：{url}",
        "brand": result["brand"],
        "model": result["model"],
        "category": "manual",
        "source_type": "gdrive",
        "source": file_id,
        "chunk_index": 1,
        "url": url,
    }
```

### 步驟 2 — provenance 解析與 bronze 綁定

`knowledge-pipeline/pipeline/silver_to_knowledge/_provenance.py:1-13`：

```python
"""Provenance 解析 — 每個知識 chunk 可回溯到 bronze 來源檔。

治理依據（CLAUDE.md bronze-only 紅線）：知識內容嚴格源自
`knowledge-pipeline/storage/bronze/`；GDrive PDF 內容不可信、只引 URL。
本模組讓紅線機器可查核：chunk 帶 bronze 檔路徑 + sha256，
audit_corpus.py 據此驗證來源存在且未漂移。
"""
...
ROOT_DIR = Path(__file__).resolve().parents[2]
BRONZE_DIR = ROOT_DIR / "storage" / "bronze"
```

冪等 id（NFR-DQ-003），`_provenance.py:24-27`：

```python
def chunk_id(source_type: str, source: str, chunk_index: str, content: str) -> str:
    """確定性 chunk id：同一來源同一段內容永遠同 id（冪等重跑不重複）。"""
    key = f"{source_type}\x00{source}\x00{chunk_index}\x00{content}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
```

`resolve_bronze` 的 4 段解析順序見 `_provenance.py:36-71`，找不到時回 `(None, None)`，docstring 明載「找不到回 (None, None) —— 由 audit 擋下」。

### 步驟 3 — 雙軌路由與 gdrive 隔離

`knowledge-pipeline/pipeline/silver_to_knowledge/emit_corpus.py:44-50`：

```python
SOURCE_TRACK = {
    "youtube": "facts",
    "video": "facts",
    "website": "facts",
    "line_chat": "behavior",
    "gdrive": "quarantine",
}
```

`emit_corpus.py:102-123`：

```python
    bronze_path, bronze_sha = resolve_bronze(source_type, source)
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": chunk_id(source_type, source, idx, content),
        ...
        "provenance": {
            "bronze_path": bronze_path,
            "bronze_sha256": bronze_sha,
            "emitted_at": run_at,
        },
    }
    if include_content:
        record["text"] = content
    else:
        # 隔離軌（gdrive）：紅線要求內容不落地，只留參照供人工比對原始 PDF/URL
        record["text_omitted_reason"] = "bronze-only 紅線：GDrive 內容不可信，只引來源"
    return record
```

`include_content` 的決定點在 `emit_corpus.py:144`：

```python
        chunk = build_chunk(doc, include_content=(track != "quarantine"), run_at=run_at)
```

去重在 `emit_corpus.py:145-147`：

```python
        if chunk["id"] in seen_ids:
            continue  # 冪等：同內容 chunk 只收一次
        seen_ids.add(chunk["id"])
```

報表另記錄無 bronze 對應的 chunk，`emit_corpus.py:156-159`：

```python
        "missing_bronze": [
            c["id"] for v in tracks.values() for c in v
            if c["provenance"]["bronze_path"] is None
        ],
```

### 步驟 4 — 語料稽核 gate

`knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:1-13`：

```python
"""Step 2: 語料治理稽核 — 落地前品質 gate（最小評測 harness）。

檢查（任一違規 exit 1，可入 CI）：
  1. provenance 完整：facts/behavior 每 chunk 有 bronze_path + sha256
  2. 來源未漂移：bronze 檔存在且 sha256 相符
  3. 紅線：facts 語料內不得出現 gdrive 來源（quarantine 軌才准）
  4. 基本欄位：id/brand/model/category/text 非空
  5. id 唯一
"""
```

掃描根目錄 `audit_corpus.py:23`：

```python
CORPUS_DIR = ROOT_DIR / "storage" / "corpus"
```

紅線與漂移檢查 `audit_corpus.py:51-66`：

```python
            # 3. 紅線：facts 不得含 gdrive
            if track_name == "facts" and c.get("source_type") == "gdrive":
                violations.append(f"{where} — 紅線違規：gdrive 內容進了 facts 語料")
            # 1./2. provenance 完整且未漂移
            prov = c.get("provenance") or {}
            bp, bs = prov.get("bronze_path"), prov.get("bronze_sha256")
            if not bp or not bs:
                violations.append(f"{where} — provenance 不完整（bronze_path/sha256 缺）")
                continue
            bronze = ROOT_DIR / bp
            if not bronze.exists():
                violations.append(f"{where} — bronze 檔不存在：{bp}")
            elif sha256_file(bronze) != bs:
                violations.append(f"{where} — bronze 內容已漂移（sha256 不符）：{bp}")
```

### 步驟 5 — TC 字面指名的 `references` 樹

skill references 位於 `agent/lockcore/skills/locksmith-product-knowledge/references/`，目錄結構為 `_common/` + 6 個品牌目錄（`3E`、`Chatlock`、`Dormakaba`、`Kaadas`、`Milre`、`Philips`）。

檔案 frontmatter 只有三個欄位，如 `agent/lockcore/skills/locksmith-product-knowledge/references/3E/TX.md:1-5`：

```
---
brand: 3E
model: TX
description: "3E 小島快鎖 TX 產品資訊（含螢幕＋貓眼，3D 人臉/掌靜脈/指紋/卡片，操作與故障排除）"
---
```

無 `provenance` / `bronze_path` / `bronze_sha256` 欄位。

PDF 引用形式（`agent/lockcore/skills/locksmith-product-knowledge/references/Dormakaba/AS701.md:125-131`）：

```
## 相關手冊

- AS701 說明書: https://drive.google.com/file/d/1khDfWOjNoYEqKq6s-WEaaEFtUpAXCMWO/view
- AS701 補充說明書: https://drive.google.com/file/d/19y8fADkvVXLQYe-LaPRYB-JF3dZIguzW/view
- WiFi 設定說明書: https://drive.google.com/file/d/15_WKocOTqfhB1Xt4ppmk_QhTROdWkEfh/view
```

即 GDrive 來源以純 URL 條列，無抄錄內容。

部分檔案以自然語言記錄 bronze 對應關係，如 `agent/lockcore/skills/locksmith-product-knowledge/references/Chatlock/AI-88.md:56-57`：

```
  - Chatlock 設定教學（APP 與螢幕齒輪進入方式）：bronze/video/Chatlock 設定教學.txt
  - Chatlock 人臉辨識與防回頭機制：bronze/video/Chatlock 人臉辨識與防回頭機制.txt
```

以及缺料時的明示，`agent/lockcore/skills/locksmith-product-knowledge/references/3E/TX.md:157`：

```
- 目前無 3E 官方手冊收錄（bronze/gdrive 內無對應 PDF），建議聯繫客服取得最新資訊。
```

該樹不在 `audit_corpus.py` 的掃描範圍（`CORPUS_DIR` 指向 `knowledge-pipeline/storage/corpus`），`emit_corpus.py` 的輸出目錄同樣是 `storage/corpus`（`emit_corpus.py:42`），未寫入 `agent/lockcore/skills/`。`emit_corpus.py:2-5` 的檔頭自述此事：

```
2026-07-09 重構（ADR-029）：取代舊 silver_to_skill（其寫入目標
`agent/skills/data/` 已於 2026-06-04 LockCore 重寫刪除，且「每 skill 一個
SKILL.md」的產出格式已被 references/{Brand}/{Model}.md 正典取代）。
```

TC 步驟寫「檢查 references provenance」（出處：批次 A TC 原文第 67 行）／程式碼中帶機器可查核 provenance 的是語料軌 `storage/corpus/*.jsonl`；`agent/lockcore/skills/.../references/` 為人工撰寫的 markdown，無 provenance 欄位、無自動稽核。此處僅並陳，不裁定。

### 步驟 6 — 上游 refinery 軌的 provenance

另一條知識來源為 refinery（問題卡 → draft）。`knowledge-pipeline/refinery/refinery/refine.py:104-112`：

```python
    provenance = {
        "problem_card_id": card["id"],
        "conversation_id": card.get("conversation_id"),
        "message_count": len(transcript),
        "spine": _spine_snapshot(card),
        "llm_model": llm_model,
        "refined_at": refined_at,
    }
```

該 dict 的每個值皆取自 `card` 參數或函式引數，LLM 回傳的 `result` 只供應 `title` / `symptom` / `resolution` / `confidence` 等內容欄（`refine.py:116-129`）。檔頭 `refine.py:8` 自述：「不得編造:LLM 只能整理卡欄位與逐字稿既有資訊;provenance 記全程溯源。」

---

## 既有測試證據

實跑語料稽核：

```
cd knowledge-pipeline && python -m pipeline.silver_to_knowledge.audit_corpus
✅ 稽核通過：facts=862 behavior=0，provenance 完整、bronze 未漂移、紅線無違規
```

語料統計（探針一次性讀檔，腳本不在 repo 內）：

```
facts source_type: Counter({'youtube': 706, 'video': 94, 'website': 62})
facts has text: 862
quarantine n= 19 with text: 0
quarantine keys: ['brand', 'category', 'chunk_index', 'id', 'model', 'provenance',
                  'schema_version', 'source', 'source_type', 'text_omitted_reason']
```

即：facts 軌 862 筆全數有內容且來源僅 youtube／video／website 三類（無 gdrive）；quarantine 軌 19 筆全數無 `text` 鍵、改帶 `text_omitted_reason`。

`knowledge-pipeline/pipeline/` 下無 pytest 測試檔（`find knowledge-pipeline -name "test*"` 的命中全部落在 `knowledge-pipeline/refinery/tests/`，共 6 檔，內容為 entitlement／intake／observability／oidc／refine／review）。

---

## 事實結論

1. provenance 的 `source_type` / `source` 在 5 個 bronze→silver 處理器中皆由 Python dict 字面覆寫，位置在 `**item["metadata"]` 之後；`process_gdrive.py` 更不展開 LLM metadata。
2. corpus 層每筆 chunk 帶 `provenance.bronze_path` + `bronze_sha256`，由 `resolve_bronze()` 從 `storage/bronze/` 實檔計算。
3. `audit_corpus.py` 為 5 項檢查的 gate，違規 exit 1；實跑通過，862 筆 facts 無違規。
4. gdrive 軌的 chunk 不落 `text`，改寫 `text_omitted_reason`；facts 軌零 gdrive 來源。
5. 冪等由確定性 `chunk_id`（sha256 前 16 碼）+ `seen_ids` 兩層保證。
6. TC 字面指名的 `agent/lockcore/skills/locksmith-product-knowledge/references/` 為人工 markdown 樹，frontmatter 僅 brand/model/description，無 provenance 欄位，且不在 `audit_corpus` 掃描範圍。
7. 該 references 樹的 GDrive 來源以純 URL 條列（`Dormakaba/AS701.md:127-131` 等），未見抄錄 PDF 內容。
8. `knowledge-pipeline/pipeline/` 無單元測試；refinery 子專案有 6 個測試檔。
