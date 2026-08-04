# TC-REF-INTAKE-01 — 素材汲取的 gate、重送冪等、跨租戶隔離與失敗可稽核

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 refinery 全測試 36 項全過（見步驟 7） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `knowledge-pipeline/refinery/refinery/{db,intake,run_intake,store,entitlement}.py`、`knowledge-pipeline/pipeline/raw_to_bronze/*`、`knowledge-pipeline/pipeline/silver_to_knowledge/{_provenance,audit_corpus,emit_corpus}.py`、`api/services/problem_card_service.py:505-552`、`SQL/migrations/093-pc-dual-gate.sql`、`SQL/migrations/117-problem-card-dismissed.sql` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | TC 前置提到兩種素材（問題卡、外部素材），程式碼中對應**兩套獨立管線**，其 gate 與稽核強度不同：**(a) 診斷對話汲取**（refinery）——gate 為 `status='resolved' AND knowledge_ready=TRUE` 且無活 draft（`intake.py:25-38`），tenant default-deny（`db.py:21-26`），重送冪等由 `UNIQUE(tenant_id, draft_key) ON CONFLICT DO NOTHING` 保證（`store.py:28-55`），單卡失敗不中斷批次（`run_intake.py:59-62`）——但**失敗只印 stderr，不落任何稽核表**；**(b) 外部素材 → bronze**（knowledge-pipeline）——bronze-only 紅線與 provenance 由 `audit_corpus.py:1-11/50-68` 在**語料落地前**檢查（gdrive 不得進 facts、bronze 檔須存在且 sha256 未漂移），但該 gate 檢查的是 `storage/corpus/`（silver→knowledge 之後），**不是** raw→bronze 的入口；`raw_to_bronze/*.py` 五支處理器無 tenant 欄位，storage 為單一檔案樹，跨租戶隔離在此層不存在。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：knowledge_ready/未完成問題卡、外部素材、兩租戶 fixture
- 步驟：從准許與未准許來源汲取；重送同素材；模擬來源讀取失敗
- 預期結果（判定基準）：僅符合 gate 的資料進 bronze；失敗／重送不產生半成品或跨租戶資料；來源與失敗原因可稽核
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-DAT-01、FR-REF-01｜屬於旅程腳本：—

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| knowledge_ready 卡才被汲取 | `knowledge-pipeline/refinery/refinery/intake.py:25-38` | 有 |
| knowledge_ready 的計算 gate | `api/services/problem_card_service.py:509-511`、`:525-552` | 有 |
| 未完成卡被排除 | `intake.py:29-30`（`knowledge_ready = TRUE`） | 有 |
| 已作廢卡被排除 | `api/services/problem_card_service.py:50-54`（`dismissed` 不映射 `resolved`） | 有 |
| 未准許來源不得進 facts 語料 | `knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:55-57` | 有（gdrive → facts 違規） |
| 僅符合 gate 的資料進 **bronze** | — | **找不到**：`raw_to_bronze/*.py` 無 gate；紅線檢查發生在 corpus 層 |
| 重送同素材冪等 | `knowledge-pipeline/refinery/refinery/store.py:42`、`refine.py:67-71` | 有 |
| 失敗不產生半成品 | `run_intake.py:52-62`（單卡例外 → skip，不寫 draft） | 有 |
| 不產生跨租戶資料 | `db.py:21-26`、`intake.py:28`、`store.py:36-42`、`review.py:43-52` | 有（refinery 側） |
| 來源可稽核 | `refine.py:105-112`（provenance）、`_provenance.py:36-62`（bronze_path+sha256） | 有 |
| 失敗原因可稽核 | `run_intake.py:60`（`print(..., file=sys.stderr)`） | 部分：僅 stderr，無稽核表 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服/技師 | 補齊 RMA spine 結案 | `KnowledgeGatePassed` | Gate② 滿分 | `api/services/problem_card_service.py:545-552` | `knowledge_ready = (knowledge_ready OR %s)`，`resolution >= 1.0` 才置 TRUE |
| 排程 | 執行汲取批次 | `CardsIntaken` | 只吃 gate 過的卡 | `knowledge-pipeline/refinery/refinery/intake.py:25-38` | `WHERE tenant_id=%s AND status='resolved' AND knowledge_ready=TRUE AND NOT EXISTS(活 draft)` |
| 排程 | 未開通 refinery 模組 | `IntakeBlocked` | License gate | `run_intake.py:29-35`、`entitlement.py:52-57` | 未開通 → 印訊息 + `return 2` |
| 排程 | 未設 tenant | `IntakeDenied` | default deny | `db.py:21-26` | `RuntimeError`，絕不退回全庫查詢 |
| 排程 | 重送同一卡同素材 | （不新增 draft） | 冪等 | `store.py:33-53` | `ON CONFLICT (tenant_id, draft_key) DO NOTHING`，`written` 只累加實際 rowcount |
| 排程 | 單卡 LLM 失敗 | `CardSkipped` | 不中斷批次 | `run_intake.py:59-62` | `except Exception` → stderr + `skipped += 1`，**不寫 draft** |
| 排程 | 記錄失敗原因 | `IntakeFailureAudited` | 可稽核 | — | **找不到**：無失敗稽核表／欄位 |
| 管線 | 外部素材 → bronze | `BronzeMaterialized` | 來源白名單 | `knowledge-pipeline/pipeline/raw_to_bronze/*.py` | 五支處理器（youtube/website/video/line/gdrive）各自輸出到 `storage/bronze/<type>/`，無准許來源判定 |
| 管線 | corpus 落地前稽核 | `CorpusAudited` | bronze-only 紅線 | `audit_corpus.py:32-79` | 違規累加 → `return 1`（CI 可 block） |

