# TC-PLT-CFG-01 — Agent Configuration Studio：發佈、保護層、SLO 失敗、rollback

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 config M18 與 skill 版控測試（見步驟 7） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/services/config_m18_service.py`、`api/routers/config_m18.py`、`api/services/skill_service.py`、`api/routers/skills_v2.py`、`api/realtime/config_canary_advance_cron.py`、`SQL/migrations/004-config-m18.sql`、`SQL/migrations/103-config-namespace-owner-protected.sql`、`agent/lockcore/skills/locksmith-product-knowledge/SKILL.md`、`agent/scripts/run_forbidden_gate.py`、`.github/workflows/forbidden-eval-gate.yml` |
| 優先級 / 路徑類型 | P1 / failure＋recovery |
| 事實結論 | 四項判定要素中三項有落點：**保護層**有機制（`config_m18_service.py:168-173` 的 `CONFIG_PROTECTED_OVERRIDE` 403），但受保護的 namespace 目前**只有 `payment_gate` 一個**（`SQL/migrations/103-config-namespace-owner-protected.sql:37-40`）——TC 指名的 `domain-safety` 不是 config namespace，它是 skill 內的一段 Markdown（`agent/lockcore/skills/locksmith-product-knowledge/SKILL.md:56`），而 skill 發佈閘（`skill_service.py:82-104`）只驗 frontmatter／大小／路徑，不保護任何內容段落；**rollback** 完整（`config_m18_service.py:574-666` 重啟 parent version、`skill_service.py:378-425` 重新 published）；**audit** 完整且 append-only（`config_m18_service.py:192-214`、`skill_service.py:493-522`）；**SLO 失敗停止擴散**只回決策不執行——`check_slo_halt` 的 docstring 自述「本函式只回 decision，不真實 halt」（`config_m18_service.py:985-986`）。另：TC 前置的 canary tenant 在程式碼中為 canary **stage**（`5%/50%/100%`，`SQL/migrations/004-config-m18.sql:91`），非 per-tenant canary。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：可變更 skill/config 版本、保護層、canary tenant
- 步驟：發佈新版、嘗試覆寫 domain-safety、製造 eval/SLO 失敗，再 rollback
- 預期結果（判定基準）：保護層不可覆寫；失敗時停止擴散並回上一版；版本、審核、測試與 rollback 全留 audit
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P1
- 驗證需求：FR-PLT-08｜屬於旅程腳本：SC-18

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 發佈 config 新版 | `api/services/config_m18_service.py:334`（draft）、`:391`（start_rollout） | 有 |
| 發佈 skill 新版 | `api/services/skill_service.py:324-375` | 有 |
| 保護層不可覆寫（config namespace） | `api/services/config_m18_service.py:168-173` | 有（僅 `payment_gate` 標 `is_protected`） |
| 保護層不可覆寫（skill domain-safety 段） | — | **找不到**：skill 發佈閘不檢查內容段落 |
| eval 失敗擋發佈 | `agent/scripts/run_forbidden_gate.py:98`、`.github/workflows/forbidden-eval-gate.yml` | 有（CI 層，與 config/skill 發佈端點不連動） |
| SLO 失敗停止擴散 | `api/services/config_m18_service.py:973-1094` | 部分：只回 `should_halt` 決策，不停 rollout |
| rollback 回上一版（config） | `api/services/config_m18_service.py:574-666` | 有 |
| rollback 回上一版（skill） | `api/services/skill_service.py:378-425` | 有 |
| 版本／審核／測試／rollback 全留 audit | `config_m18_service.py:192-214`、`skill_service.py:493-522` | 部分：config/skill 各自有 audit；「測試（eval）」結果不入 audit 表 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 租戶 Admin | 發佈 skill 新版 | `SkillPublished` | 發佈閘 | `api/services/skill_service.py:337-375` | 交易內 `validate_publishable` → retire 舊 published → publish 目標 → bump stamp |
| 租戶 Admin | 覆寫受保護 config namespace | `RequestRejected(403)` | 受保護層 | `api/services/config_m18_service.py:168-173` | `CONFIG_PROTECTED_OVERRIDE` 403（僅當 `is_protected` 且 `tenant_id` 非 NULL） |
| 租戶 Admin | 覆寫 skill 內 domain-safety 段落 | `RequestRejected` | 受保護層 | `api/services/skill_service.py:82-104` | **無此判定**：只驗 SKILL.md 存在、≤16KB、frontmatter 有 name/description、路徑合法 |
| 非 owner 角色 | 改 config | `RequestRejected(403)` | owner 治理 | `api/services/config_m18_service.py:174-189` | `CONFIG_OWNER_ROLE_REQUIRED` 403；admin 恆 bypass（`:146`、`:174-175`） |
| Admin | 送 SLO 觀測值 | `RolloutHalted` | 失敗停止擴散 | `api/services/config_m18_service.py:1062-1067` | 只回 `should_halt` + `recommendation` 字串，rollout stage 不變 |
| Admin | rollback | `ConfigRolledBack` | 回上一版 | `api/services/config_m18_service.py:622-656` | rollout→`rolled_back`、version→`rolled_back`、parent version 重設 `active`、寫 audit |
| 系統 | 記錄變更 | `ConfigAudited` | append-only | `api/services/config_m18_service.py:192-214` | `INSERT INTO saas.config_audit`（無 UPDATE/DELETE 路徑） |

---

## 逐層走查

### 步驟 1 — 受保護層的判定邏輯與作用範圍

`api/services/config_m18_service.py:149-189`

```python
async def _assert_namespace_writable(
    namespace: str, *, actor_role: str | None, tenant_id: str | None
) -> None:
    """CR-0166 R1-6（受保護層）＋R1-7（owner 治理）統一寫入 gate。

    - is_protected 且租戶層 override（tenant_id 非 NULL）→ 403 CONFIG_PROTECTED_OVERRIDE。
    ...
    """
    cur = await db_module._conn.execute(
        "SELECT is_protected, owner_role_codes FROM saas.config_namespace WHERE code = %s",
        (namespace,),
    )
    ...
    if is_protected and tenant_id is not None:
        raise ApiError(
            "CONFIG_PROTECTED_OVERRIDE",
            f"namespace '{namespace}' 為受保護配置，租戶層不可覆寫（僅平台級可改）",
            403,
        )
