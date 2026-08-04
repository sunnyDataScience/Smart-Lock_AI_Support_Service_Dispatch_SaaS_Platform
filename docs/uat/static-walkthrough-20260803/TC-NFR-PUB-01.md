# TC-NFR-PUB-01 — 未核可零落地、append-only、同源檢查、跨租戶 default deny

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `knowledge-pipeline/refinery/refinery/review.py`、`publisher.py`、`intake.py`、`apply_behavior.py`、`entitlement.py`、`api/routers/skills_v2.py`、`api/services/skill_service.py`、`SQL/migrations/106-skill-revisions.sql`、`agent/lockcore/agent/skill_sync.py`、`agent/rag/rag/store.py`、`scripts/ci/references-provenance-check.py`、`knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py` |
| 優先級 / 路徑類型 | P0 / failure |
| 旅程 | SC-15 |

判定理由：四項判定基準中三項在程式碼中有對應實作、一項僅部分。**未核可零落地**：refinery 的 `approve()` 是唯一觸發 Publisher 的入口，且以樂觀鎖 `WHERE status='pending_review'` 佔位後同交易落地、失敗全回滾（`knowledge-pipeline/refinery/refinery/review.py:66-105`）；pipeline 自動汲取一律進 draft、絕不 publish（`api/services/skill_service.py:450-453`）；skill 發佈端點限 `FULL_ACCESS_ROLES`（`api/routers/skills_v2.py:146-160`）。**append-only**：`saas.skill_revision` 為版本快照表、`skills_v2.py` 無任何 `DELETE` 端點、`skill_service.py` 無 DELETE SQL，舊版轉 `retired` 而非刪除（`SQL/migrations/106-skill-revisions.sql:27-56`）；merge 汲取為嚴格加性（`api/services/skill_service.py:463-471`）。**但**「檔案層」不是 append-only：`save_draft` 以 `SET files = %s::jsonb` 整體覆蓋（`api/services/skill_service.py:293-299`），SkillSync 物化為版本目錄全量重建 + symlink 換裝（`agent/lockcore/agent/skill_sync.py:155-171`），故人工存草稿時少帶檔案並發佈，workspace overlay 中該檔會消失（舊 revision 仍留於 DB）。**同源檢查**：兩支腳本存在（`scripts/ci/references-provenance-check.py`、`knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py`），但 `.github/workflows/` 中無任何 job 呼叫它們（零命中），故「CI 阻擋」不成立。**跨租戶 default deny**：RAG 查詢無 `RAG_TENANT_ID` 直接 raise（`agent/rag/rag/store.py:29-33`），兩支檢索 SQL 皆帶 `WHERE tenant_id = %s`；skill 端點的 `tenant_id` 一律取自 JWT（`api/routers/skills_v2.py:78`、`:104` 等），內部汲取端點另有 `assert_tenant_scope`（`:199`）。

**TC 原文**｜章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）｜前置：draft、approved revision、錯來源與跨 tenant fixture｜步驟：未核可 publish、刪除既有 skill、來源不同步、tenant A 查 B 語料｜判定基準：未核可零落地；更新 append-only；同源檢查失敗即阻擋；跨租戶 default deny｜路徑類型：failure｜驗證面向：功能｜優先級：P0｜驗證哪些需求：NFR-PUB-001～004｜旅程：SC-15

---

## 逐條驗收條件對照

