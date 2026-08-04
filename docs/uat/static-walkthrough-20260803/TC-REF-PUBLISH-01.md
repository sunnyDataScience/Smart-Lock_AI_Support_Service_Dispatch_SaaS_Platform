# TC-REF-PUBLISH-01 — 核可後發布：未核可零落地、雙簽、Family Reviewer 逾時、來源白名單、跨租戶

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 refinery 全測試 36 項、API skill/config 相關 58 項全過，並實跑 references provenance gate（exit=0，31 個 reference）（見步驟 7） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `knowledge-pipeline/refinery/refinery/{review,publisher,service,db}.py`、`api/services/family_review_service.py`、`api/realtime/family_review_sla_cron.py`、`api/services/skill_service.py`、`api/routers/skills_v2.py`、`agent/lockcore/agent/skill_sync.py`、`scripts/ci/references-provenance-check.py`、`knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py`、`SQL/migrations/095-case-entries-merge-shape.sql` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | 五個違規情境中三個有落點、兩個沒有：**未核可發布**——`review.approve` 是唯一落地入口，`reject`/`re_refine` 不呼叫 publisher（`review.py:89-122`），且落地與狀態轉移同交易、失敗全回滾（`:93`）；**跨租戶 publish**——refinery 側 `require_reviewer` 比對 token tenant 與服務 tenant（`service.py:92-94`），落地 SQL 一律帶 `db.tenant_id()`（`review.py:139`、`:146`）；skill 側 `tenant_id` 取自 token claim，非請求參數（`skills_v2.py:78` 等）；**Family Reviewer 逾時**——有 SLA cron 寫 audit + 通知（`family_review_sla_cron.py:89-161`），但**未暫停 publish**（該 cron 對 `sop_drafts` 只 SELECT，無狀態變更）；**同人雙簽**——`SOD_VIOLATION` 403 存在於 SOP 家族覆核（`family_review_service.py:226-231`），但 **refinery draft 審核路徑無雙簽**（`review.py:89-108` 單一 `reviewer_id`）；**來源非 bronze**——`publisher.publish_case_entry`（`publisher.py:20-53`）**無任何 bronze 來源校驗**，bronze 白名單檢查存在於另兩個位置（`audit_corpus.py:55-68` 檢查 corpus JSONL、`scripts/ci/references-provenance-check.py` 檢查 references 結構），皆非 Publisher 灌注前的 gate。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：approved/rejected/high-risk draft、兩租戶、Family Reviewer fixture
- 步驟：嘗試未核可發布、同人雙簽、Family Reviewer 逾時、來源非 bronze、跨租戶 publish
- 預期結果（判定基準）：違規均零落地；核可後 facts 帶 tenant/provenance 進 pgvector、行為 append-only 發佈；逾時暫停並升級
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-REF-03、FR-REF-04、FR-REF-05｜屬於旅程腳本：SC-15、SC-16

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 未核可不得發布 | `knowledge-pipeline/refinery/refinery/review.py:89-122` | 有 |
| 未核可零落地（交易保證） | `review.py:93-107` | 有 |
| 同人雙簽被擋（SOP 家族覆核） | `api/services/family_review_service.py:223-231` | 有（`SOD_VIOLATION` 403） |
| 同人雙簽被擋（refinery draft） | — | **找不到**：單一 reviewer，無第二簽 |
| Family Reviewer 逾時升級 | `api/realtime/family_review_sla_cron.py:89-141` | 有（audit + 通知） |
| Family Reviewer 逾時暫停 publish | — | **找不到**：cron 不改 draft 狀態 |
| 來源非 bronze 被 Publisher 擋下 | — | **找不到**：`publisher.py:20-53` 無來源校驗 |
| bronze 白名單稽核（corpus 側） | `knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:55-68` | 有（CI gate，非 Publisher 前置） |
| bronze provenance 稽核（references 側） | `scripts/ci/references-provenance-check.py` | 有（結構 gate；檔頭自述不驗 bronze 內容） |
| 跨租戶 publish 被擋（refinery） | `knowledge-pipeline/refinery/refinery/service.py:92-94`、`review.py:139/146` | 有 |
| 跨租戶 publish 被擋（skill） | `api/routers/skills_v2.py:148-161`（`user.tenant_id`） | 有 |
| facts 帶 tenant/provenance 進 pgvector | `publisher.py:34-53` | 有 |
| 行為 append-only 發佈 | `publisher.py:56-70`、`api/services/skill_service.py:443-478` | 有 |
| 發佈後 ≤60s 生效 | `agent/lockcore/agent/skill_sync.py:31`、`:99-115` | 有（60s 輪詢 + stamp 比對） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 審核者 | 對非 pending_review 的 draft 發布 | `RequestRejected(409)` | 樂觀鎖 | `knowledge-pipeline/refinery/refinery/review.py:82-86` | rowcount 0 → `INVALID_TRANSITION` 409 |
| 審核者 | 核可 draft（事實軌） | `CaseEntryPublished` | 同交易 | `review.py:97-101`、`publisher.py:34-53` | INSERT `case_entries`（帶 `tenant_id`、`source='refinery'`、`approved_by`、`verified=TRUE`、`embedding`） |
| 審核者 | 核可 draft（行為軌） | `BehaviorPatchProduced` | append-only 新檔 | `publisher.py:56-70` | 產 `{target_path, content}`，target 為 `…/references/refined/<YYYYMMDD>-<draft_key>.md` |
| 審核者 | 落地失敗 | `PublishRolledBack` | 核可前絕不落地的反向保證 | `review.py:93` | docstring 自述「同一交易,落地失敗全回滾」 |
| 同一人 | 對自己初審過的 SOP 做家族覆核 | `RequestRejected(403)` | 四眼 | `api/services/family_review_service.py:226-231` | `SOD_VIOLATION` 403 |
| 同一人 | 對自己送的 refinery draft 核可 | （TC 預期擋） | 雙簽 | — | **找不到**：無 proposer 概念，`_transition` 只寫單一 `reviewed_by` |
| 系統 | Family Reviewer 逾 24h | `FamilyReviewOverdue` | SLA 24h | `api/realtime/family_review_sla_cron.py:121-135` | 寫 `audit_events`（`action='sop.family_review_overdue'`）+ 通知 admin/ops |
| 系統 | 逾時後暫停 publish | `PublishSuspended` | 缺席暫停 | — | **找不到**：cron 對 `sop_drafts` 僅 SELECT |
| 審核者 A 租戶 | publish B 租戶的 draft | `RequestRejected` | 租戶隔離 | `service.py:92-94`、`review.py:59-64` | token tenant ≠ 服務 tenant → 403；查 draft 一律帶 `WHERE tenant_id = %s` → 404 |
| agent | 取得新發佈 skill | `SkillOverlaySwapped` | ≤60s | `agent/lockcore/agent/skill_sync.py:99-115` | stamp 變動才全量重拉 + 原子 symlink 換裝 |

