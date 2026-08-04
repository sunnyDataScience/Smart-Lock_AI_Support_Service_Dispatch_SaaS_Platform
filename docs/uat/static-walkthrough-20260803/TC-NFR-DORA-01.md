# TC-NFR-DORA-01 — 可追溯 release、rollback 與四項 DORA 指標

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `.github/workflows/cloud-run-deploy.yml`、`scripts/release/release_manifest.py`、`scripts/release/release-manifest.schema.json`、`scripts/release/rollback-cloud-run.sh`、`scripts/release/record-drill-evidence.py`、`scripts/ci/migration-drift-check.py`、`SQL/migrations/`、`api/services/audit_log_service.py` |
| 優先級 / 路徑類型 | P1 / failure＋recovery |

判定理由：**「可追溯 release」與「rollback 不遺失 migration/audit 證據」的機制存在且相當完整**——release manifest 有 21 個必填欄位含 `release_id` / `commit_sha` / `image_digest` / `revision` / `previous_revision` / `migration_versions` / `migration_evidence` / `rollback` / `created_at`（`scripts/release/release_manifest.py:39-60`、`:113-149`），staging 與 production 各產出並驗證一份、保存 90 天（`.github/workflows/cloud-run-deploy.yml` 的 `staging-evidence` 與 `promote-production` job）；rollback 命令自動由 `previous_revision` 生成且 DB 策略硬約束為 `forward-fix-or-restore; never down-migrate in place`（`scripts/release/release_manifest.py:100-103`、`:141-146`），`SQL/migrations/` 下 126 個檔案中 0 個 down/rollback 腳本；audit 為 append-only sha256 hash chain（`api/services/audit_log_service.py:27-29`）。**但「四項 DORA 指標可計算且來源一致」不成立**：`DORA`／`lead_time`／`change_failure`／`MTTR` 四個識別碼在 `.github/`、`scripts/`、`api/`、`web/` 的程式碼中零命中，只出現在 `smartlock-docs/enterprise/*.md`；repo 中無指標計算腳本、無指標儲存、無 dashboard 定義。另 TC 寫「四項 DORA 指標」而 NFR 只列三項（NFR-DORA-001～003），此差異於下方並陳。

**TC 原文**｜章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）｜前置：staging、變更與 rollback fixture｜步驟：執行可追溯 release、製造失敗並 rollback，收集 DORA 指標｜判定基準：四項 DORA 指標可計算且來源一致；rollback 不遺失 migration/audit 證據｜路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P1｜驗證哪些需求：NFR-DORA-001、NFR-DORA-002、NFR-DORA-003｜旅程：—

---

## 逐條驗收條件對照

| 條件 | 類型 | 程式碼落點 | 狀態 |
|---|---|---|---|
| release 有唯一識別 | 機制存在 | `scripts/release/release_manifest.py:114`、`.github/workflows/cloud-run-deploy.yml`（`--release-id "${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"`） | 存在 |
| release 綁 commit | 機制存在 | `scripts/release/release_manifest.py:118`、`:23`（`SHA_RE`） | 存在（40 位 hex 驗證） |
| release 綁不可變 image digest | 機制存在 | `scripts/release/release_manifest.py:119-120`、`:22`（`DIGEST_RE`） | 存在（`sha256:` + 64 hex） |
| production 不重建、沿用 staging digest | 機制存在 | `.github/workflows/cloud-run-deploy.yml`（`Assert immutable digest from staging`） | 存在 |
| 記錄 previous_revision（可回滾點） | 機制存在 | `scripts/release/release_manifest.py:127` | 存在 |
| rollback 指令自動生成 | 機制存在 | `scripts/release/release_manifest.py:110-114`、`:141-143` | 存在 |
| rollback 不做 DB down migration | 機制存在 | `scripts/release/release_manifest.py:100-103`、`scripts/release/rollback-cloud-run.sh:2` | 存在（字面硬比對） |
| migration 版本清單入 manifest | 機制存在 | `scripts/release/release_manifest.py:31-32`、`:128` | 存在（列 `SQL/migrations/*.sql` 檔名） |
| migration 證據為 durable URL | 機制存在 | `.github/workflows/cloud-run-deploy.yml`（`Durable migration evidence gate`）、`scripts/release/release_manifest.py:24` | 存在（限 `https://` / `gs://`） |
| migration drift 守門 | 機制存在 | `.github/workflows/migration-drift-check.yml:20-32`、`.github/workflows/cloud-run-deploy.yml`（`Migration drift`） | 存在 |
| audit append-only 可回溯 | 機制存在 | `api/services/audit_log_service.py:27-29`、`:60-61` | 存在（sha256 hash chain） |
| manifest 保存期 | 機制存在 | `.github/workflows/cloud-run-deploy.yml`（`retention-days: 90`） | 存在 |
| drill 證據記錄器 | 機制存在 | `scripts/release/record-drill-evidence.py:13-26` | 存在（rollback/forward-fix/restore 三型） |
| Lead time 可計算 | 機制存在 | — | **零命中** |
| Change Failure Rate 可計算 | 機制存在 | — | **零命中** |
| MTTR 可計算 | 機制存在 | — | **零命中** |
| 第四項 DORA 指標（部署頻率） | 機制存在 | — | **零命中**（NFR 亦只列三項） |
| 四項指標來源一致 | 執行期 | — | **無法靜態判定**（前提不成立） |
| 實際 rollback 演練結果 | 執行期 | — | **無法靜態判定** |

