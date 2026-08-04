# TC-REF-SPLIT-01 — 提煉分流：事實／行為兩軌、惡意覆寫 prompt、re-refine

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 refinery 全測試 36 項全過（見步驟 6）。TC 步驟中的「惡意覆寫 prompt 是否被 LLM 忽略」需真實 LLM 回應才能判定，屬本走查無法涵蓋的部分 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `knowledge-pipeline/refinery/refinery/{refine,store,review,publisher,llm}.py`、`SQL/migrations/094-knowledge-drafts.sql`、`knowledge-pipeline/refinery/tests/test_refine_unit.py` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | **兩軌分流**成立且由 DB CHECK 收斂：`draft_type IN ('case_entry','behavior')`（`SQL/migrations/094-knowledge-drafts.sql:20`），`refine_card` 對 `case_entry` 必產一則、`behavior` 0-2 則（`refine.py:116-150`），且兩軌 payload 結構不同（事實軌 `{symptom, resolution}`、行為軌 `{proposal, target_skill, rationale}`）。**未核可 draft 不改既有內容**成立：落地只在 `review.approve` 內發生（`review.py:89-108`），`reject` / `re_refine` 路徑不呼叫 publisher。**重跑 append-only 可回溯**成立：`ON CONFLICT (tenant_id, draft_key) DO NOTHING`（`store.py:42`）＋ re_refine 舊 draft 標 `superseded` 不刪列（`store.py:13-25`）。**惡意覆寫 prompt 的防護**在程式碼中只有 system prompt 的文字鐵律（`refine.py:59-62`）與 JSON schema 強制（`refine.py:19-48`）——**無程式化的注入偵測或內容過濾**，且 `_build_prompt`（`refine.py:81-91`）將逐字稿原文以 `[role] content` 直接串接進 user prompt，無跳脫處理。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：含事實、行為指令、惡意覆寫 prompt 的 silver fixture
- 步驟：執行 refine，檢查 facts/behavior 分流與 re-refine
- 預期結果（判定基準）：事實只進 fact draft、行為只進 skill diff；未核可 draft 不改既有內容；重跑 append-only 可回溯
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-REF-02｜屬於旅程腳本：SC-15

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 事實只進 fact draft | `knowledge-pipeline/refinery/refinery/refine.py:116-130`、`SQL/migrations/094-knowledge-drafts.sql:20` | 有 |
| 行為只進 skill diff | `refine.py:132-150`、`publisher.py:56-70`（patch artifact） | 有 |
| 兩軌 payload 結構分離 | `refine.py:117`、`:133-137`、`SQL/migrations/094-knowledge-drafts.sql:27-28` | 有 |
| 惡意覆寫 prompt 被拒 | `refine.py:59-62`（system prompt 鐵律）、`:19-48`（JSON schema） | 無法靜態判定：需 LLM 實際回應 |
| 惡意內容的程式化過濾 | — | **找不到**：無注入偵測／內容黑名單 |
| 未核可 draft 不改既有內容 | `review.py:89-108`、`:111-122` | 有 |
| 重跑 append-only | `store.py:28-55`、`:13-25` | 有 |
| 可回溯（provenance） | `refine.py:105-112`、`SQL/migrations/094-knowledge-drafts.sql:29-31` | 有 |
| re-refine 重煉 | `review.py:118-122`、`store.py:13-25`、`intake.py:31-35` | 有 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 排程 | 對一張卡執行 refine | `DraftsProduced` | 事實必產、行為選產 | `knowledge-pipeline/refinery/refinery/refine.py:114-150` | `case_entry` 必 append 一則；`behavior_candidates` 迴圈 append 0-N 則 |
| LLM | 回傳不合 schema 的結果 | `RefineFailed` | JSON schema 強制 | `refine.py:19-48`、`llm.py` | schema 由 `generate` 注入；`run_intake.py:59-62` 捕捉例外 → skip |
| 對話逐字稿 | 含「忽略前述指令」類文字 | `InjectionIgnored` | system prompt 鐵律 | `refine.py:59-62` | 僅為 prompt 文字約束，無程式化偵測 |
| 排程 | 對同一卡重跑 | （不新增重複 draft） | 冪等 | `store.py:42` | `ON CONFLICT (tenant_id, draft_key) DO NOTHING` |
| 審核者 | 退回重煉 | `DraftReRefine` | 樂觀鎖 | `review.py:68-86`、`:118-122` | `WHERE status='pending_review'`；rowcount 0 → `INVALID_TRANSITION` |
| 排程 | 重煉後再寫 draft | `OldDraftSuperseded` | append-only | `store.py:13-25`、`run_intake.py:71-72` | 舊 `re_refine` draft → `superseded`（UPDATE 狀態，不刪列） |
| 審核者 | 拒絕 draft | `DraftRejected` | 不落地 | `review.py:111-115` | 只轉狀態 + commit，不呼叫 publisher |
| 審核者 | 核可 draft | `DraftApproved` + 落地 | 同一交易 | `review.py:89-108` | 先 `_transition` 佔鎖再落地；落地失敗全回滾 |

