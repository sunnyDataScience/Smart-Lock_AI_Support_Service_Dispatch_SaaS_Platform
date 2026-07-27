"""ADR-038：staging→production promotion、manifest 與 rollback 靜態關卡。"""

from __future__ import annotations

import importlib.util
import json
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