---

## 逐層走查

### 步驟 1 — 汲取 gate 的 SQL

`knowledge-pipeline/refinery/refinery/intake.py:1-11`

```python
"""汲取層 — 撿 knowledge_ready 的問題卡與其對話逐字稿（CR-0139 D1：直連品牌 DB 唯讀）。

撿卡條件（冪等）：
  status='resolved' AND knowledge_ready=TRUE
  AND 無「活的」draft（pending_review/approved/rejected/superseded 任一存在即跳過；
      re_refine 表示審核者退回重煉 → 重新撿起，舊 draft 由 store 標 superseded）
```

`knowledge-pipeline/refinery/refinery/intake.py:25-38`

```python
_PENDING_CARDS_SQL = f"""
SELECT {', '.join('pc.' + c for c in _CARD_COLS)}
FROM problem_cards pc
WHERE pc.tenant_id = %s
  AND pc.status = 'resolved'
  AND pc.knowledge_ready = TRUE
  AND NOT EXISTS (
      SELECT 1 FROM knowledge_drafts kd
      WHERE kd.source_problem_card_id = pc.id
        AND kd.status <> 're_refine'
  )
ORDER BY pc.updated_at
LIMIT %s
"""
```

`knowledge_ready` 的來源在 API 側，`api/services/problem_card_service.py:525-552`：

```python
async def _recompute_gates(pc_id: str) -> None:
    """重算雙完整度並持久化；Gate② 滿分 → knowledge_ready=TRUE（精煉汲取條件）。

    knowledge_ready 單向落 TRUE 後不自動退回（避免精煉已汲取後旗標翻覆）；
    spine 欄位被清空屬人工異常，交由審核流程處理。
    """
    ...
    await db_module._conn.execute(
        "UPDATE problem_cards SET intake_completeness = %s, resolution_completeness = %s, "
        "  knowledge_ready = (knowledge_ready OR %s), updated_at = updated_at "
        "WHERE id = %s::uuid",
        (intake, resolution, resolution >= 1.0, pc_id),
    )
```

Gate② 必填集 `api/services/problem_card_service.py:509-511`：

```python
# Gate②（知識/精煉 RMA spine）必填；L3 追加 firmware_version/serial
_GATE2_FIELDS = ("root_cause", "root_cause_category", "corrective_action",
                 "verification", "disposition", "resolution_channel", "resolved_by")
```

### 步驟 2 — 「未准許來源」在兩套管線中的兩種意義

**(a) refinery（診斷對話）**：准許與否由 `knowledge_ready` 與作廢狀態決定。`api/services/problem_card_service.py:50-54` 記錄了一項刻意設計：

```python
    # CR-0185：作廢終態。**必須有此對映** —— _coerce_status 對未知值 fallback 回 "draft"，
    # 漏加會讓作廢卡在全站顯示成「待確認」並回到待確認佇列（本修復自我廢除）。
    # 且**絕不可**映射到 "resolved" —— refinery 的 _PENDING_CARDS_SQL 只吃
    # status='resolved' AND knowledge_ready=TRUE，會把垃圾卡汲取成知識。
    "dismissed": "dismissed",
```

同一約束亦寫入 `SQL/migrations/117-problem-card-dismissed.sql:8`。

**(b) knowledge-pipeline（外部素材）**：准許與否由 bronze-only 紅線決定。`knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:1-11`：

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

紅線判定 `audit_corpus.py:55-57`：

```python
            # 3. 紅線：facts 不得含 gdrive
            if track_name == "facts" and c.get("source_type") == "gdrive":
                violations.append(f"{where} — 紅線違規：gdrive 內容進了 facts 語料")
```