---

## Event Storming

本案例為非功能需求，無 domain event。改列機制與落點對照：

| Actor | 動作 | 期待機制 | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|
| 發版者 | 觸發 release | 可追溯 | `.github/workflows/cloud-run-deploy.yml:4-36` | `workflow_dispatch` only，強制輸入 `migration_evidence_url` |
| CI | 契約 gate | 阻擋不合格 | `.github/workflows/cloud-run-deploy.yml`（`contract-gate` job） | 跑 11 條治理/授權測試 + browser token gate + durable evidence gate |
| CI | build once | digest 不可變 | `.github/workflows/cloud-run-deploy.yml`（`Resolve registry digest`） | `[[ "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]` |
| CI | 產 staging manifest | 留證 | `scripts/release/release_manifest.py:107-150` | 21 欄位 + `validate` |
| CI | 晉升 production | 同 digest | `.github/workflows/cloud-run-deploy.yml`（`Assert immutable digest from staging`） | `test "${IMAGE_OVERRIDE#*@}" = "${{ needs.build-once.outputs.image_digest }}"` |
| 維運 | rollback | 切流量、不動 DB | `scripts/release/rollback-cloud-run.sh:20-26` | `gcloud run services update-traffic ... --to-revisions=<rev>=100` |
| 維運 | 記錄演練 | 可稽核 | `scripts/release/record-drill-evidence.py:26` | 拒絕非 `https://`／`gs://` 證據 URL |
| 指標系統 | 計算 DORA | 四指標 | — | **找不到**：repo 中無 DORA 計算實作 |

---

## 逐層走查

### 第 1 層 — release 是否可追溯

`.github/workflows/cloud-run-deploy.yml:1-5`

```yaml
# ADR-038 / WBS 3.6.7：manual release，不接受 branch push 直達 production。
# GitHub Environments 必須由 repo admin 設定：
#   staging    -> staging WIF provider / deploy SA
#   production -> production WIF provider / deploy SA + required reviewer
name: cloud-run-deploy
```

`.github/workflows/cloud-run-deploy.yml:6-8` 觸發器只有 `workflow_dispatch`（無 `push` / `pull_request`）。

`.github/workflows/cloud-run-deploy.yml:30-34`

```yaml
      migration_evidence_url:
        description: "已核准的三庫 migration apply/drift 證據（https:// 或 gs:// durable URL）"
        required: true
        type: string
```

manifest 的必填欄位，`scripts/release/release_manifest.py:39-60`

```python
    required = {
        "schema_version",
        "release_id",
        "environment",
        "component",
        "commit_sha",
        "image",
        "image_digest",
        "resource_kind",
        "resource_name",
        "revision",
        "previous_revision",
        "migration_versions",
        "migration_evidence",
        "config_references",
        "secret_references",
        "health_url",
        "operator",
        "evidence",
        "rollback",
        "observation_window_minutes",
        "created_at",
    }
```

同一組 21 欄位亦為 `scripts/release/release-manifest.schema.json` 的 `required`。

格式驗證常數，`scripts/release/release_manifest.py:22-25`

```python
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]*:[^:]+$")
EVIDENCE_RE = re.compile(r"^(?:https://|gs://).+")
```

`scripts/release/release_manifest.py:1` docstring：「建立/驗證 ADR-038 release manifest（只存 secret reference，不存值）」。

### 第 2 層 — 不可變 digest 與 production 不重建