```

實際被標為受保護的 namespace，`SQL/migrations/103-config-namespace-owner-protected.sql:36-40`：

```sql
-- 平台閘門：payment_gate 鎖 admin-only（owner 空集合）＋受保護（租戶不可 override）
UPDATE saas.config_namespace
SET is_protected = true
WHERE code = 'payment_gate';
```

`is_protected` 欄預設為 false（`:20-21`），其餘 namespace 未被設為 true。

### 步驟 2 — TC 指名的 `domain-safety` 在程式碼中的位置

```
git grep -rni "domain.safety|domain_safety" -- api/ agent/ web/ SQL/
agent/lockcore/skills/locksmith-product-knowledge/SKILL.md:33:All domain safety rules below apply **unchanged** regardless of which lookup path was used.
agent/lockcore/skills/locksmith-product-knowledge/SKILL.md:56:## Domain safety rules (do not violate)
```

`domain-safety` 不是 `saas.config_namespace` 的一個 code（`SQL/migrations/004-config-m18.sql:128` 起的 seed 與後續 044/047/051/053/054/055 各 migration 的 namespace 清單皆無此 code），而是 builtin skill 的 Markdown 章節標題。

### 步驟 3 — skill 發佈閘檢查了什麼

`api/services/skill_service.py:82-104`

```python
def validate_publishable(skill_name: str, files: dict) -> None:
    """發佈閘：publish / rollback 前強制。draft 暫存不跑此閘（可存半成品）。"""
    validate_skill_name(skill_name)
    if not isinstance(files, dict) or not files:
        raise ApiError("EMPTY_SKILL", "skill 內容為空", 422)

    for rel_path, content in files.items():
        _validate_rel_path(rel_path)
        if not isinstance(content, str):
            raise ApiError("INVALID_FILE_CONTENT", f"檔案內容須為字串：{rel_path!r}", 422)

    _reject_path_collisions(files)

    skill_md = files.get("SKILL.md")
    if skill_md is None:
        raise ApiError("MISSING_SKILL_MD", "缺 SKILL.md（skill 進入點）", 422)
    if len(skill_md.encode("utf-8")) > _SKILL_MD_MAX_BYTES:
        raise ApiError(
            "SKILL_MD_TOO_LARGE",
            ...
        )
    _validate_frontmatter(skill_md)