TC 判定基準寫「僅符合 gate 的資料**進 bronze**」／程式碼的紅線 gate 位於 `storage/corpus/`（silver→knowledge 之後）而非 bronze 入口；`raw_to_bronze/process_gdrive.py` 等五支處理器對來源不做准許判定，逕行輸出到 `storage/bronze/<source_type>/`。此處僅並陳，不裁定。

### 步驟 3 — 跨租戶隔離

refinery 側為 default-deny，`knowledge-pipeline/refinery/refinery/db.py:21-26`：

```python
def tenant_id() -> str:
    """default deny：tenant 未設定即拒絕服務（CR-0139 D1，比照 ADR-010 治理）。"""
    tid = os.getenv("REFINERY_TENANT_ID")
    if not tid:
        raise RuntimeError("需要 REFINERY_TENANT_ID（汲取必帶 tenant，default deny）")
    return str(uuid.UUID(tid))  # 驗格式
```

所有讀寫皆帶 tenant：撿卡 `intake.py:28`（`WHERE pc.tenant_id = %s`）、寫 draft `store.py:36`（`INSERT ... (tenant_id, draft_key, ...)`）、supersede `store.py:20`（`WHERE tenant_id = %s AND source_problem_card_id = %s::uuid`）、審核讀取 `review.py:43`／`:59-60`（皆 `WHERE tenant_id = %s`）。

外部素材管線的 storage 為單一檔案樹（`knowledge-pipeline/storage/{raw,bronze,silver,corpus}`），`pipeline/raw_to_bronze/process_youtube.py:21-22` 的目錄常數：

```python
RAW_DIR = ROOT_DIR / "storage" / "raw" / "youtube"
BRONZE_DIR = ROOT_DIR / "storage" / "bronze" / "youtube"
```

無 tenant 維度。

### 步驟 4 — 重送同素材

draft_key 為確定性雜湊，`knowledge-pipeline/refinery/refinery/refine.py:64-71`：

```python
_DRAFT_KEY_NS = "kd\x00"


def draft_key(card_id: str, draft_type: str, payload: dict) -> str:
    """確定性 draft id(冪等;比照 knowledge-pipeline chunk_id 慣例)。"""
    canon = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    raw = f"{_DRAFT_KEY_NS}{card_id}\x00{draft_type}\x00{canon}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
```

寫入端 `knowledge-pipeline/refinery/refinery/store.py:1-6`、`:33-55`：

```python
"""Draft Queue 存取層 — knowledge_drafts 表(migration 094/CR-0139 D2)。

冪等:UNIQUE(tenant_id, draft_key) ON CONFLICT DO NOTHING → 重跑不重複。
re_refine 重煉:寫入新 draft 前把該卡的 re_refine 舊 draft 標 superseded
(append-only 精神——不刪列,留完整審核軌跡)。
"""
...
            cur.execute(
                """
                INSERT INTO knowledge_drafts
                    (tenant_id, draft_key, draft_type,
                     ...
                ON CONFLICT (tenant_id, draft_key) DO NOTHING
                """,
                ...
            )
            written += cur.rowcount
```

外部素材管線的對應機制為 chunk_id，`knowledge-pipeline/pipeline/silver_to_knowledge/_provenance.py:27-30`：

```python
def chunk_id(source_type: str, source: str, chunk_index: str, content: str) -> str:
    """確定性 chunk id：同一來源同一段內容永遠同 id（冪等重跑不重複）。"""
    key = f"{source_type}\x00{source}\x00{chunk_index}\x00{content}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
```

### 步驟 5 — 來源讀取失敗的處置

`knowledge-pipeline/refinery/refinery/run_intake.py:46-75`

```python
        for card in cards:
            if not card.get("conversation_id"):
                print(f"[refinery] 跳過 {card['id'][:8]}:無關聯對話")
                skipped += 1
                continue
            transcript = intake.fetch_transcript(conn, card["conversation_id"])
            try:
                drafts = refine_card(
                    card, transcript,
                    generate=generate_json,
                    llm_model=llm_model,
                    refined_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception as e:  # noqa: BLE001 — 單卡失敗不中斷批次
                print(f"[refinery] 煉製失敗 {card['id'][:8]}:{e}", file=sys.stderr)
                skipped += 1
                continue
            ...
            store.supersede_rerefine(conn, tenant, card["id"])
            n = store.insert_drafts(conn, tenant, drafts)
```

失敗時 `store.insert_drafts` 完全不被呼叫，故無半成品 draft。失敗紀錄僅為 stderr 一行，`knowledge_drafts` 表無 failure 狀態值（`review.py:2-6` 列出的狀態為 `pending_review` / `approved` / `rejected` / `re_refine` / `superseded`）。

