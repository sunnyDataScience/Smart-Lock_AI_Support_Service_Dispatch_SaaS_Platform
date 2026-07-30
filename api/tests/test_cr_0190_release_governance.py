"""ADR-038：staging→production promotion、manifest 與 rollback 靜態關卡。"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _manifest_module():
    path = ROOT / "scripts/release/release_manifest.py"
    spec = importlib.util.spec_from_file_location("release_manifest", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_workflow_has_no_push_to_production_and_uses_protected_environments():
    workflow = (ROOT / ".github/workflows/cloud-run-deploy.yml").read_text(
        encoding="utf-8"
    )
    trigger = workflow.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "\n  push:" not in trigger
    assert "environment: staging" in workflow
    assert "environment: production" in workflow
    assert "needs: [build-once, deploy-staging, staging-evidence]" in workflow
    for node_id in (
        "test_missing_authorization_returns_401",
        "test_verify_expired_token_raises",
        "test_create_requires_platform_admin",
        "test_ingest_missing_token_401",
        "test_get_technician_v2_cross_tenant_403",
        "test_tenant_mismatch_returns_403",
        "test_tech_token_denied_on_brand_service",
    ):
        assert workflow.count(node_id) >= 2


@pytest.mark.unit
def test_production_promotes_build_output_digest_without_rebuild():
    workflow = (ROOT / ".github/workflows/cloud-run-deploy.yml").read_text(
        encoding="utf-8"
    )
    production = workflow.split("  promote-production:", 1)[1]
    assert "IMAGE_OVERRIDE: ${{ needs.build-once.outputs.image }}" in production
    assert '[[ "${IMAGE_OVERRIDE}" == *@sha256:* ]]' in production
    assert "--deploy-only" in production
    assert "--build-only" not in production
    assert "Production health/smoke" in production
    assert "worker-job) JOB_NAME=\"${name}\" EXECUTE_JOB=1" in production
    for script_name in ("api.sh", "agent.sh", "web.sh"):
        source = (ROOT / f"scripts/deploy/{script_name}").read_text(encoding="utf-8")
        assert "IMAGE_OVERRIDE" in source


@pytest.mark.unit
def test_manifest_validator_rejects_mutable_image_and_missing_evidence():
    module = _manifest_module()
    invalid = {
        "schema_version": "1.0",
        "environment": "production",
        "component": "api",
        "commit_sha": "a" * 40,
        "image": "example.invalid/api:latest",
        "image_digest": "latest",
        "resource_kind": "service",
        "observation_window_minutes": 30,
        "secret_references": ["POSTGRES_URI:latest"],
        "evidence": {},
        "rollback": {
            "command": "",
            "database_strategy": "down migration",
        },
    }
    errors = module.validate_manifest(invalid)
    assert "image_digest" in errors
    assert "image" in errors
    assert "migration_evidence" in errors
    assert "evidence.health" in errors
    assert "rollback.command" in errors
    assert "rollback.database_strategy" in errors


@pytest.mark.unit
def test_manifest_schema_contains_no_secret_value_field():
    schema = json.loads(
        (ROOT / "scripts/release/release-manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    properties = schema["properties"]
    assert "secret_references" in properties
    assert "secret_values" not in properties
    assert properties["image_digest"]["pattern"].startswith("^sha256:")


@pytest.mark.unit
def test_staging_and_production_each_publish_a_validated_manifest():
    workflow = (ROOT / ".github/workflows/cloud-run-deploy.yml").read_text(
        encoding="utf-8"
    )
    staging = workflow.split("  staging-evidence:", 1)[1].split(
        "  promote-production:", 1
    )[0]
    production = workflow.split("  promote-production:", 1)[1]
    assert "--environment staging" in staging
    assert "--migration-evidence" in staging
    assert "release_manifest.py validate" in staging
    assert "actions/upload-artifact@v4" in staging
    assert "--environment production" in production
    assert "--migration-evidence" in production
    assert "release_manifest.py validate" in production
    assert "actions/upload-artifact@v4" in production


@pytest.mark.unit
def test_workflow_requires_durable_database_migration_evidence():
    workflow = (ROOT / ".github/workflows/cloud-run-deploy.yml").read_text(
        encoding="utf-8"
    )
    assert "migration_evidence_url:" in workflow
    assert "required: true" in workflow.split("migration_evidence_url:", 1)[1].split(
        "permissions:", 1
    )[0]
    assert "https://*|gs://*" in workflow


@pytest.mark.unit
def test_production_service_manifest_requires_a_rollback_revision():
    module = _manifest_module()
    data = {
        "schema_version": "1.0",
        "release_id": "release-123",
        "environment": "production",
        "component": "api",
        "commit_sha": "a" * 40,
        "image": f"example.invalid/api@sha256:{'b' * 64}",
        "image_digest": f"sha256:{'b' * 64}",
        "resource_kind": "service",
        "resource_name": "smart-lock-api",
        "revision": "smart-lock-api-00002",
        "previous_revision": "",
        "migration_versions": ["120-user-preferences.sql"],
        "migration_evidence": "https://example.invalid/migrations/123",
        "config_references": [],
        "secret_references": [],
        "health_url": "https://api.example.invalid",
        "operator": "tester",
        "evidence": {
            key: f"https://example.invalid/{key}"
            for key in ("workflow_run", "health", "smoke", "bola", "worker")
        },
        "rollback": {
            "command": "scripts/release/rollback-cloud-run.sh smart-lock-api",
            "database_strategy": (
                "forward-fix-or-restore; never down-migrate in place"
            ),
        },
        "observation_window_minutes": 30,
        "created_at": "2026-07-27T00:00:00+00:00",
    }
    assert "previous_revision" in module.validate_manifest(data)


@pytest.mark.unit
def test_worker_job_uses_same_api_image_and_bounded_pilot():
    deploy = (ROOT / "scripts/deploy/worker-job.sh").read_text(encoding="utf-8")
    assert 'IMAGE_OVERRIDE:?IMAGE_OVERRIDE must be an immutable @sha256 digest' in deploy
    assert "webhook-idempotency-cleanup" in deploy
    assert "--tasks=1" in deploy
    assert "--max-retries=3" in deploy
    assert "worker_main,run" in deploy


@pytest.mark.unit
def test_drill_recorder_requires_durable_evidence_url():
    source = (ROOT / "scripts/release/record-drill-evidence.py").read_text(
        encoding="utf-8"
    )
    assert '"rollback", "forward-fix", "restore"' in source
    assert 'startswith(("https://", "gs://"))' in source


@pytest.mark.unit
def test_routed_migration_never_records_a_failed_apply_or_swallows_drift():
    source = (ROOT / "scripts/db/apply-schema-routed.sh").read_text(
        encoding="utf-8"
    )
    assert source.count("ON_ERROR_STOP=1") >= 2
    assert "ON_ERROR_STOP=0" not in source
    assert 'if ! apply_file "$u" "$f"; then' in source
    assert 'if ! record "$u" "$ver" "$base"; then' in source
    assert 'if ! python3 "${PROJECT_ROOT}/scripts/ci/migration-drift-check.py"; then' in source
    assert "本次 migration 發布證據不得標記成功" in source


@pytest.mark.unit
def test_prism_smoke_uses_current_tenant_scoped_contract_paths():
    workflow = (ROOT / ".github/workflows/mock-smoke.yml").read_text(
        encoding="utf-8"
    )
    compose = (ROOT / "api/docker-compose.mock.yml").read_text(encoding="utf-8")
    assert "/api/v1/work-orders" not in workflow
    for suffix in (
        "work-orders/pool",
        "dispatch/queue",
        "conversations",
        "notifications",
        "accounting/invoices",
    ):
        assert f"/tenants/00000000-0000-0000-0000-000000000000/{suffix}" in workflow
    assert "/tenants/health/work-orders/pool" in compose


# ── UAT-D-006：promotion 的 runtime proxy 變數三層防護 ────────────────────────
# 為什麼要用契約測試釘住：這個缺陷的失敗形態是「health check 綠、功能全死」——
# 沒有任何功能測試會抓到，防護一旦被靜默移除也不會有人發現。三層各擋不同時機：
#   ① web.sh pre-flight（部署腳本層）
#   ② workflow 前置 test -n（CI 層，錯誤訊息指向 GH 變數）
#   ③ smoke 實打 /api-proxy/health（驗收層，讓 503 真的擋住晉升）

_WEB_COMPONENTS = ("brand-web", "tech-web", "platform-web", "landing")


@pytest.mark.unit
def test_web_deploy_steps_all_pass_runtime_api_base_url():
    """workflow 每個 web component 的 deploy 步驟都必須帶 API_BASE_URL。

    漏帶＝該站 /api-proxy 全 503。原判定曾主張「沒人會設」，紅隊查證後推翻
    （四個 component 目前都有帶），故本測試是**釘住現狀**不讓它退化。
    """
    wf = (ROOT / ".github/workflows/cloud-run-deploy.yml").read_text(encoding="utf-8")

    # ⚠️ 元件名在 workflow 內出現多次（artifact 命名、resource 解析、deploy…），
    #    必須先把範圍縮到 deploy 步驟，否則會抓錯 case 分支（本測試初版就踩到）。
    def _deploy_blocks() -> list[str]:
        blocks = []
        for marker in ("Deploy exact staging digest", "Deploy to production"):
            start = wf.find(marker)
            if start == -1:
                continue
            # 到下一個 `- name:` 為止
            end = wf.find("\n      - name:", start + len(marker))
            blocks.append(wf[start: end if end != -1 else len(wf)])
        assert blocks, "workflow 找不到任何 deploy 步驟"
        return blocks

    # ⚠️ 不可用 `"API_BASE_URL=" in block`——`PLATFORM_API_BASE_URL=` 尾部就含
    #    `API_BASE_URL=`，於是移除了真正的 API_BASE_URL 仍會判為存在（本測試初版
    #    正是這樣假綠，靠反向驗證才抓到）。改用詞界：變數名前必須是行首或空白。
    def _passes(var: str, text: str) -> bool:
        return re.search(rf"(?:^|\s){re.escape(var)}=", text) is not None

    for block in _deploy_blocks():
        for comp in _WEB_COMPONENTS:
            idx = block.find(f"{comp})")
            if idx == -1:
                continue  # 該 deploy 步驟不含此元件分支
            case_block = block[idx: block.find(";;", idx)]
            assert _passes("API_BASE_URL", case_block), (
                f"{comp} 的 deploy 分支沒帶 API_BASE_URL → 該站 /api-proxy 會全數 503"
            )
            if comp in ("brand-web", "tech-web", "landing"):
                assert _passes("PLATFORM_API_BASE_URL", case_block), (
                    f"{comp} 有 /platform-api-proxy 但 deploy 沒帶 PLATFORM_API_BASE_URL"
                )


@pytest.mark.unit
def test_workflow_asserts_runtime_vars_before_deploy():
    """CI 必須在部署前先驗 GH Environment variable 非空（②）。"""
    wf = (ROOT / ".github/workflows/cloud-run-deploy.yml").read_text(encoding="utf-8")
    assert "RUNTIME_API_BASE_URL" in wf
    assert 'test -n "${{ vars.RUNTIME_API_BASE_URL }}"' in wf, (
        "workflow 缺 RUNTIME_API_BASE_URL 的前置非空檢查"
    )
    assert 'test -n "${{ vars.RUNTIME_PLATFORM_API_BASE_URL }}"' in wf, (
        "workflow 缺 RUNTIME_PLATFORM_API_BASE_URL 的前置非空檢查"
    )


@pytest.mark.unit
def test_smoke_actually_exercises_the_same_origin_proxy():
    """smoke 必須實打 /api-proxy/health（③）。

    只 curl `/` 的話，proxy 全 503 時頁面殼與 SSR 仍回 200 → smoke 綠、晉升通過、
    上線功能全死。staging 與 production 兩段都要有。
    """
    wf = (ROOT / ".github/workflows/cloud-run-deploy.yml").read_text(encoding="utf-8")
    assert wf.count("/api-proxy/health") >= 2, (
        "staging 與 production 的 smoke 都必須實打 /api-proxy/health"
    )
    assert wf.count("/platform-api-proxy/health") >= 2, (
        "有兩條 proxy 的站台，兩段 smoke 都要驗 /platform-api-proxy/health"
    )


@pytest.mark.unit
def test_web_sh_fails_fast_on_empty_runtime_var():
    """web.sh 必須擋「有傳入但為空」（①），且不可誤擋「完全未設」。

    兩者語意不同：CI 一律傳（空值＝GH 變數漏設，要擋）；手動部署完全不傳
    （靠 image 烤好的 NEXT_PUBLIC_* 直連，合法，不可擋）。
    """
    sh = (ROOT / "scripts/deploy/web.sh").read_text(encoding="utf-8")
    assert "_require_nonempty_if_set" in sh, "web.sh 缺 pre-flight 守衛"
    # 用 ${VAR+set} 才分得出 set-but-empty 與 unset
    assert "+set}" in sh, "守衛必須用 ${VAR+set} 區分『有設但空』與『未設』"
    assert "PROMOTION_BUILD" in sh