`.github/workflows/cloud-run-deploy.yml` 的 `build-once` job 內：

```bash
          digest=$(gcloud artifacts docker images describe "${tagged}" --format='value(image_summary.digest)')
          [[ "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]
          echo "image=${tagged%:*}@${digest}" >> "${GITHUB_OUTPUT}"
```

`promote-production` job 的第一個實質步驟：

```bash
      - name: Assert immutable digest from staging
        run: |
          [[ "${IMAGE_OVERRIDE}" == *@sha256:* ]]
          test "${IMAGE_OVERRIDE#*@}" = "${{ needs.build-once.outputs.image_digest }}"
```

`api/tests/test_cr_0190_release_governance.py:48` 的 `test_production_promotes_build_output_digest_without_rebuild` 為此行為的守線測試。

### 第 3 層 — rollback 的定義與 DB 策略

`scripts/release/release_manifest.py:109-114`

```python
    rollback_command = (
        f"scripts/release/rollback-cloud-run.sh {args.resource_name} "
        f"{args.previous_revision}"
        if args.resource_kind == "service"
        else f"gcloud run jobs update {args.resource_name} --image=<previous-digest>"
    )
```

`scripts/release/release_manifest.py:141-146`

```python
        "rollback": {
            "command": rollback_command,
            "database_strategy": (
                "forward-fix-or-restore; never down-migrate in place"
            ),
        },
```

驗證器對此字串做**字面等值比對**，`scripts/release/release_manifest.py:97-103`

```python
    rollback = data.get("rollback", {})
    if not isinstance(rollback, dict) or not rollback.get("command"):
        errors.append("rollback.command")
    if rollback.get("database_strategy") != (
        "forward-fix-or-restore; never down-migrate in place"
    ):
        errors.append("rollback.database_strategy")
```

實際 rollback 腳本，`scripts/release/rollback-cloud-run.sh:1-26`

```bash
#!/usr/bin/env bash
# 切回指定 Cloud Run revision；不執行 DB down migration。
set -euo pipefail
...
gcloud run revisions describe "${revision}" \
  --region="${REGION}" \
  --format='value(metadata.name)' >/dev/null
gcloud run services update-traffic "${service}" \
  --region="${REGION}" \
  --to-revisions="${revision}=100"
echo "traffic restored: ${service} -> ${revision}=100"
```

`SQL/migrations/` 目錄下共 126 個檔案，檔名含 `down` 或 `rollback` 者為 0 個（`ls SQL/migrations/ | grep -ci "down\|rollback"` → `0`）。

### 第 4 層 — migration 與 audit 證據不遺失

manifest 內的 migration 清單，`scripts/release/release_manifest.py:31-32`

```python
def _required_migrations(root: Path) -> list[str]:
    return sorted(path.name for path in (root / "SQL/migrations").glob("*.sql"))
```

寫入點 `:128`（`"migration_versions": _required_migrations(root)`）。

durable evidence gate，`.github/workflows/cloud-run-deploy.yml` 的 `contract-gate` job：

```bash
      - name: Durable migration evidence gate
        env:
          MIGRATION_EVIDENCE_URL: ${{ inputs.migration_evidence_url }}
        run: |
          case "${MIGRATION_EVIDENCE_URL}" in
            https://*|gs://*) ;;
            *) echo "migration_evidence_url must be a durable https:// or gs:// URL"; exit 1 ;;
          esac
```

drift 檢查在 `staging-evidence` job（`- name: Migration drift` → `uv run python scripts/ci/migration-drift-check.py`），另有獨立 workflow `.github/workflows/migration-drift-check.yml:20-32`（觸發於 `SQL/migrations/**` 變更）。該 workflow 檔頭 `:3-9` 記載：「編號唯一、全數登記 REGISTRY、無死列」「另支援多庫 DB 真值對照…opt-in，需 POSTGRES_URI/TECH_POSTGRES_URI/PLATFORM_POSTGRES_URI…CI 此 job 僅跑檔案層」。

audit 的 append-only 保證，`api/services/audit_log_service.py:27-30`

```python
# ── TI-AUDIT-03：append-only sha256 hash chain（合規紅線）────────────────────
# entry_hash = sha256(prev_hash + "|" + 正規化內容)；prev_hash 接前一列 entry_hash。
# 竄改任一列內容 → 其 entry_hash 對不上 → verify_audit_chain 偵測得到。
```

`api/services/audit_log_service.py:60-61`