---

## 逐層走查

### 步驟 1 — 兩軌的定義與 DB 收斂

`SQL/migrations/094-knowledge-drafts.sql:19-28`

```sql
    -- 兩軌分流(ADR-018 步驟②):case_entry=事實軌(案例史)、behavior=行為軌(skill SOP 候選)
    draft_type              VARCHAR(20) NOT NULL CHECK (draft_type IN ('case_entry', 'behavior')),
    ...
    -- 結構化草稿:case_entry={symptom, resolution};behavior={proposal, target_skill, rationale}
    payload                 JSONB NOT NULL,
```

分流規則的程式碼註解，`knowledge-pipeline/refinery/refinery/refine.py:1-10`：

```python
"""提煉分流器 — 卡 spine + 對話逐字稿 → 兩軌 draft(ADR-018 步驟②/CR-0139)。

分流規則:
  事實軌 case_entry(必產):症狀→解法的案例史素材,目標落點=案例語料(2.3.2 Publisher 灌)
  行為軌 behavior(選產):對話展現的可重用客服 SOP 模式,目標落點=locksmith-cs-sop skill
    (references/skill 鎖定中——本層只產 draft,寫入屬 2.3.2 且需業主解鎖,CIA §8-3)

不得編造:LLM 只能整理卡欄位與逐字稿既有資訊;provenance 記全程溯源。
冪等:draft_key = sha256(card_id + draft_type + 正規化 payload)[:16]。
"""
```

### 步驟 2 — 分流的實作

`knowledge-pipeline/refinery/refinery/refine.py:114-150`

```python
    drafts: list[dict] = []

    ce = result["case_entry"]
    ce_payload = {"symptom": ce["symptom"], "resolution": ce["resolution"]}
    drafts.append({
        "draft_key": draft_key(card["id"], "case_entry", ce_payload),
        "draft_type": "case_entry",
        ...
    })

    for bc in result.get("behavior_candidates", []):
        bc_payload = {
            "proposal": bc["proposal"],
            "target_skill": bc["target_skill"],
            "rationale": bc["rationale"],
        }
        drafts.append({
            "draft_key": draft_key(card["id"], "behavior", bc_payload),
            "draft_type": "behavior",
            ...
        })
```

兩軌欄位不交叉：事實軌 payload 只含 `symptom` / `resolution`，行為軌只含 `proposal` / `target_skill` / `rationale`。落地時亦分流，`knowledge-pipeline/refinery/refinery/review.py:97-105`：

```python
    if draft["draft_type"] == "case_entry":
        case_id = publisher.publish_case_entry(
            conn, tenant, draft,
            reviewer_id=reviewer_id, embed_fn=embed_fn, embed_model_name=embed_model_name,
        )
        published = {"kind": "case_entry", "case_entry_id": case_id,
                     "embedding_model": embed_model_name}
    else:
        published = {"kind": "behavior_patch", **publisher.behavior_patch_artifact(draft)}
```

事實軌落 `case_entries`（`publisher.py:34-53`），行為軌只產 patch artifact（`publisher.py:56-70`），落檔目標為 `agent/lockcore/skills/locksmith-cs-sop/references/refined`（`publisher.py:17`）。

### 步驟 3 — LLM 輸出的 schema 約束與 prompt 鐵律

`knowledge-pipeline/refinery/refinery/refine.py:18-48`