---

## 逐層走查

### 步驟 1 — 未核可零落地

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
    if draft["draft_type"] == "case_entry":
        case_id = publisher.publish_case_entry(...)
        ...
    else:
        published = {"kind": "behavior_patch", **publisher.behavior_patch_artifact(draft)}
    publisher.record_publish_result(conn, tenant, draft_id, published)
    conn.commit()
    return published
```

`publisher` 在全檔的呼叫點僅此三處（`:98`、`:105`、`:106`），皆在 `approve` 內。

### 步驟 2 — 同人雙簽

**SOP 家族覆核路徑有**，`api/services/family_review_service.py:223-231`：

```python
    # TI-A10-02 / 合約 4.4(d)：高風險 SOP 雙審 —— 家族覆核者須異於初審 admin
    # （Knowledge Owner ≠ domain expert，四眼），同人不得兩審。
    admin_reviewer = row[1]
    if admin_reviewer and str(admin_reviewer) == str(reviewer_id):
        raise ApiError(
            "SOD_VIOLATION",
            "family reviewer must differ from initial admin reviewer (dual-review)",
            403,
        )
```

該表另有 hash-chain 不可篡改 ledger（`family_review_service.py:233-252`）與 DB uniq（`:255-260` 捕捉 `uniq_family_review_draft` → 409）。

**refinery draft 審核路徑沒有**：`review.py:68-86` 的 `_transition` 只寫一個 `reviewed_by`；`knowledge_drafts` 表（`SQL/migrations/094-knowledge-drafts.sql:15-41`）無 proposer / co-signer 欄位；`git grep -n "SOD_VIOLATION\|dual" -- knowledge-pipeline/` 零命中。

TC 步驟寫「同人雙簽」為五種違規之一、判定基準寫「違規均零落地」（出處：② 測試案例主表 TC-REF-PUBLISH-01 列）／程式碼在 SOP 家族覆核有此判定、在 refinery draft 發布路徑無此判定。此處僅並陳，不裁定。

### 步驟 3 — Family Reviewer 逾時

`api/realtime/family_review_sla_cron.py:1-11`

```python
"""家族覆核 SLA 逾時升級 cron — CR-0166 R1（合約 4.4(d) / BR-SOP-002）。

家族覆核端點宣稱 reviewer SLA 24h，但逾時無任何升級機制。本 cron 每日掃
sop_drafts.reviewed_at（管理員初審通過時間）超過 24h、仍未有 family_reviews
紀錄的草稿 → 寫 audit event（sop.family_review_overdue）＋通知該租戶管理層。

去重（同一 draft 只升級一次、跨重啟安全）：以 audit_events 查重，不用 in-memory。
對齊 DisputeEscalationCron pattern：ensure_leader + startup delay + run_once 可手動觸發。

「累計 ≥3 件未審 → ChangeRequest 替補提名」（BR-SOP-002 後半）列 Phase II backlog。
"""
```

`api/realtime/family_review_sla_cron.py:93-114` 的 `run_once` 對 `sop_drafts` 只有 SELECT：

```python
        cur = await db_module._conn.execute(
            "SELECT sd.id, sd.tenant_id, sd.title, sd.reviewed_at "
            "FROM sop_drafts sd "
            "WHERE LOWER(sd.status) = 'approved' "
            "  AND sd.reviewed_at IS NOT NULL "
            "  AND sd.reviewed_at < NOW() - (%s * INTERVAL '1 hour') "
            ...
```

`_escalate_one`（`:116-140`）只做兩件事：寫 append-only audit（`:121-135`）與通知管理層（`:138`，best-effort）。全檔無 `UPDATE sop_drafts`。

SLA 門檻可由環境變數覆寫，`:27`：

```python
SLA_HOURS = int(os.getenv("FAMILY_REVIEW_SLA_HOURS", "24"))
```

TC 判定基準寫「逾時**暫停**並升級」／程式碼實作了升級（audit + 通知），未實作暫停（無狀態變更、無 publish 阻擋）。此處僅並陳，不裁定。

### 步驟 4 — 來源非 bronze

`knowledge-pipeline/refinery/refinery/publisher.py:20-53`（全函式）

```python
def publish_case_entry(
    conn: psycopg.Connection,
    tenant: str,
    draft: dict,
    *,
    reviewer_id: str,
    embed_fn: Callable[[str], list[float]],
    embed_model_name: str,
) -> str:
    """draft(case_entry 軌)→ case_entries 一列;回 case_entry id。不 commit(由呼叫端交易)。"""
    payload = draft["payload"]
    symptom = payload["symptom"]
    vec = embed_fn(symptom)
    vec_literal = "[" + ",".join(f"{v:.7g}" for v in vec) + "]"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO case_entries
                (tenant_id, title, problem_description, solution, brand, model,
                 source, approved_by, verified, is_active,
                 embedding, embedding_model, embedding_status, source_problem_card_id)
            VALUES (%s, %s, %s, %s, %s, %s,
                    'refinery', %s::uuid, TRUE, TRUE,
                    %s::vector, %s, 'ready', %s::uuid)
            RETURNING id
            """,
```

`git grep -n "bronze" -- knowledge-pipeline/refinery/` 零命中。

bronze 白名單檢查存在於另外兩處，皆非 Publisher 前置：

- corpus 側，`knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:55-68`（gdrive 不得進 facts；bronze 檔存在且 sha256 未漂移）。
- references 側，`scripts/ci/references-provenance-check.py:1-17`：

```python
"""FR-REF-04：references 側 bronze provenance gate（雙路一致性的 references 半邊）。
...
註（sourcing rule，CLAUDE.md）：references 內容源自 bronze（YouTube/website/video）；
GDrive/PDF **只引 URL 不抄內容**——「引 URL」為允許（指標），故本 gate **不**擋 GDrive URL
引用（那是合法指標），只驗結構與 brand 對齊。references 無機讀 bronze provenance metadata
（內容鎖定、人工由 bronze 策展），故「源自 bronze」在 references 側靠 authoring 紀律 +
本結構 gate；corpus 側的完整 bronze provenance（bronze_path+sha256）由 audit_corpus.py 稽核。
```

refinery 的 case_entry 來源是問題卡與對話逐字稿（`refine.py:105-112` 的 provenance），不經 bronze 檔案樹，故 bronze 路徑校驗在此軌無對應資料可驗。

FR-REF-04 原文（`smartlock-docs/enterprise/04_SRS.md:344`）為「Publisher 灌注前校驗 source 屬 bronze 白名單；references ↔ pgvector CI 同源檢查（🔜 規劃中）」／程式碼的 Publisher（`publisher.py:20-53`）無此校驗。此處僅並陳，不裁定。

### 步驟 5 — 跨租戶 publish

refinery 審核 API 的守衛，`knowledge-pipeline/refinery/refinery/service.py:78-94`：

```python
def require_reviewer(request: Request) -> dict:
    """Bearer JWT(與 api 同 secret/HS256)→ 審核角色白名單 + tenant 相符。"""
    ...
    role = payload.get("role", "")
    if role not in _REVIEW_ROLES:
        raise HTTPException(..., "message": f"角色 {role} 無審核權"})
    if payload.get("tenant_id") != db.tenant_id():
        raise HTTPException(..., "message": "token tenant 與服務不符"})