```python
def _compute_entry_hash(prev_hash: str, content: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{content}".encode("utf-8")).hexdigest()
```

`:101` 另有 `audit_chain_checkpoint` 表的讀取、`:116` 有 `create_chain_checkpoint`。由於 rollback 僅切 Cloud Run 流量、不改 DB（第 3 層），audit_events 與 schema_migrations 的列不因 rollback 而被刪。

### 第 5 層 — manifest 產出與保存

`.github/workflows/cloud-run-deploy.yml` 的 `staging-evidence` job：

```bash
          output="release-evidence/${GITHUB_RUN_ID}-${{ inputs.component }}-staging.json"
          uv run python scripts/release/release_manifest.py create \
            --release-id "${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-staging" \
            --environment staging \
            ...
            --previous-revision "${{ needs.deploy-staging.outputs.previous_revision }}" \
            ...
            --migration-evidence "${{ inputs.migration_evidence_url }}" \
            ...
          uv run python scripts/release/release_manifest.py validate "${output}"
```

```yaml
      - uses: actions/upload-artifact@v4
        with:
          name: release-manifest-${{ github.run_id }}-${{ inputs.component }}-staging
          path: release-evidence/*.json
          if-no-files-found: error
          retention-days: 90
```

`promote-production` job 有結構相同的第二份（`-production.json`，同樣 `retention-days: 90`）。

`scripts/release/release_manifest.py:83-84`：`observation_window_minutes` 小於 15 即判為錯誤。

### 第 6 層 — 演練證據記錄器

`scripts/release/record-drill-evidence.py:1-2`

```python
#!/usr/bin/env python3
"""建立可稽核的 rollback/forward-fix/restore drill 證據；不允許空白佔位。"""
```

`scripts/release/record-drill-evidence.py:14-26`

```python
    parser.add_argument("--drill-type", choices=("rollback", "forward-fix", "restore"), required=True)
    parser.add_argument("--environment", choices=("staging", "production"), required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--finished-at", required=True)
    parser.add_argument("--result", choices=("passed", "failed"), required=True)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.evidence_url.startswith(("https://", "gs://")):
        raise SystemExit("evidence-url must be durable https:// or gs:// evidence")
```

該腳本收 `started_at` / `finished_at` / `result`，但在 `.github/workflows/` 中無呼叫點（`grep -rn "record-drill-evidence" .github/` 無輸出），僅由 `api/tests/test_cr_0190_release_governance.py:184` 的 `test_drill_recorder_requires_durable_evidence_url` 覆蓋。

### 第 7 層 — DORA 指標的計算實作

```
grep -rn "DORA\|lead_time\|change_failure\|MTTR" -i .github/ scripts/ api/ web/
（程式碼側無輸出；web/ 僅命中 i18n 檔中的 "vendorApprovals" 誤配，非 DORA）
```

文件側命中：

```
smartlock-docs/enterprise/05_NFR.md:217  | NFR-DORA-001 | Lead time | < 1 day | CI/CD metrics | 營運目標 |
smartlock-docs/enterprise/05_NFR.md:218  | NFR-DORA-002 | Change Failure Rate | < 15% | release 統計 | 營運目標 |
smartlock-docs/enterprise/05_NFR.md:219  | NFR-DORA-003 | MTTR | < 1 day | incident 統計 | 營運目標 |
smartlock-docs/enterprise/26_Incident_Postmortem.md:195  | **MTTR** | 事故偵測 → 恢復驗證通過 | < 1 天（DORA）|
smartlock-docs/enterprise/26_Incident_Postmortem.md:197  | **CFR（Change Failure Rate）** | 需回滾/hotfix 的部署 ÷ 總部署 | < 15%（DORA）|
```

`smartlock-docs/enterprise/20_Test_Cases.md:230-232` 對三條 NFR-DORA 皆標註「⚠ 完全沒有案例」。

TC 判定基準寫「**四項** DORA 指標可計算」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:434`）／NFR 只定義三項（NFR-DORA-001～003，`smartlock-docs/enterprise/05_NFR.md:217-219`），DORA 標準第四項（部署頻率）在 NFR 與程式碼中皆無對應條目。此處僅並陳，不裁定。

manifest 中與指標可能相關的欄位為 `created_at`（`scripts/release/release_manifest.py:148`，ISO8601 UTC）與 `commit_sha`（`:118`），但 repo 中無讀取這些 artifact 並聚合成指標的腳本。

---

## 既有測試證據

本次於本機 Docker 測試庫實跑（Windows 需 `-p winloop_plugin`）：

```
cd api && python -m pytest tests/test_cr_0190_release_governance.py -q -p winloop_plugin
15 passed in 0.46s