```python
# LLM 輸出 schema(litellm JSON schema 強制;fake 注入時亦依此驗)
REFINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "case_entry": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "symptom": {"type": "string"},
                "resolution": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["title", "symptom", "resolution", "confidence"],
        },
        "behavior_candidates": { ... },
    },
    "required": ["case_entry", "behavior_candidates"],
}
```

`knowledge-pipeline/refinery/refinery/refine.py:56-62`

```python
2. behavior_candidates(0 到 2 則):僅當對話展現「可重用的客服處理模式」
   (如特定情境的問法順序、轉接時機、安全拒答姿態)才產;target_skill 固定 "locksmith-cs-sop"。

鐵律:
- 只能整理輸入中既有的資訊,不得推測或編造未出現的事實
- 使用繁體中文;品牌/型號/術語保持原文
- confidence 為 0-1,反映素材完整度與可重用性"""
```

逐字稿的組裝方式，`knowledge-pipeline/refinery/refinery/refine.py:81-91`：

```python
def _build_prompt(card: dict, transcript: list[dict]) -> str:
    lines = [f"[{m['sender_role']}] {m['content']}" for m in transcript]
    return (
        "## 問題卡\n"
        + json.dumps(_spine_snapshot(card) | {
            "brand": card.get("brand"), "model": card.get("model"),
            "category": card.get("category"),
        }, ensure_ascii=False, indent=1)
        + "\n\n## 對話逐字稿\n"
        + ("\n".join(lines) if lines else "(無文字訊息)")
    )
```

`m['content']` 為 DB 原文，未經跳脫、標記或長度截斷。

TC 前置寫「含…惡意覆寫 prompt 的 silver fixture」、判定基準寫「事實只進 fact draft、行為只進 skill diff」／程式碼對注入的抵抗僅為 system prompt 文字鐵律與輸出 schema 形狀約束；`target_skill` 雖在 prompt 中要求固定為 `locksmith-cs-sop`，但 `refine.py:135` 直接採用 LLM 回傳值寫入 payload，無程式端白名單比對。此處僅並陳，不裁定。

由於「LLM 是否遵守鐵律」需真實模型回應，此判定基準的最終效果**無法由靜態走查得出**。

### 步驟 4 — 未核可 draft 不改既有內容

`knowledge-pipeline/refinery/refinery/review.py:1-7`

```python
"""審核層 — draft 讀取與狀態轉移(15_SDS §9.2 狀態機/CR-0140)。

轉移(僅 pending_review 可動作;HITL 硬 gate:approve 時才呼叫 Publisher):
  pending_review → approved(事實軌落 case_entries;行為軌產 patch artifact)
                 → rejected(留 audit)
                 → re_refine(2.3.1 intake 重撿,舊 draft 屆時標 superseded)
"""
```

`knowledge-pipeline/refinery/refinery/review.py:89-108`

```python
def approve(conn: psycopg.Connection, tenant: str, draft_id: int, *,
            reviewer_id: str, comment: str | None,
            embed_fn: Callable[[str], list[float]],
            embed_model_name: str) -> dict:
    """核可:先轉移(佔鎖)再落地;同一交易,落地失敗全回滾(核可前絕不落地的反向保證)。"""
    draft = get_draft(conn, tenant, draft_id)
    _transition(conn, tenant, draft_id, to_status="approved",
                reviewer_id=reviewer_id, comment=comment)
```

`reject`（`:111-115`）與 `re_refine`（`:118-122`）皆只呼叫 `_transition` + `conn.commit()`，全檔對 `publisher` 的呼叫僅出現在 `approve` 內（`:98`、`:105`、`:106`）。

狀態轉移採樂觀鎖，`knowledge-pipeline/refinery/refinery/review.py:68-86`：

```python
def _transition(conn: psycopg.Connection, tenant: str, draft_id: int, *,
                to_status: str, reviewer_id: str, comment: str | None) -> None:
    """pending_review → to_status(樂觀鎖:WHERE status='pending_review')。不 commit。"""
    ...
            WHERE tenant_id = %s AND id = %s AND status = 'pending_review'
    ...
        if cur.rowcount == 0:
            raise ReviewError(
                "INVALID_TRANSITION",
                f"draft {draft_id} 非 pending_review,不可轉 {to_status}",
            )
```