| 條件（對應 NFR） | 類型 | 程式碼落點 | 狀態 |
|---|---|---|---|
| 只有 approve 才觸發 Publisher（NFR-PUB-001） | 機制存在 | `knowledge-pipeline/refinery/refinery/review.py:87-105` | 存在（唯一入口） |
| 非 `pending_review` 不可轉核可 | 機制存在 | `knowledge-pipeline/refinery/refinery/review.py:66-84` | 存在（樂觀鎖 + `INVALID_TRANSITION`） |
| 落地失敗全回滾 | 機制存在 | `knowledge-pipeline/refinery/refinery/review.py:88`、`:104` | 存在（同交易，末尾才 commit） |
| refinery 套件不直接寫 pgvector/skill | 機制存在 | `knowledge-pipeline/refinery/refinery/__init__.py:9` | 存在（檔內硬 gate 宣告） |
| 行為軌只產 patch artifact、不 publish | 機制存在 | `knowledge-pipeline/refinery/refinery/apply_behavior.py:6`、`:16` | 存在（只吃 `status='approved'`） |
| pipeline 汲取只進 draft | 機制存在 | `api/services/skill_service.py:450-453`、`:476-485` | 存在 |
| 發佈端點限 admin | 機制存在 | `api/routers/skills_v2.py:146-152`、`:6-9` | 存在（`FULL_ACCESS_ROLES`） |
| 發佈驗證閘 | 機制存在 | `api/services/skill_service.py:355`、`:91-105`、`:126-140` | 存在（frontmatter/大小/路徑衝突） |
| revision 表 append-only（NFR-PUB-002） | 機制存在 | `SQL/migrations/106-skill-revisions.sql:27-56` | 存在（狀態轉 `retired`，無刪除） |
| 無 skill 刪除端點 | 機制存在 | `api/routers/skills_v2.py` | 存在（`router.delete` 零命中） |
| merge 汲取嚴格加性 | 機制存在 | `api/services/skill_service.py:463-471` | 存在（`{**baseline, **files}`） |
| 檔案層 append-only | 機制存在 | `api/services/skill_service.py:293-299`、`agent/lockcore/agent/skill_sync.py:155-171` | **不成立**（draft 整體覆蓋 + 物化全量重建） |
| references 同源 gate 腳本（NFR-PUB-003） | 機制存在 | `scripts/ci/references-provenance-check.py:60-84` | 腳本存在 |
| corpus bronze provenance gate | 機制存在 | `knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:1-11` | 腳本存在 |
| 同源 gate 接上 CI | 機制存在 | `.github/workflows/` | **零命中**（無 job 呼叫兩支腳本） |
| RAG 查詢 default deny（NFR-PUB-004） | 機制存在 | `agent/rag/rag/store.py:29-33` | 存在（無 tenant 直接 raise） |
| RAG 檢索 SQL 帶 tenant | 機制存在 | `agent/rag/rag/store.py:89`、`:120` | 存在（兩支皆有 `WHERE tenant_id = %s`） |
| corpus 寫入帶 tenant | 機制存在 | `agent/rag/rag/store.py:43`、`:53` | 存在（`ON CONFLICT (tenant_id, chunk_id)`） |
| 灌注帶 tenant（refinery） | 機制存在 | `knowledge-pipeline/refinery/refinery/publisher.py:33-47` | 存在（`INSERT ... (tenant_id, ...)`） |
| skill 端點 tenant 取自 JWT | 機制存在 | `api/routers/skills_v2.py:78`、`:93`、`:109`、`:129`、`:154`、`:177` | 存在（無 path tenantId） |
| 內部汲取端點 tenant scope | 機制存在 | `api/routers/skills_v2.py:196-199` | 存在（`assert_tenant_scope`） |
| refinery 模組授權 | 機制存在 | `knowledge-pipeline/refinery/refinery/entitlement.py:25-56` | 存在（License 檢查） |
| 實際 fixture 跑通四條負向 | 執行期 | — | **無法靜態判定** |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 汲取管線 | intake 產 draft | `KnowledgeDraftCreated` | 只進 draft | `knowledge-pipeline/refinery/refinery/intake.py:5` | 已有「活的」draft 即跳過 |
| 未核可者 | 直接 publish | `PublishRejected` | 未核可零落地 | `knowledge-pipeline/refinery/refinery/review.py:75-84` | `rowcount == 0` → `INVALID_TRANSITION`（409） |
| Reviewer | approve draft | `KnowledgeApproved` + `CaseEntryPublished` | 先轉移再落地 | `knowledge-pipeline/refinery/refinery/review.py:87-105` | 同交易；落地失敗全回滾 |
| Reviewer | reject / re_refine | `KnowledgeRejected` | 留 audit | `knowledge-pipeline/refinery/refinery/review.py:108-119` | 狀態轉移 + `review_comment` + `reviewed_by` |
| pipeline | 汲取 skill | `SkillDraftIngested` | 絕不 publish | `api/services/skill_service.py:450-453` | 落 `source='pipeline_ingest'` 的 draft |
| admin | publish skill | `SkillPublished` | 至多一個 published | `api/services/skill_service.py:324-376`、`SQL/migrations/106:59-62` | 舊版轉 `retired`；partial unique index 硬保證 |
| 品牌使用者 | 刪除既有 skill | `DeleteRejected` | append-only | `api/routers/skills_v2.py` | **找不到**：無 DELETE 端點 |
| CI | 同源檢查 | `ProvenanceGateFailed` | 失敗即阻擋 | `scripts/ci/references-provenance-check.py:73-79` | 腳本 `return 1`；**無 workflow 呼叫** |
| tenant A | 查 tenant B 語料 | `CrossTenantDenied` | default deny | `agent/rag/rag/store.py:29-33`、`:89` | 無 `RAG_TENANT_ID` 直接 raise；SQL 綁單一 tid |

