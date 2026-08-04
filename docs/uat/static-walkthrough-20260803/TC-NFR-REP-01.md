# TC-NFR-REP-01 — 知識產線可重現與 raw 保存

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（補一次 `--dry-run` 與一次治理稽核的實跑證據，皆為唯讀） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `knowledge-pipeline/pipeline/silver_to_knowledge/emit_corpus.py:1-195`、`_provenance.py:1-71`、`audit_corpus.py:1-82`、`knowledge-pipeline/pipeline/raw_to_bronze/process_video.py:55-116`、`knowledge-pipeline/pipeline/bronze_to_silver/process_video.py:93-200`、`knowledge-pipeline/llms/provider.py:64-107`、`knowledge-pipeline/config.toml:1-60`、`knowledge-pipeline/.gitignore:1-17`、`knowledge-pipeline/README.md:1-80`、`smartlock-docs/enterprise/05_NFR.md:183-184` |
| 優先級 / 路徑類型 | P1 / failure＋recovery |

「相同輸入產同結構結果」在最末段（silver → corpus）成立且可實證：chunk id 是內容雜湊（`_provenance.py:24-27`），重複 id 直接跳過（`emit_corpus.py:145-147`），本次兩次 `--dry-run` 的統計與 2026-07-17 落盤的 `storage/corpus/_report.json` 三者數字完全相同（862 / 0 / 19，見步驟 2），唯一逐次變動的欄位是時間戳 `run_at` / `emitted_at`（`emit_corpus.py:132`、`:115`）。判定為「部分實作」的兩點：其一，**「保存不足時明確阻擋」的層級不齊**——`bronze_to_silver` 在 bronze 為空時 `sys.exit`（`process_video.py:177-178`）、`audit_corpus` 在 bronze 缺檔或 sha256 漂移時 exit 1（`audit_corpus.py:62-66`、`:68-74`），但 `raw_to_bronze` 在 raw 被移除時只是掃到 0 個候選並印出「共 0 支影片待處理」（`process_video.py:79-84`、`:116`），不阻擋、不非零退出；其二，**稽核輸出不落檔**——`audit_corpus` 只 `print` 到 stdout 與回傳 exit code（`:69-77`），落盤的 `_report.json` 由 `emit_corpus` 產生（`:188-190`），內容為統計與 `missing_bronze` / `unknown_sources`，不含稽核判定。另 NFR-Rep-002 的「原始資產保存策略」在需求表中即記為 `[待確認]`（`05_NFR.md:184`），而 raw 層的大型媒體皆被 gitignore（`knowledge-pipeline/.gitignore:4-7`），版控中的 `storage/raw/` 只有 7 個檔（含 5 個 `.keep`）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | 固定 raw、config 與保存位置 fixture |
| 步驟 | 重跑 pipeline、變更 config、移除 raw 後嘗試 rebuild |
| 預期結果（判定基準） | 相同輸入產同結構結果；保存不足時明確阻擋並保留稽核 |
| 路徑類型 | failure＋recovery |
| 驗證面向 | 功能 |
| 優先級 | P1 |
| 驗證哪些需求 | NFR-Rep-001、NFR-Rep-002 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:442`。兩條需求原文（`smartlock-docs/enterprise/05_NFR.md:183-184`）：

```
| NFR-Rep-001 | Pipeline 可重現 | config-driven，同 config 產同結構輸出 | 重跑驗證 | 營運目標 |
| NFR-Rep-002 | raw → bronze 可重建 | 原始資產保存策略 `[待確認]` | 保存位置文件化 | 營運目標 |
```

同檔 `20_Test_Cases.md:211-212` 記載兩條需求的追溯狀態皆為「⚠ 完全沒有案例」。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| chunk 產出為確定性 | `_provenance.py:24-27`（sha256 of `source_type\0source\0index\0content`） | 一致 |
| 重跑冪等（不重複收） | `emit_corpus.py:145-147` | 一致 |
| 重跑產同結構 | 兩次 `--dry-run` 與已落盤 `_report.json` 三者統計相同（步驟 2） | 一致 |
| 重跑產逐位元組相同輸出 | `emit_corpus.py:132`（`run_at`）、`:115`（`emitted_at`）逐次變動 | 不一致 |
| 上游 bronze → silver 為確定性 | `llms/provider.py:72`、`config.toml:2-4` 走 LLM（`temperature = 0.3`） | 不一致 |
| config-driven | `bronze_to_silver/process_*.py` 各自 `load_pipeline_config()` 讀 `config.toml`；`emit_corpus` / `audit_corpus` 不讀 config | 部分實作 |
| 變更 config 後重跑會反映 | `process_video.py:190-193` 已存在即 SKIP，需 `--force` | 部分實作 |
| config 版本被記錄進產出 | `_report.json` 欄位為 `run_at` / `schema_version` / `totals` / `by_brand` / `by_category` / `missing_bronze` / `unknown_sources`，無 config 指紋 | 不一致 |
| 移除 raw 後 rebuild 明確阻擋 | `raw_to_bronze/process_video.py:79-84`、`:116`（掃到 0 個只 log，`return` 前無非零退出） | 不一致 |
| 移除 bronze 後 rebuild 明確阻擋 | `bronze_to_silver/process_video.py:176-178`（`sys.exit`） | 一致 |
| 產出前有品質 gate | `audit_corpus.py:32-78`（5 項檢查，違規 exit 1） | 一致 |
| provenance 可回溯 | `emit_corpus.py:102`、`:112-116`；`_provenance.py:36-71` | 一致 |
| 保留稽核（落檔） | `audit_corpus.py:69-77` 僅 stdout；`_report.json` 不含稽核判定 | 部分實作 |
| raw 保存位置文件化 | `README.md:41-52` 目錄結構；`.gitignore:4-7` 排除大型媒體；`05_NFR.md:184` 記為 `[待確認]` | 部分實作 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 維運 | 跑 `source_to_raw` | `RawFetched` | 由 config 的來源清單決定 | `config.toml:20-28`（`youtube_fetch.playlists`）、`pipeline/source_to_raw/process_youtube.py` | 依播放清單下載 |
| 維運 | 跑 `raw_to_bronze` | `BronzeBuilt` | 已存在即跳過 | `raw_to_bronze/process_video.py:98-101` | `output_path.exists() and not --force` → skip |
| 維運 | raw 已被移除後跑 `raw_to_bronze` | `RebuildBlocked` | 保存不足時阻擋 | `raw_to_bronze/process_video.py:79-84` | **找不到阻擋**：`rglob` 掃到 0 個 → `found=0` → 迴圈不執行 → log「完成：找到 0 / 處理 0 / 跳過 0 / 失敗 0」 |
| 維運 | 跑 `bronze_to_silver` | `SilverBuilt` | bronze 不可為空 | `bronze_to_silver/process_video.py:176-178` | `sys.exit("No .txt files found in ...")` |
| 維運 | 跑 `emit_corpus` | `CorpusEmitted` | 確定性路由 + 冪等 | `emit_corpus.py:44-50`、`:138-148` | 依 `SOURCE_TRACK` 分軌；重複 id 跳過 |
| 維運 | 跑 `audit_corpus` | `CorpusAudited` / `AuditFailed` | 不過不落地 | `audit_corpus.py:32-78` | 違規列印後 return 1 |
| 系統 | bronze 檔內容漂移 | `ProvenanceDrift` | sha256 比對 | `audit_corpus.py:65-66` | 「bronze 內容已漂移（sha256 不符）」 |
| 系統 | gdrive 內容誤入 facts | `RedlineViolation` | bronze-only 紅線 | `audit_corpus.py:54-55` | 記為違規 |

---

## 逐層走查

### 步驟 1 — 確定性的來源：chunk id 與冪等

`knowledge-pipeline/pipeline/silver_to_knowledge/_provenance.py:24-27`

```python
def chunk_id(source_type: str, source: str, chunk_index: str, content: str) -> str:
    """確定性 chunk id：同一來源同一段內容永遠同 id（冪等重跑不重複）。"""
    key = f"{source_type}\x00{source}\x00{chunk_index}\x00{content}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