```

四項檢查為：skill 名稱 kebab-case（`:63-69`）、相對路徑無 traversal（`:72-79`）、路徑碰撞（`:107-123`）、frontmatter 具 `name`/`description`（`:126-141`）。**無**任何「必存內容段落」或「不可刪除規則」之檢查。

TC 步驟寫「嘗試覆寫 domain-safety」（出處：② 測試案例主表 TC-PLT-CFG-01 列；SC-18 feature `smartlock-docs/enterprise/bdd/SC-18.feature:27-30` 亦寫「嘗試覆寫受保護層（escalation／domain-safety）→ 阻擋」）／程式碼在 config 層有 `is_protected` 但該旗標未涵蓋 escalation/domain-safety，在 skill 層則無內容層保護。此處僅並陳，不裁定。

### 步驟 4 — SLO 失敗是否停止擴散

`api/services/config_m18_service.py:983-986`

```python
    """SLO halt decision endpoint — admin 觀察 metrics 後請求是否該 halt rollout。

    本函式只回 decision，不真實 halt（halt 動作由 admin 顯式呼 rollback —
    對齊 dispute 負值 resolution 人工 trail 精神，避免自動 trigger 風險）。
```

`api/services/config_m18_service.py:1062-1067`

```python
    should_halt = bool(exceeded)
    recommendation = (
        f"建議：立即呼 rollback endpoint 將 rollout 退回前一版（exceeded: {', '.join(exceeded)}）"
        if should_halt
        else "SLO 通過：rollout 可繼續推進；建議等 next_stage_eta 自動 advance"
    )
```

該函式對 `saas.config_rollout` 只做讀取（`:1031-1040`），無 UPDATE；唯一寫入為 audit（`:1069-1072`）。

canary 自動推進由獨立 cron 執行，`api/realtime/config_canary_advance_cron.py:105-130`——其 `run_once` 掃 `strategy = 'canary_5_50_100'` 的 rollout 並呼 `_advance_canary_stage`，同檔未讀取任何 SLO 判定結果。

### 步驟 5 — rollback 路徑

config：`api/services/config_m18_service.py:619-656`

```python
    if current_stage == "rolled_back":
        raise ApiError("CONFLICT", "rollout 已 rolled_back，無法再次 rollback", 409)

    # Mark rollout as rolled_back
    await db_module._conn.execute(
        "UPDATE saas.config_rollout SET current_stage = 'rolled_back' WHERE id = %s::uuid",
        (rollout_id,),
    )
    ...
    # Re-activate parent_version if exists
    if parent_vid_str:
        ...
            UPDATE saas.config_version
            SET state = 'active', activated_at = %s
            WHERE id = %s::uuid AND state IN ('retired','rolled_back')
    ...
    await _append_audit(
        tenant_id=str(ver_tenant) if ver_tenant else None,
        config_version_id=version_id_str,
        actor_user_id=actor_user_id,
        action="rolled_back",
```

同函式 `:603-614` 另有租戶收斂：

```python
    if ver_tenant is not None and str(ver_tenant) != str(tenant_id):
        logger.warning(
            "cross-tenant config rollback blocked rollout=%s owner=%s caller=%s",
            rollout_id, ver_tenant, tenant_id,
        )
        raise ApiError("CONFIG_NOT_FOUND", f"rollout {rollout_id} 不存在", 404)
```

skill：`api/services/skill_service.py:386-425` 同機制（`validate_publishable` → retire 當前 published → 目標版重設 published → `_bump_stamp`），並於 `:421-424` 寫 `rollback` audit。

### 步驟 6 — audit 落點

config：`api/services/config_m18_service.py:200-214`

```python
    """Append a record to saas.config_audit (append-only)."""
    await db_module._conn.execute(
        """
        INSERT INTO saas.config_audit
            (tenant_id, config_version_id, actor_user_id, action, diff)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb)
        """,
```

skill：`api/services/skill_service.py:503-522`

```python
    """best-effort：audit 失敗不阻擋主操作（比照 kb_v2._write_audit_log）。"""
    try:
        await db_module._conn.execute(
            "INSERT INTO saas.skill_audit_log "
            ...
    except Exception:  # noqa: BLE001 — best-effort audit 不得反向阻擋已完成的主操作
        logger.warning("skill_audit_log write failed (non-fatal)", exc_info=True)
```

兩者的失敗語意不同：config audit 在同一交易內（`start_rollout`／`rollback` 呼叫鏈），skill audit 為 best-effort 且失敗僅 warning。

eval 結果不入上述任一 audit 表：`agent/scripts/run_forbidden_gate.py:8-10` 自述產物落 `evals/forbidden_run_<ts>.json` 檔案，`.github/workflows/forbidden-eval-gate.yml` 為 CI 工作流，與 `saas.config_audit` / `saas.skill_audit_log` 無連線。

### 步驟 7 — 執行既有測試

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest -p winloop_plugin \
  tests/test_skills_v2_endpoint.py tests/test_escalation_to_draft_pc.py \
  tests/test_internal_ingest.py tests/test_config_m18.py -q
58 passed, 3 skipped in 6.09s
```

---

## 既有測試證據

- `api/tests/test_config_m18.py`、`api/tests/test_skills_v2_endpoint.py`：與其他兩檔合跑 58 passed / 3 skipped（步驟 7）。
- 無對應既有測試涵蓋「覆寫 skill 內 domain-safety 段落應被阻擋」——該行為在程式碼中不存在，故亦無測試。

---

## 觀測到的其他事實

1. **canary 的粒度是 stage 而非 tenant**：`SQL/migrations/004-config-m18.sql:91` 的 `strategy` CHECK 值域為 `('canary_5_50_100','instant')`；同檔 `:151` 註解「canary_5_50_100 auto-advance deferred to Phase II（needs scheduler）」，該 scheduler 後由 `api/realtime/config_canary_advance_cron.py` 補上（`:3` 自述「解凍 `config_m18_service._advance_canary_stage`」）。TC 前置寫「canary tenant」／程式碼為 canary stage。此處僅並陳，不裁定。

2. **`admin` 對 owner 治理恆 bypass**：`api/services/config_m18_service.py:142-146`

```python
# CR-0166 R1-6/R1-7：admin 永遠可寫（全權治理角色；owner_role_codes 語意＝
# 「除 admin 外的授權 owner」）。
_ADMIN_BYPASS_ROLES = frozenset({"admin"})
```

受保護層（`is_protected`）的判定在 admin bypass **之前**（`:168-173` 早於 `:174-175`），故 admin 亦無法做租戶層 override。

3. **skill 發佈與回滾要求 `FULL_ACCESS_ROLES`，讀取與存草稿為 `OPS_ROLES`**：`api/routers/skills_v2.py:151`、`:173`（publish/rollback）與 `:76`、`:91`、`:107`、`:125`（read/save draft）。

4. **eval gate 存在於 CI，不在發佈端點**：`.github/workflows/forbidden-eval-gate.yml`；runner `agent/scripts/run_forbidden_gate.py:11` 自述「退出碼：0=gate 過；1=gate 未過或結構錯（CI 據此 block deploy）」。TC 步驟的「製造 eval 失敗」在程式碼中對應的是 CI 阻擋部署，非 config/skill 發佈 API 的 422/409。此處僅並陳，不裁定。
</content>