---

## 逐層走查

### 第 1 層 — 未核可零落地（refinery 事實軌）

`knowledge-pipeline/refinery/refinery/review.py:1-8`

```python
"""審核層 — draft 讀取與狀態轉移(15_SDS §9.2 狀態機/CR-0140)。

轉移(僅 pending_review 可動作;HITL 硬 gate:approve 時才呼叫 Publisher):
  pending_review → approved(事實軌落 case_entries;行為軌產 patch artifact)
                 → rejected(留 audit)
                 → re_refine(2.3.1 intake 重撿,舊 draft 屆時標 superseded)
"""
```

樂觀鎖轉移，`knowledge-pipeline/refinery/refinery/review.py:66-84`

```python
def _transition(conn: psycopg.Connection, tenant: str, draft_id: int, *,
                to_status: str, reviewer_id: str, comment: str | None) -> None:
    """pending_review → to_status(樂觀鎖:WHERE status='pending_review')。不 commit。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE knowledge_drafts
            SET status = %s, review_comment = %s, reviewed_by = %s::uuid,
                reviewed_at = %s, updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status = 'pending_review'
            """,
            ...
        )
        if cur.rowcount == 0:
            raise ReviewError(
                "INVALID_TRANSITION",
                f"draft {draft_id} 非 pending_review,不可轉 {to_status}",
            )
```

唯一的落地入口，`knowledge-pipeline/refinery/refinery/review.py:87-105`

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
        case_id = publisher.publish_case_entry(
            conn, tenant, draft,
            reviewer_id=reviewer_id, embed_fn=embed_fn, embed_model_name=embed_model_name,
        )
        published = {"kind": "case_entry", "case_entry_id": case_id,
                     "embedding_model": embed_model_name}
    else:
        published = {"kind": "behavior_patch", **publisher.behavior_patch_artifact(draft)}
    publisher.record_publish_result(conn, tenant, draft_id, published)
    conn.commit()
    return published
```

`grep -n "publish_case_entry" knowledge-pipeline/refinery/` 的呼叫點只有 `review.py:96`。

`knowledge-pipeline/refinery/refinery/__init__.py:9`

```
  - HITL 硬 gate：本套件**只產 draft，絕不寫入** pgvector 語料或 skill（落地屬 2.3.2 Publisher）
```

行為軌，`knowledge-pipeline/refinery/refinery/apply_behavior.py:6`、`:16-17`

```
     免重佈、免 repo checkout。**只進 draft，絕不 publish → 對 agent 回答品質零影響，
...
  - 只處理 status='approved' 且 provenance.published.kind='behavior_patch' 且未 applied 的 draft
  - 落地後標 provenance.published.applied=true（A 路徑記 skill/version，B 路徑記檔路徑）
```

`knowledge-pipeline/refinery/refinery/apply_behavior.py:99-102` 的 SQL 條件

```sql
            WHERE tenant_id = %s AND draft_type = 'behavior' AND status = 'approved'
              AND provenance->'published'->>'kind' = 'behavior_patch'
              AND COALESCE((provenance->'published'->>'applied')::boolean, FALSE) = FALSE