```

`emit_corpus.py:138-148`

```python
    for fp, doc in _iter_silver_chunks():
        source_type = doc.get("source_type") or fp.parent.name
        track = SOURCE_TRACK.get(source_type)
        if track is None:
            unknown_sources.add(source_type)
            continue
        chunk = build_chunk(doc, include_content=(track != "quarantine"), run_at=run_at)
        if chunk["id"] in seen_ids:
            continue  # 冪等：同內容 chunk 只收一次
        seen_ids.add(chunk["id"])
        tracks[track].append(chunk)
```

走訪順序為排序後的目錄與檔名（`:57-60` 的兩層 `sorted`），輸出逐行寫入（`:182-187`），因此 jsonl 的列順序在相同 silver 輸入下固定。

逐次變動的只有時間戳（`:132`、`:112-116`）：

```python
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
```

```python
        "provenance": {
            "bronze_path": bronze_path,
            "bronze_sha256": bronze_sha,
            "emitted_at": run_at,
        },
```

### 步驟 2 — 重跑驗證（實跑）

兩次唯讀 `--dry-run`：

```
cd knowledge-pipeline && python -m pipeline.silver_to_knowledge.emit_corpus --dry-run
INFO: facts=862 behavior=0 quarantine=19 missing_bronze=0
{
  "run_at": "2026-08-04T01:22:10+00:00",
  "schema_version": 1,
  "totals": { "facts": 862, "behavior": 0, "quarantine": 19 },
  "by_brand": { "Chainlock": 5, "Dormakaba": 364, "general": 131, "Chatlock": 193,
                "鎖市": 48, "3E": 103, "小島": 5, "Kaadas": 13 },
  "by_category": { "setup": 570, "knowledge": 171, "troubleshoot": 80, "specification": 41 },
  "missing_bronze": [],
  "unknown_sources": []
}