cd api && python -m pytest tests/test_cr_0190_job_registry.py -q -p winloop_plugin
7 passed in 0.42s
```

`api/tests/test_cr_0190_release_governance.py` 的 15 條測試名稱（`grep -n "def test_"`）：

```
25:def test_workflow_has_no_push_to_production_and_uses_protected_environments():
48:def test_production_promotes_build_output_digest_without_rebuild():
65:def test_manifest_validator_rejects_mutable_image_and_missing_evidence():
93:def test_manifest_schema_contains_no_secret_value_field():
106:def test_staging_and_production_each_publish_a_validated_manifest():
125:def test_workflow_requires_durable_database_migration_evidence():
137:def test_production_service_manifest_requires_a_rollback_revision():
174:def test_worker_job_uses_same_api_image_and_bounded_pilot():
184:def test_drill_recorder_requires_durable_evidence_url():
193:def test_routed_migration_never_records_a_failed_apply_or_swallows_drift():
206:def test_prism_smoke_uses_current_tenant_scoped_contract_paths():
234:def test_web_deploy_steps_all_pass_runtime_api_base_url():
278:def test_workflow_asserts_runtime_vars_before_deploy():
291:def test_smoke_actually_exercises_the_same_origin_proxy():
307:def test_web_sh_fails_fast_on_empty_runtime_var():
```

該檔涵蓋 release 治理與 rollback 欄位，**無**任何 DORA 指標計算的測試。

---

## 事實結論

1. release 流程只由 `workflow_dispatch` 觸發，無 branch push 直達 production（`.github/workflows/cloud-run-deploy.yml:1-8`）。
2. release manifest 有 21 個必填欄位，含 `release_id`、`commit_sha`（40 hex 驗證）、`image_digest`（`sha256:` + 64 hex 驗證）、`revision`、`previous_revision`、`migration_versions`、`migration_evidence`、`rollback`、`created_at`（`scripts/release/release_manifest.py:39-60`、`:22-25`、`:113-149`）。
3. production 晉升強制沿用 staging 的 digest，不重新 build（`.github/workflows/cloud-run-deploy.yml` `Assert immutable digest from staging`）。
4. rollback 指令由 `previous_revision` 自動生成；DB 策略以字面等值驗證固定為 `forward-fix-or-restore; never down-migrate in place`（`scripts/release/release_manifest.py:100-103`、`:143-146`）。
5. `scripts/release/rollback-cloud-run.sh:2` 註明「不執行 DB down migration」，實作為 `gcloud run services update-traffic --to-revisions=<rev>=100`；`SQL/migrations/` 下 126 個檔案中無任何 down/rollback 腳本。
6. migration 清單自 `SQL/migrations/*.sql` 檔名列入 manifest（`scripts/release/release_manifest.py:31-32`、`:128`）；migration 證據限 durable `https://`／`gs://` URL，於 `contract-gate` 與 manifest 驗證器兩處把關。
7. migration drift 有兩個檢查點：獨立 workflow（`.github/workflows/migration-drift-check.yml`，檔案層）與 `staging-evidence` job 內的同一支腳本。
8. audit 為 append-only sha256 hash chain（`api/services/audit_log_service.py:27-29`、`:60-61`），且 rollback 不觸及 DB，故 rollback 不刪除 audit 或 migration 紀錄。
9. 兩份 manifest（staging / production）皆以 `if-no-files-found: error` 上傳、保存 90 天。
10. `scripts/release/record-drill-evidence.py` 存在且拒絕非 durable URL，但在 `.github/workflows/` 中無呼叫點。
11. `DORA`／`lead_time`／`change_failure`／`MTTR` 在 `.github/`、`scripts/`、`api/`、`web/` 程式碼中零命中；repo 中無 DORA 指標的計算、儲存或呈現實作。`smartlock-docs/enterprise/20_Test_Cases.md:230-232` 對三條 NFR-DORA 標註「⚠ 完全沒有案例」。
12. TC 寫「四項 DORA 指標」而 NFR 只定義三項（NFR-DORA-001～003）；第四項在 NFR 與程式碼中皆無對應。
13. 「實際製造失敗並 rollback 後的指標數值與來源一致性」需執行期演練，本次未取得。