TC 判定基準寫「來源與失敗原因**可稽核**」／程式碼對「來源」有完整 provenance（步驟 6），對「失敗原因」只有 stderr 輸出與批次結束時的 `summary`（`run_intake.py:77-78`）。此處僅並陳，不裁定。

### 步驟 6 — 來源可稽核（provenance）

refinery 每筆 draft 帶 provenance，`knowledge-pipeline/refinery/refinery/refine.py:105-112`：

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

外部素材語料帶 bronze 路徑與雜湊，`knowledge-pipeline/pipeline/silver_to_knowledge/_provenance.py:1-8`：

```python
"""Provenance 解析 — 每個知識 chunk 可回溯到 bronze 來源檔。

治理依據（CLAUDE.md bronze-only 紅線）：知識內容嚴格源自
`knowledge-pipeline/storage/bronze/`；GDrive PDF 內容不可信、只引 URL。
本模組讓紅線機器可查核：chunk 帶 bronze 檔路徑 + sha256，
audit_corpus.py 據此驗證來源存在且未漂移。
"""
```

漂移偵測 `audit_corpus.py:64-68`：

```python
            bronze = ROOT_DIR / bp
            if not bronze.exists():
                violations.append(f"{where} — bronze 檔不存在：{bp}")
            elif sha256_file(bronze) != bs:
                violations.append(f"{where} — bronze 內容已漂移（sha256 不符）：{bp}")
```

### 步驟 7 — 執行既有測試

第一輪（未帶 DB）：

```
cd knowledge-pipeline/refinery && python -m pytest tests/ -q
24 passed, 12 skipped in 0.89s
```

skip 原因為「需 POSTGRES_URI(scratch 庫)」（`tests/test_intake_component.py:91` 等）。

第二輪（本機 Docker 測試庫）：

```
cd knowledge-pipeline/refinery && POSTGRES_URI=<本機測試庫> \
  REFINERY_TENANT_ID=00000000-0000-0000-0000-000000000001 python -m pytest tests/ -q
36 passed, 1 warning in 2.27s
```

---

## 既有測試證據

- `knowledge-pipeline/refinery/tests/`：36 項，接上測試庫後全過（步驟 7）；涵蓋 `test_intake_component.py`（撿卡條件）、`test_refine_unit.py`（分流與 draft_key）、`test_entitlement.py`（License gate）、`test_review_service.py`（狀態機）、`test_oidc_auth.py`、`test_observability.py`。
- 無對應既有測試涵蓋「raw→bronze 的來源准許 gate」——該 gate 在程式碼中不存在於 bronze 入口。

---

## 觀測到的其他事實

1. **License gate 在汲取入口而非 API 層**：`knowledge-pipeline/refinery/refinery/run_intake.py:29-35`

```python
    # CR-0166 R3：refinery 為 License 附加模組——租戶須開通 'refinery' 才可煉製。
    from .entitlement import ModuleNotEntitledError, assert_refinery_entitled
    try:
        assert_refinery_entitled(tenant)
    except ModuleNotEntitledError as e:
        print(f"[refinery] {e}", file=sys.stderr)
        return 2  # 未開通：明確退出碼（≠0 gate 未過，≠1 執行錯誤）
```

`entitlement.py:26-32` 的 fail 方向為：平台庫未配置 → `True`（fail-open，本機 dev）；DB 失敗或查無租戶 → `False`（fail-closed）。

2. **FR-REF-01 於 SRS 標為待確認**：`smartlock-docs/enterprise/04_SRS.md:341` 該列的驗收欄為「汲取機制（api 唯讀端點 / 批次匯出 / 事件）`[待確認]`」；同檔 `:555` 的待確認清單第 2 項為「refinery 診斷對話汲取機制（api 唯讀端點 / 批次匯出 / Kafka 事件）」。程式碼實作為 CLI 批次直連品牌 DB 唯讀（`intake.py:1`）。

3. **`storage/bronze/` 的目錄結構為 source_type 分層**：`_provenance.py:38-42` 以 `BRONZE_DIR / source_type / source` 定位，並在 `:31-34` 保留一張別名表處理「silver 產生後 bronze 曾改名（錯字修正）」的血緣漂移。

4. **逐字稿讀取無失敗分支**：`knowledge-pipeline/refinery/refinery/intake.py:60-80` 的 `fetch_transcript` 直接執行 SQL 並回列表，無 try/except；DB 層例外會逸出到 `run_intake.py` 的 `with db.connect() as conn:` 區塊外（該 `try` 只包住 `refine_card`，見 `:52-62`）。
</content>