（第二次，同指令）
INFO: facts=862 behavior=0 quarantine=19 missing_bronze=0
  "run_at": "2026-08-04T01:22:11+00:00"
  （其餘欄位逐字相同）
```

與版控中 2026-07-17 落盤的 `knowledge-pipeline/storage/corpus/_report.json` 相比：

```json
{
  "run_at": "2026-07-17T16:08:40+00:00",
  "schema_version": 1,
  "totals": { "facts": 862, "behavior": 0, "quarantine": 19 },
  "by_brand": { "Chainlock": 5, "Dormakaba": 364, "general": 131, "Chatlock": 193,
                "鎖市": 48, "3E": 103, "小島": 5, "Kaadas": 13 },
  ...
```

三次結果除 `run_at` 外完全相同。輸入端在版控中固定：`git ls-files knowledge-pipeline/storage/silver` 為 116 個檔、`storage/bronze` 為 115 個檔。

治理稽核同樣實跑（唯讀）：

```
cd knowledge-pipeline && python -m pipeline.silver_to_knowledge.audit_corpus
✅ 稽核通過：facts=862 behavior=0，provenance 完整、bronze 未漂移、紅線無違規
```

### 步驟 3 — config 的作用範圍

`config.toml` 由各 `bronze_to_silver` / `raw_to_bronze` 腳本各自載入，例如 `bronze_to_silver/process_video.py:93-99`：

```python
def load_pipeline_config() -> dict:
    """Read [pipelines.video] from config.toml."""
    config_path = ROOT_DIR / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config["pipelines"]["video"]
```

`emit_corpus.py` 與 `audit_corpus.py` 全檔對 `config.toml` / `tomllib` 零命中——末段路由是硬編的 `SOURCE_TRACK`（`emit_corpus.py:44-50`）與 `SCHEMA_VERSION = 1`（`:52`）。`config.toml:57-60` 亦記載此事：

```toml
[pipelines.silver_to_knowledge]
# 雙軌產出為確定性路由（不呼叫 LLM）；產出位置固定 storage/corpus/。
# 舊 silver_to_skill 段已刪（寫入目標 agent/skills/data 於 2026-06-04 消失，見 ADR-029）。
corpus_dir = "storage/corpus"
```

中段（bronze → silver）走 LLM，`config.toml:1-4`：

```toml
[pipelines.video]
llm_provider = "vertexai"
llm_model = "gemini-2.5-flash"
temperature = 0.3
```

`llms/provider.py:72`、`:74-88`：

```python
    temperature = kwargs.get("temperature", 0.3)

    def generate_json(prompt: str, system_prompt: str, schema: dict) -> dict:
        if provider == "vertexai":
            response = litellm.completion(
                model=litellm_model,
                messages=[...],
                temperature=temperature,
                response_format={
                    "type": "json_object",
                    "response_schema": schema,
                },
            )
```

即該段輸出的**結構**由 `RESPONSE_SCHEMA`（`process_video.py:60-87` 一帶）約束，**內容**由 LLM 在 `temperature = 0.3` 下生成。

變更 config 後重跑不會自動重算既有輸出（`bronze_to_silver/process_video.py:190-193`）：

```python
        # Idempotency check
        if out_path.exists() and not args.force and not args.retry_failed:
            log.info("SKIP (already exists): %s", filepath.name)
            skipped += 1
            continue
```

`raw_to_bronze/process_video.py:98-101` 為同型（`--force` 才覆寫）。

產出中無 config 指紋：`_report.json` 的欄位由 `emit_corpus.py:150-161` 決定，為 `run_at` / `schema_version` / `totals` / `by_brand` / `by_category` / `missing_bronze` / `unknown_sources`。

TC 判定基準寫「相同輸入產同結構結果」，NFR-Rep-001 寫「**config-driven**，同 config 產同結構輸出」（出處：`smartlock-docs/enterprise/05_NFR.md:183`）／程式碼在末段不讀 config（`emit_corpus.py` 對 `tomllib` 零命中），在中段讀 config 但輸出經 LLM 生成、且既有輸出預設 SKIP 不重算。此處僅並陳，不裁定。

### 步驟 4 — 移除 raw 後嘗試 rebuild

`knowledge-pipeline/pipeline/raw_to_bronze/process_video.py:76-101`

```python
    if args.file:
        candidates = [RAW_DIR / args.file]
    else:
        mov_files = list(RAW_DIR.rglob("*.[mM][oO][vV]"))
        mp4_files = list(RAW_DIR.rglob("*.[mM][pP]4"))
        candidates = sorted(set(mov_files + mp4_files))

    found = len(candidates)
    logger.info(f"共 {found} 支影片待處理")

    processed = 0
    skipped = 0
    failed = 0

    for filepath in candidates:
        if not filepath.exists():
            logger.error(f"檔案不存在: {filepath}")
            failed += 1
            continue
```

`:91-94` 的「檔案不存在」分支只在 `--file` 單檔模式下可能觸發（批次模式的候選來自 `rglob`，必然存在）。批次模式下 raw 目錄被清空時，`found = 0`、迴圈不執行，函式以 `:116` 的 log 收尾：

```python
    logger.info(f"完成：找到 {found} / 處理 {processed} / 跳過 {skipped} / 失敗 {failed}")
```

該函式無 `sys.exit` 非零回傳。

下一層則有阻擋（`bronze_to_silver/process_video.py:167-178`）：

```python
    if args.file:
        files = [BRONZE_DIR / args.file]
        if not files[0].exists():
            sys.exit(f"File not found: {files[0]}")
    elif args.retry_failed:
        files = [BRONZE_DIR / f for f in prev_failures if (BRONZE_DIR / f).exists()]
        if not files:
            sys.exit("No previously failed files to retry")
    else:
        files = sorted(BRONZE_DIR.glob("*.txt"))
        if not files:
            sys.exit(f"No .txt files found in {BRONZE_DIR}")
```

再下一層的 gate（`audit_corpus.py:56-74`）檢查的對象是 bronze 而非 raw：

```python
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

    if violations:
        print(f"❌ 稽核失敗（{len(violations)} 項違規）：")
        for v in violations[:30]:
            print(f"  - {v}")
        if len(violations) > 30:
            print(f"  ...（其餘 {len(violations) - 30} 項省略）")
        return 1
```

TC 判定基準寫「保存不足時**明確阻擋**並保留稽核」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:442`）／程式碼在 raw 層無阻擋（批次模式掃到 0 個即正常結束），在 bronze 層與 corpus 層各有一道阻擋。此處僅並陳，不裁定。

### 步驟 5 — raw 的保存位置與版控狀態

`knowledge-pipeline/.gitignore:1-17`

```
# ── data/ 專用規則（通用規則已在主目錄 .gitignore）──

# ── Large binary / media files ────────────────────────────────────────
storage/raw/video/*.MOV
storage/raw/video/*.mp4
storage/raw/youtube/*.mp4
storage/raw/line_chat/*.csv

# ── Large binary / media files ────────────────────────────────────────
storage/bronze/line_chat/*.csv

# ── Silver layer generated JSON ──────────────────────────────────────
storage/silver/line_chat/*.json
!storage/silver/line_chat/_irrelevant.json

# ── Keep .keep files inside ignored directories ──────────────────────
!**/.keep
```

版控中的 `storage/raw/` 內容：

```
git ls-files knowledge-pipeline/storage/raw
knowledge-pipeline/storage/raw/gdrive/.keep
knowledge-pipeline/storage/raw/gdrive/links.txt
knowledge-pipeline/storage/raw/line_chat/.keep
knowledge-pipeline/storage/raw/video/.keep
knowledge-pipeline/storage/raw/website/.keep
knowledge-pipeline/storage/raw/website/website.txt
knowledge-pipeline/storage/raw/youtube/.keep
```

即 7 個檔，其中 5 個是佔位 `.keep`；`storage/bronze` 為 115 個檔、`storage/silver` 為 116 個檔、`storage/corpus` 為 4 個檔（`facts.jsonl` / `behavior_candidates.jsonl` / `quarantine_gdrive.jsonl` / `_report.json`）。

來源清單以 URL 形式保存於 config（`config.toml:20-28` 的 `youtube_fetch.playlists` 六條播放清單）與 `storage/raw/gdrive/links.txt`、`storage/raw/website/website.txt`。

`README.md:41-52` 記載目錄結構與各層職責；`05_NFR.md:184` 的 NFR-Rep-002 「原始資產保存策略」欄位值為 `[待確認]`。

### 步驟 6 — 血緣漂移的既有處理

`_provenance.py:30-71` 有四段式的 bronze 解析（處理 silver 產生後 bronze 改名）：

```python
# silver 產生後 bronze 曾改名（錯字修正），後綴比對救不回的登記於此
_SOURCE_ALIASES = {
    ("video", "Chainlock 設定教學.txt"): "Chatlock 設定教學.txt",  # Chainlock 為錯字
}


def resolve_bronze(source_type: str, source: str) -> tuple[str | None, str | None]:
    """由 silver chunk 的 (source_type, source) 找 bronze 檔，回傳 (相對路徑, sha256)。

    解析順序（處理 silver 產生後 bronze 改名的血緣漂移）：
      1. 精確路徑
      2. 別名表（錯字修正類改名）
      3. stem 完全相符（副檔名/子目錄差異）
      4. 唯一後綴相符（bronze 後來加品牌前綴，如「鎖栓測試進階」→「Dormakaba 鎖栓測試進階」）
    找不到回 (None, None) —— 由 audit 擋下。
    """
```

第 3、4 步的模糊比對在 bronze 檔集合變動時可能落到不同檔（`:63-70` 要求 `len(matches) == 1` 才採用，否則回 `(None, None)`）。

---

## 既有測試證據

- `knowledge-pipeline/` 下無 pipeline 自身的測試：`find knowledge-pipeline -name "test_*.py"` 命中的六個檔全在 `knowledge-pipeline/refinery/tests/`（`test_entitlement.py`、`test_intake_component.py`、`test_observability.py`、`test_oidc_auth.py`、`test_refine_unit.py`、`test_review_service.py`），對象是 refinery 服務，不是 `pipeline/` 四層。
- 本次的執行證據為兩次 `emit_corpus --dry-run` 與一次 `audit_corpus`，皆為唯讀指令（`--dry-run` 於 `emit_corpus.py:172-174` 只 `print` 後 return，不寫檔；`audit_corpus` 全檔無寫入）。執行後 `git status` 在 `knowledge-pipeline/` 下無任何變更。

---

## 事實結論

1. chunk id 為 `(source_type, source, chunk_index, content)` 的 sha256 前 16 碼（`_provenance.py:24-27`），同輸入必得同 id。
2. 重複 id 於 `emit_corpus.py:145-147` 跳過；走訪順序經兩層 `sorted`（`:57-60`）。
3. 兩次 `--dry-run` 與版控中 2026-07-17 的 `_report.json` 三者統計完全相同（facts 862 / behavior 0 / quarantine 19，`by_brand`、`by_category` 逐項相同），差異僅 `run_at`。
4. 每筆 chunk 帶 `emitted_at`（`emit_corpus.py:115`），故輸出檔逐次不會逐位元組相同。
5. `emit_corpus.py` 與 `audit_corpus.py` 對 `config.toml` / `tomllib` 零命中；末段路由為硬編 `SOURCE_TRACK`。
6. 中段 `bronze_to_silver` 讀 config 並呼叫 LLM，`temperature = 0.3`（`config.toml:4`、`llms/provider.py:72`）。
7. `raw_to_bronze` 與 `bronze_to_silver` 預設「輸出已存在即 SKIP」，變更 config 後需 `--force` 才重算（`raw_to_bronze/process_video.py:98-101`、`bronze_to_silver/process_video.py:190-193`）。
8. `_report.json` 不含 config 指紋或模型版本欄位（欄位由 `emit_corpus.py:150-161` 決定）。
9. raw 被清空後跑 `raw_to_bronze` 批次模式：`rglob` 得 0 個候選，只 log「共 0 支影片待處理」與收尾統計，無非零退出（`process_video.py:79-84`、`:116`）。
10. bronze 為空時 `bronze_to_silver` 以 `sys.exit` 阻擋（`process_video.py:177-178`）。
11. `audit_corpus` 有 5 項檢查（provenance 完整、bronze 存在且 sha256 未漂移、facts 不得含 gdrive、基本欄位非空、id 唯一），違規 exit 1（`audit_corpus.py:1-9`、`:32-78`）。
12. 稽核結果只寫 stdout，不落檔（`audit_corpus.py:69-77`）。
13. 版控中的 `storage/raw/` 只有 7 個檔（5 個 `.keep` + `gdrive/links.txt` + `website/website.txt`）；大型媒體由 `.gitignore:4-7` 排除。
14. NFR-Rep-002 的保存策略在需求表中即為 `[待確認]`（`05_NFR.md:184`）。
15. `knowledge-pipeline/pipeline/` 無既有測試；六支測試皆屬 `refinery/`。
16. `20_Test_Cases.md:211-212` 記載 NFR-Rep-001/002 追溯狀態為「⚠ 完全沒有案例」，同檔 `:442` 又列有 TC-NFR-REP-01 一列。
17. 實際移除 raw / 變更 config 後的完整重跑（含 LLM 呼叫與寫檔）屬破壞性操作，本次未執行。