```

### 第 2 層 — 未核可零落地（skill 軌）

自動汲取通道，`api/services/skill_service.py:443-485`

```python
async def ingest_revision(
    ...
) -> dict:
    """knowledge-pipeline 自動汲取通道（HD-2=a：一律進 draft，人工發佈——絕不 publish，
    故對 agent 回答品質零影響，須人工審核發佈後才生效）。
    ...
    """
    ...
    return await save_draft(
        tenant_id=tenant_id,
        skill_name=skill_name,
        files=files,
        note=note or "pipeline 自動汲取",
        actor_user_id=None,
        actor_role="pipeline",
        source="pipeline_ingest",
    )
```

發佈端點的角色閘，`api/routers/skills_v2.py:5-9`

```
角色閘（HD-5=a）：
  編輯（listSkills/getSkill/saveSkillDraft/listRevisions）＝ OPS_ROLES
  發佈（publishSkill/rollbackSkill）＝ admin（FULL_ACCESS_ROLES）
  自動汲取（ingestSkillRevision）＝ INTERNAL_API_TOKEN（knowledge-pipeline 用）
```

`api/routers/skills_v2.py:146-152`

```python
async def publish_skill(
    body: PublishRequest,
    name: str = Path(),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
```

發佈驗證閘（在交易內，失敗自動 rollback），`api/services/skill_service.py:355`

```python
            validate_publishable(skill_name, files)  # 發佈閘（在交易內，失敗自動 rollback）
```

閘的內容：SKILL.md 存在且 ≤ 16KB（`api/services/skill_service.py:49-51`、`:98-105`）、frontmatter 必含 `name` / `description` 且 YAML 可解析（`:126-140`）、路徑不得為祖先/後代衝突（`:107-124`）、`skill_name` kebab-case（`:53-55`、`:70-77`）、`rel_path` 無 traversal（`:80-89`）。

### 第 3 層 — append-only（revision 層）

`SQL/migrations/106-skill-revisions.sql:12-15`

```
--   把 skill SSOT 從 image 改為「品牌庫 DB → agent workspace overlay 物化同步」。
--   1. saas.skill_revision — 版本快照（append-only 版控）；files jsonb = {rel_path: content}。
--   2. saas.skill_bundle   — 每租戶目前發佈版本 stamp（SkillSync 只輪詢這張做變更偵測）。
--   3. saas.skill_audit_log — 編輯/發佈/回滾審計（比照 saas.kb_audit_log）。
```

`SQL/migrations/106-skill-revisions.sql:44-46`

```sql
    -- 生命週期：draft（草稿）→ published（生效中）→ retired（曾發佈、被新版取代）
    status          text        NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'published', 'retired')),
```

`SQL/migrations/106-skill-revisions.sql:59-62`

```sql
-- 至多一個 published/(tenant,skill)——發佈流程的核心不變式（硬保證，非靠 app 邏輯）
CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_revision_published
    ON saas.skill_revision (tenant_id, skill_name)
    WHERE status = 'published';
```

發佈時舊版轉 `retired` 而非刪除，`api/services/skill_service.py:357-366`

```python
            # 先 retire 當前 published，避免撞 partial unique index
            await db_module._conn.execute(
                "UPDATE saas.skill_revision SET status = 'retired' "
                "WHERE tenant_id = %s::uuid AND skill_name = %s AND status = 'published'",
                (tenant_id, skill_name),
            )