```

所有審核操作以服務層 tenant（非請求參數）呼叫，`knowledge-pipeline/refinery/refinery/service.py:144-146`：

```python
def _do_review(action, draft_id: int, body: ReviewBody, user: dict, conn):
    try:
        result = action(conn, db.tenant_id(), draft_id,
```

讀取端一律帶 tenant，`review.py:55-64`：

```python
def get_draft(conn: psycopg.Connection, tenant: str, draft_id: int) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_DRAFT_COLS)} FROM knowledge_drafts "
            "WHERE tenant_id = %s AND id = %s",
            (tenant, draft_id),
        )
        row = cur.fetchone()
    if row is None:
        raise ReviewError("DRAFT_NOT_FOUND", f"draft {draft_id} 不存在", 404)
```

skill 發佈端亦以 token claim 為 tenant，`api/routers/skills_v2.py:148-161`：

```python
async def publish_skill(
    ...
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
```

service 端 SQL 一律 `WHERE tenant_id = %s::uuid`（`api/services/skill_service.py:342-345`、`:357-366`）。

### 步驟 6 — 核可後的兩軌落地與生效路徑

**事實軌 → pgvector**：`publisher.py:36-51` 的 INSERT 帶 `tenant_id`、`embedding`、`embedding_model`、`embedding_status='ready'`、`source_problem_card_id`。檢索端對應 `agent/rag/rag/store.py:113-134`，`WHERE tenant_id = %s AND embedding IS NOT NULL AND is_active AND deleted_at IS NULL`，同檔 `:110` 註明「只有 refinery Publisher 灌入的列可被語義檢索」。

**行為軌 → skill**：`publisher.py:56-70` 產 patch artifact，target 目錄 `publisher.py:17`：

```python
# 行為軌落檔目標(append-only 新檔;product-knowledge references 鎖定不受影響)
BEHAVIOR_TARGET_DIR = "agent/lockcore/skills/locksmith-cs-sop/references/refined"
```

品牌庫路線的加性合併在 `api/services/skill_service.py:443-478`：

```python
async def ingest_revision(
    ...
    """knowledge-pipeline 自動汲取通道（HD-2=a：一律進 draft，人工發佈——絕不 publish，
    故對 agent 回答品質零影響，須人工審核發佈後才生效）。

    merge=True（refinery 行為軌用）：只送新增/更新的檔（如單一 refined reference），
    後端讀現有基準（草稿>發佈>最新）併入後存草稿——**嚴格加性**，保留既有 SKILL.md 與
    所有 references，只新增，不刪改，確保發佈後 skill 為既有內容的超集。
    """
    ...
        files = {**baseline, **files}  # 新檔覆蓋/新增，其餘一律保留（加性）
```

發佈後生效路徑：`api/services/skill_service.py:481-490` 的 `_bump_stamp` → agent 端 `agent/lockcore/agent/skill_sync.py:99-115`：

```python
    async def _sync_once(self) -> bool:
        """查 stamp；變了才全量重拉並物化。回傳是否有換裝。"""
        stamp = await self._fetch_stamp()
        if stamp is None:
            return False  # 無 bundle 記錄 = 此租戶尚未發佈任何 skill → 不動 overlay
        if stamp == self._last_stamp:
            return False
        skills = await self._fetch_published_skills()
```

`_fetch_published_skills` 只取 published 且同 tenant，`skill_sync.py:141-152`：

```python
            cur = await conn.execute(
                "SELECT skill_name, files FROM saas.skill_revision "
                "WHERE tenant_id = %s::uuid AND status = 'published'",
                (self.tenant_id,),
            )
```

輪詢週期預設 60s（`skill_sync.py:31`：`_DEFAULT_POLL_SECONDS = 60`），wiring 在 `agent/scripts/line_gateway.py:121-129`。

### 步驟 7 — 執行既有測試

```
cd knowledge-pipeline/refinery && POSTGRES_URI=<本機測試庫> \
  REFINERY_TENANT_ID=00000000-0000-0000-0000-000000000001 python -m pytest tests/ -q
36 passed, 1 warning in 2.27s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest -p winloop_plugin \
  tests/test_skills_v2_endpoint.py tests/test_escalation_to_draft_pc.py \
  tests/test_internal_ingest.py tests/test_config_m18.py -q
58 passed, 3 skipped in 6.09s

python scripts/ci/references-provenance-check.py
✅ references provenance gate：31 個型號 reference 結構完整、brand 對齊目錄（corpus 側完整 bronze provenance 另由 audit_corpus.py 稽核）
exit=0
```

`knowledge-pipeline/refinery/tests/test_review_service.py` 內與本 TC 相關的測試位置：`:100`（狀態機）、`:117`、`:155`、`:177`、`:217`、`:228`、`:260`；`test_auth_guards` 覆蓋跨租戶／角色守衛。

---

## 既有測試證據

- `knowledge-pipeline/refinery/tests/`：36 項全過（步驟 7），含 `test_review_service.py` 的狀態機與 auth guard。
- `api/tests/test_skills_v2_endpoint.py` 等 4 檔：58 passed / 3 skipped。
- `scripts/ci/references-provenance-check.py`：exit=0，31 個 reference。
- 無對應既有測試涵蓋「refinery draft 同人雙簽」與「Publisher 前 bronze 白名單校驗」——兩項行為在程式碼中不存在。

---

## 觀測到的其他事實

1. **`agent/lockcore/skills/` builtin 與 `workspace/skills/` overlay 兩條發佈路線並存**：`agent/lockcore/agent/skill_sync.py:1-16` 自述「把 `saas.skill_revision` 的 published 版本拉下來、落盤到 `workspace/skills/`，SkillsLoader 的 overlay 機制（skills.py:_skill_entries_from_dir，workspace 優先於 builtin）即讓 agent 下一 turn 用到新知識——**不重佈**」，未配置時 `enabled=False`、行為與現況一致（`:16`、`:60-67`）。

2. **skill audit 為 best-effort、config audit 在交易內**：`api/services/skill_service.py:503-522` 的 `_write_audit` 失敗只 warning；`api/services/config_m18_service.py:200-214` 的 `_append_audit` 無 try/except。TC 判定基準未區分兩者，本項列為觀測事實。

3. **SkillSync 落盤有二次防禦**：`agent/lockcore/agent/skill_sync.py:178-201` 對 skill 名稱與相對路徑再驗一次（`_SKILL_NAME_RE`、`_safe_rel`、`resolve().relative_to(version_root_resolved)`），註解自述「service 端已驗，但 DB 讀回來也不盡信」。

4. **`case_entries` 併形來源**：`SQL/migrations/095-case-entries-merge-shape.sql:16` 註明「Phase D 溯源:核可案例 → 來源 knowledge_ready 問題卡(ADR-018)」，即事實軌的溯源錨點是問題卡而非 bronze 檔。
</content>