### 步驟 5 — re-refine 與 append-only

退回重煉後，下一輪 intake 會重新撿起同一張卡，`knowledge-pipeline/refinery/refinery/intake.py:31-35`：

```python
  AND NOT EXISTS (
      SELECT 1 FROM knowledge_drafts kd
      WHERE kd.source_problem_card_id = pc.id
        AND kd.status <> 're_refine'
  )
```

舊 draft 於重寫前標 superseded（不刪列），`knowledge-pipeline/refinery/refinery/store.py:13-25`：

```python
def supersede_rerefine(conn: psycopg.Connection, tenant: str, card_id: str) -> int:
    """該卡被審核者退回重煉的舊 draft → superseded。回異動列數。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE knowledge_drafts
            SET status = 'superseded', updated_at = now()
            WHERE tenant_id = %s AND source_problem_card_id = %s::uuid
              AND status = 're_refine'
            """,
            (tenant, card_id),
        )
        return cur.rowcount
```

呼叫順序在 `run_intake.py:71-73`：

```python
            store.supersede_rerefine(conn, tenant, card["id"])
            n = store.insert_drafts(conn, tenant, drafts)
            written += n
```

DB 狀態值域 `SQL/migrations/094-knowledge-drafts.sql:32-33`：

```sql
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review', 'approved', 'rejected', 're_refine', 'superseded')),
```

全表無 DELETE 路徑：`git grep -n "DELETE FROM knowledge_drafts" -- knowledge-pipeline/` 零命中。

### 步驟 6 — 執行既有測試

```
cd knowledge-pipeline/refinery && POSTGRES_URI=<本機測試庫> \
  REFINERY_TENANT_ID=00000000-0000-0000-0000-000000000001 python -m pytest tests/ -q
36 passed, 1 warning in 2.27s
```

分流相關測試在 `knowledge-pipeline/refinery/tests/test_refine_unit.py`，三項：

```
:51  def test_refine_card_two_tracks_with_provenance():
:75  def test_draft_key_deterministic_and_content_sensitive():
:83  def test_no_behavior_candidates_ok():
```

該檔以注入的 fake `generate` 執行，不打真實 LLM；`git grep -ni "injection\|惡意\|覆寫" -- knowledge-pipeline/refinery/tests` 零命中。

---

## 既有測試證據

- `knowledge-pipeline/refinery/tests/`：36 項全過（步驟 6）。
- 分流與冪等由 `test_refine_unit.py:51-90` 三項覆蓋（fake LLM 注入）。
- 無對應既有測試涵蓋「惡意覆寫 prompt」——該情境需真實 LLM 回應。

---

## 觀測到的其他事實

1. **行為軌落檔不由服務端執行**：`knowledge-pipeline/refinery/refinery/publisher.py:5-7`

```python
行為軌 behavior:產 patch artifact(target_path + content 存回 draft provenance),
  實際落檔走 `python -m refinery.apply_behavior`(repo checkout 內執行,人 git commit)
  ——服務容器無 skills 檔案系統,git 寫入本質是 repo 操作(CIA D5)。
```

TC 判定基準的「行為只進 skill diff」在程式碼中對應的是 `behavior_patch_artifact` 產出的 `{target_path, content}`，寫檔為另一支 CLI（`apply_behavior.py`）。

2. **`target_skill` 由 LLM 回傳值直接採用**：`refine.py:133-137` 將 `bc["target_skill"]` 原樣放入 payload，程式端未比對 `locksmith-cs-sop` 白名單；schema（`:38-43`）僅要求該欄為 string。

3. **draft_key 對內容敏感**：`refine.py:67-71` 以 `sort_keys=True` 正規化 payload 後雜湊，故同一張卡若 LLM 產出不同文字，會產生新 draft_key 而非覆寫既有——與 append-only 語意一致，但也意味著同卡重跑若 LLM 輸出漂移會累積多筆 draft。

4. **`case_entries` 落地帶溯源欄**：`publisher.py:36-51` 的 INSERT 帶 `source='refinery'`、`approved_by`、`verified=TRUE`、`source_problem_card_id`，即事實軌落地時記錄核可者與來源卡。
</content>