```

回滾即把舊 version 重新 published（`api/services/skill_service.py:378-381`）。

端點層無刪除：`grep -rn "delete" api/routers/skills_v2.py` 無輸出；`api/routers/skills_v2.py` 的路由僅 `@router.get` ×3、`@router.put` ×1、`@router.post` ×3。`api/services/skill_service.py` 中無 `DELETE FROM` 語句。

merge 汲取的加性保證，`api/services/skill_service.py:454-471`

```python
    merge=True（refinery 行為軌用）：只送新增/更新的檔（如單一 refined reference），
    後端讀現有基準（草稿>發佈>最新）併入後存草稿——**嚴格加性**，保留既有 SKILL.md 與
    所有 references，只新增，不刪改，確保發佈後 skill 為既有內容的超集。
    """
    ...
    if merge:
        baseline = await _current_baseline_files(tenant_id, skill_name)
        ...
        files = {**baseline, **files}  # 新檔覆蓋/新增，其餘一律保留（加性）
```

### 第 4 層 — 檔案層不是 append-only

`save_draft` 的更新語句，`api/services/skill_service.py:293-299`

```python
                await db_module._conn.execute(
                    "UPDATE saas.skill_revision "
                    "SET files = %s::jsonb, note = %s, source = %s, created_at = NOW(), "
                    "    created_by = %s::uuid "
                    "WHERE tenant_id = %s::uuid AND skill_name = %s AND version = %s",
                    (files_json, note, source, actor_user_id, tenant_id, skill_name, version),
                )
```

該語句以呼叫端傳入的 `files` 整體覆蓋既有 jsonb（`merge=False` 的一般後台編輯路徑不做 baseline 併入，`:265-280` 僅驗 `rel_path` 與內容型別）。

物化端為全量重建，`agent/lockcore/agent/skill_sync.py:155-171`

```python
    def _materialize(self, skills: dict[str, dict]) -> None:
        self._version_seq += 1
        version_dir = self.workspace / f".skills-v{self._version_seq}"
        if version_dir.exists():
            shutil.rmtree(version_dir, ignore_errors=True)
        version_dir.mkdir(parents=True, exist_ok=True)
        ...
        # 原子重指：symlink swap（os.replace 對 symlink 於 POSIX 為原子操作）
        self._atomic_symlink(version_dir, self._skills_link)
        self._gc_old_versions(keep=version_dir.name)
```

`agent/lockcore/agent/skill_sync.py:1-5` 說明 overlay 語意：

```
"""SkillSync —— 品牌庫 skill 物化到 workspace overlay（CR-0167 / LiveSkill）。

把 saas.skill_revision 的 published 版本拉下來、落盤到 ``workspace/skills/``，
SkillsLoader 的 overlay 機制（skills.py:_skill_entries_from_dir，workspace 優先於
builtin）即讓 agent 下一 turn 用到新知識——**不重佈**。
```

TC 步驟寫「刪除既有 skill」→ 判定基準「更新 append-only」（NFR-PUB-002 原文為「skill 更新只增不刪；git 可完整回溯每次落地」，`smartlock-docs/enterprise/05_NFR.md:177`）／程式碼中 append-only 保證落在 **revision 列**（舊版 `retired` 保留、無 DELETE 端點），檔案層的 `files` jsonb 由 `save_draft` 整體覆蓋、workspace 物化為全量重建。另 NFR-PUB-002 寫「git 可完整回溯每次落地」，而現行 SSOT 為 `saas.skill_revision`（DB）非 git（`SQL/migrations/106-skill-revisions.sql:8-11` 記載此變更）。此處僅並陳，不裁定。

`SQL/migrations/106-skill-revisions.sql:64-70` 另有 `uq_skill_revision_draft`（至多一個 draft/(tenant,skill)），`api/services/skill_service.py:284-292` 以 advisory lock 序列化 check-then-insert。

### 第 5 層 — 同源檢查

references 側，`scripts/ci/references-provenance-check.py:1-17`

```python
"""FR-REF-04：references 側 bronze provenance gate（雙路一致性的 references 半邊）。

背景：知識雙路（ADR-030）——事實走 pgvector corpus、行為/知識走 skill references。
corpus 側 bronze provenance 已由 `pipeline/silver_to_knowledge/audit_corpus.py` 稽核
（bronze_path + sha256 + facts 不含 gdrive）。本腳本補 **references 側** 的同源 gate。

檢查（任一違規 exit 1，可入 CI）：
  1. 結構完整：每個型號 reference 有 frontmatter brand / model / description。
  2. 來源一致：frontmatter brand 與所在品牌目錄一致（防錯置）。
```

失敗行為，`scripts/ci/references-provenance-check.py:72-79`

```python
    if violations:
        print(f"❌ references provenance gate 失敗（{len(violations)} 項）：")
        for v in violations[:30]:
            print(f"  - {v}")
        if len(violations) > 30:
            print(f"  ...（其餘 {len(violations) - 30} 項省略）")
        return 1
```

corpus 側，`knowledge-pipeline/pipeline/silver_to_knowledge/audit_corpus.py:1-11`

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

CI 接線：

```
grep -rn "references-provenance-check\|audit_corpus" .github/ Makefile scripts/
scripts/ci/references-provenance-check.py:4    （檔內註解）
scripts/ci/references-provenance-check.py:15   （檔內註解）
scripts/ci/references-provenance-check.py:17   （檔內註解，用法說明）
scripts/ci/references-provenance-check.py:81   （檔內輸出字串）
```

`.github/workflows/` 中零命中。兩支腳本的 docstring 均寫「可入 CI」，`scripts/ci/references-provenance-check.py:17` 的用法為手動 `uv run python scripts/ci/references-provenance-check.py`。

`smartlock-docs/enterprise/05_NFR.md:178`（NFR-PUB-003）驗證方式欄為「CI job」，`:282` 記載「✅ 2026-07-21 已落地：`scripts/ci/references-provenance-check.py`（references 側）+ `audit_corpus.py`（corpus 側 bronze provenance）＝兩路都有 gate」。TC 判定基準為「同源檢查失敗即阻擋」／`.github/workflows/` 中無呼叫這兩支腳本的 job。此處僅並陳，不裁定。

`scripts/ci/references-provenance-check.py:11-15` 另說明 gate 不擋 GDrive URL 引用：

```
註（sourcing rule，CLAUDE.md）：references 內容源自 bronze（YouTube/website/video）；
GDrive/PDF **只引 URL 不抄內容**——「引 URL」為允許（指標），故本 gate **不**擋 GDrive URL
引用（那是合法指標），只驗結構與 brand 對齊。references 無機讀 bronze provenance metadata
（內容鎖定、人工由 bronze 策展），故「源自 bronze」在 references 側靠 authoring 紀律 +
本結構 gate；corpus 側的完整 bronze provenance（bronze_path+sha256）由 audit_corpus.py 稽核。
```

### 第 6 層 — 跨租戶 default deny

RAG 檢索層，`agent/rag/rag/store.py:1-8`

```python
"""pgvector 存取層 — upsert 與 cosine 檢索。

治理（ADR-010）：
  - 每條查詢 WHERE 必帶 tenant_id（default deny：無 tenant 直接拒絕）
  - manual 檢索帶品牌/型號 gating（brand/model 相符或 'general' 通用列）
  - case 檢索閾值 similarity ≥ 0.85、排除 is_active=false / deleted_at 非空
"""
```

`agent/rag/rag/store.py:29-34`

```python
def tenant_id() -> str:
    """default deny：tenant 未設定即拒絕服務，不退回任何『全庫』查詢。"""
    tid = os.getenv("RAG_TENANT_ID")
    if not tid:
        raise RuntimeError("需要 RAG_TENANT_ID（ADR-010：查詢必帶 tenant，default deny）")
    return str(uuid.UUID(tid))  # 驗格式
```

`agent/rag/rag/store.py:82-92`（`search_manual`）

```python
    tid = tenant_id()
    with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_id, brand, model, category, content, source_type, source,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM rag_manual_chunks
            WHERE tenant_id = %s
              AND is_active
```

`agent/rag/rag/store.py:112-122`（`search_cases`）為同型（`WHERE tenant_id = %s AND embedding IS NOT NULL AND is_active AND deleted_at IS NULL ...`）。

寫入端，`agent/rag/rag/store.py:41-53`

```python
def upsert_manual_chunks(rows: list[dict], *, embed_model: str) -> int:
    """冪等 upsert（ON CONFLICT (tenant_id, chunk_id)）。rows 需含 embedding。"""
    tid = tenant_id()
    ...
                ON CONFLICT (tenant_id, chunk_id) DO UPDATE SET
```

`agent/rag/rag/server.py:8` 記載同一條治理原則（「查詢必帶 tenant_id（RAG_TENANT_ID env；default deny）」），`:80` 於啟動時呼叫 `store.tenant_id()`（未設即在啟動階段 raise）。

灌注端（refinery Publisher），`knowledge-pipeline/refinery/refinery/publisher.py:33-47`

```python
        cur.execute(
            """
            INSERT INTO case_entries
                (tenant_id, title, problem_description, solution, brand, model,
                 source, approved_by, verified, is_active,
                 embedding, embedding_model, embedding_status, source_problem_card_id)
            VALUES (%s, %s, %s, %s, %s, %s,
                    'refinery', %s::uuid, TRUE, TRUE,
                    %s::vector, %s, 'ready', %s::uuid)
```

refinery 的 draft 讀寫皆以 `WHERE tenant_id = %s` 限縮（`review.py:43`、`:59`、`:77`；`apply_behavior.py:100`、`:175`；`intake.py:28`）。

skill 端點的 tenant 來源，`api/routers/skills_v2.py:75-79`

```python
async def list_skills(
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    result = await skill_service.list_skills(tenant_id=user.tenant_id)
```

其餘五個端點同型（`:93`、`:109`、`:129`、`:154`、`:177` 皆為 `tenant_id=user.tenant_id`），路徑參數只有 `{name}`，無 `tenantId`。內部汲取端點的 tenant 由 body 帶入但受服務憑證範圍檢查，`api/routers/skills_v2.py:193-201`

```python
async def ingest_skill_revision(
    body: IngestRequest,
    auth: ServicePrincipalContext = Depends(
        service_credential_required("skills:write")
    ),
) -> dict:
    assert_tenant_scope(auth, body.tenant_id)
```

`skill_service` 內所有 SQL 皆帶 `WHERE tenant_id = %s::uuid`（`:159-256`、`:288-306`、`:344-370`、`:387-412`、`:428-440`、`:481-489`、`:493-520`）。

模組授權，`knowledge-pipeline/refinery/refinery/entitlement.py:52-56`

```python
def assert_refinery_entitled(tenant_id: str) -> None:
    ...
    if not is_refinery_entitled(tenant_id):
        ...
            f"租戶 {tenant_id} 未開通 refinery 模組或 License 已過期"
```

### 第 7 層 — SkillSync 的二次防禦

`agent/lockcore/agent/skill_sync.py:141-151`

```python
    async def _fetch_published_skills(self) -> dict[str, dict]:
        """{ skill_name: {rel_path: content} }（僅 status='published'）。"""
        ...
                "WHERE tenant_id = %s::uuid AND status = 'published'",
```

`agent/lockcore/agent/skill_sync.py:173-197`

```python
    # skill_name 二次防禦：service 端已驗，但 DB 讀回來也不盡信（CR-0167 review finding 3）
    _SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")

    def _write_skill(self, version_dir: Path, skill_name: str, files: dict) -> None:
        """落盤單一 skill。二次防禦：service 端已驗，此處再擋 skill_name 與 rel_path traversal。"""
        if not self._SKILL_NAME_RE.match(skill_name or ""):
            logger.warning("SkillSync 略過非法 skill 名稱 %r", skill_name)
            return
        ...
            try:
                target.resolve().relative_to(version_root_resolved)
            except (ValueError, OSError):
                logger.warning("SkillSync 略過越界路徑 %r（skill=%s）", rel_path, skill_name)
                continue
```

`agent/lockcore/agent/skill_sync.py:104-113`：`stamp is None`（該租戶尚未發佈）或 `skills` 為空時「不動 overlay / 保留現況」。

---

## 既有測試證據

本次於本機 Docker 測試庫實跑（Windows 需 `-p winloop_plugin`）：

```
cd api && python -m pytest tests/test_skills_v2_endpoint.py -q -p winloop_plugin
13 passed, 3 skipped in 5.84s

cd agent && python -m pytest tests/test_skill_sync.py -q -p winloop_plugin
5 failed, 3 passed, 2 skipped in 3.71s
```

`test_skill_sync.py` 的 5 個失敗皆為同一個 Windows 環境限制，錯誤為 `OSError: [WinError 1314] 用戶端沒有這項特殊權限。` 發生於 `agent/lockcore/agent/skill_sync.py:210` 的 `os.symlink`（建立符號連結需 Windows 的 SeCreateSymbolicLinkPrivilege）。失敗清單：

```
FAILED tests/test_skill_sync.py::test_materialize_overlays_builtin
FAILED tests/test_skill_sync.py::test_atomic_reswap_updates_content
FAILED tests/test_skill_sync.py::test_materialize_rejects_path_traversal
FAILED tests/test_skill_sync.py::test_materialize_rejects_skill_name_traversal
FAILED tests/test_skill_sync.py::test_materialize_bad_skill_does_not_wedge_others
```

三個 traversal 相關測試在 symlink 步驟之前的守線分支**已實際觸發**，pytest 擷取到的 log 為：

```
WARNING  lockcore.skill_sync:skill_sync.py:186 SkillSync 略過非法路徑 '../escape.md'（skill=evil）
WARNING  lockcore.skill_sync:skill_sync.py:180 SkillSync 略過非法 skill 名稱 '../evil'
WARNING  lockcore.skill_sync:skill_sync.py:168 SkillSync 略過物化失敗的 skill=bad
```

`knowledge-pipeline/refinery/tests/` 由 `.github/workflows/component-nightly.yml:101` 在 nightly 執行；本次未於本機跑該套件（需 refinery 的獨立依賴環境）。

---

## 事實結論

1. refinery 的 `approve()` 是 Publisher 的唯一呼叫點，且先以樂觀鎖 `WHERE status='pending_review'` 佔位、同交易落地、末尾才 `commit()`（`knowledge-pipeline/refinery/refinery/review.py:87-105`）；非 `pending_review` 的 draft 轉態直接 raise `INVALID_TRANSITION`（`:80-84`）。
2. `knowledge-pipeline/refinery/refinery/__init__.py:9` 明載本套件「只產 draft，絕不寫入 pgvector 語料或 skill」；行為軌 `apply_behavior.py:100-102` 的 SQL 只吃 `status='approved'` 且未 applied 的列。
3. skill 自動汲取一律進 draft（`api/services/skill_service.py:450-453`、`:476-485`）；發佈與回滾端點限 `FULL_ACCESS_ROLES`（`api/routers/skills_v2.py:152`、`:174`），編輯限 `OPS_ROLES`。
4. 發佈前有驗證閘（SKILL.md 存在且 ≤16KB、frontmatter `name`/`description`、路徑衝突、skill_name kebab-case、rel_path 無 traversal），在交易內執行、失敗自動 rollback（`api/services/skill_service.py:355`）。
5. revision 層 append-only：`status` 為 `draft/published/retired` 三態、發佈時舊版轉 `retired`、partial unique index 保證至多一個 published；`api/routers/skills_v2.py` 無 DELETE 端點，`api/services/skill_service.py` 無 `DELETE FROM`。
6. 檔案層非 append-only：`save_draft` 以 `SET files = %s::jsonb` 整體覆蓋（`api/services/skill_service.py:293-299`），SkillSync 物化為版本目錄全量重建 + symlink 換裝（`agent/lockcore/agent/skill_sync.py:155-171`）。`ingest_revision(merge=True)` 才是嚴格加性。
7. NFR-PUB-002 寫「git 可完整回溯每次落地」，而現行 skill SSOT 為 `saas.skill_revision`（DB），`SQL/migrations/106-skill-revisions.sql:8-11` 記載此變更成因。
8. 同源檢查有兩支腳本（references 側與 corpus 側），失敗皆 `exit 1`；但 `.github/workflows/` 中無任何 job 呼叫，`grep` 零命中。
9. RAG 跨租戶 default deny 完整：`tenant_id()` 無 env 即 raise（`agent/rag/rag/store.py:29-33`），`search_manual` / `search_cases` / `upsert_manual_chunks` 三支 SQL 皆綁單一 tid。
10. skill 端點的 `tenant_id` 一律取自 JWT（`user.tenant_id`），路徑無 `tenantId` 參數；內部汲取端點以 `assert_tenant_scope(auth, body.tenant_id)` 限縮（`api/routers/skills_v2.py:199`）。
11. refinery 的 draft 讀寫全部 `WHERE tenant_id = %s`；另有 License 模組授權檢查（`knowledge-pipeline/refinery/refinery/entitlement.py:52-56`）。
12. SkillSync 有 skill_name 與 rel_path 的二次防禦，並以 `version_dir` 為信任根做越界檢查（`agent/lockcore/agent/skill_sync.py:173-197`）。
13. 本機執行 `agent/tests/test_skill_sync.py` 的 5 個失敗皆為 Windows `os.symlink` 權限限制（WinError 1314），非程式邏輯；其中三個 traversal 守線分支在失敗前已實際觸發並輸出 WARNING。
14. 「四條負向 fixture（未核可 publish／刪除既有 skill／來源不同步／tenant A 查 B）的實際執行結果」需執行期，本次未取得。
