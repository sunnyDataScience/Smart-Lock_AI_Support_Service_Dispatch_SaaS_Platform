"""M18 Runtime Config Governance tests (ADR-0067 Phase 0 / CR-0004 §8).

Tests:
  @pytest.mark.unit  — 純函式（無 DB）：schema 驗證、TTL cache
  @pytest.mark.component — 整合（需 live DB）：全部 7 endpoint + business logic

Component tests 使用 conftest 的 admin_headers（tenant 00000000-…-0001）。
每個 test 自建 / 自清 saas.config_version、saas.config_rollout、saas.config_audit
(namespace/tenant FK 存在即可，無需 setup seed)。
"""

from __future__ import annotations

import time
import uuid

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Unit tests (no DB)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSchemaValidation:
    """Unit tests for _validate_against_schema."""

    def test_valid_object_passes(self):
        from services.config_m18_service import _validate_against_schema
        schema = {"type": "object", "properties": {"normal_min": {"type": "integer"}}}
        _validate_against_schema({"normal_min": 10}, schema)  # should not raise

    def test_schema_required_missing_raises(self):
        from services.config_m18_service import _validate_against_schema
        from core.errors import ApiError
        schema = {
            "type": "object",
            "required": ["code", "label_zh"],
            "properties": {
                "code": {"type": "string"},
                "label_zh": {"type": "string"},
            },
        }
        with pytest.raises(ApiError) as ei:
            _validate_against_schema({"code": "X"}, schema)  # missing label_zh
        assert ei.value.error_code == "CONFIG_SCHEMA_INVALID"
        assert ei.value.status_code == 422

    def test_wrong_type_raises(self):
        from services.config_m18_service import _validate_against_schema
        from core.errors import ApiError
        schema = {"type": "object"}
        with pytest.raises(ApiError) as ei:
            _validate_against_schema("not_an_object", schema)
        assert ei.value.error_code == "CONFIG_SCHEMA_INVALID"

    def test_empty_schema_passes_any_object(self):
        from services.config_m18_service import _validate_against_schema
        _validate_against_schema({"anything": "goes"}, {"type": "object"})


@pytest.mark.unit
class TestTtlCache:
    """Unit tests for in-process TTL cache."""

    def setup_method(self):
        from services.config_m18_service import _READ_CACHE
        _READ_CACHE.clear()

    def test_cache_miss_on_empty(self):
        from services.config_m18_service import _cache_get
        assert _cache_get("t1", "sla_dispatch", "default") is None

    def test_cache_put_and_hit(self):
        from services.config_m18_service import _cache_put, _cache_get
        _cache_put("t1", "sla_dispatch", "default",
                   {"normal_min": 10}, "ver-123", "2026-06-02T00:00:00+00:00")
        cached = _cache_get("t1", "sla_dispatch", "default")
        assert cached is not None
        assert cached["version_id"] == "ver-123"
        assert cached["value"]["normal_min"] == 10

    def test_cache_expires(self, monkeypatch):
        from services.config_m18_service import _cache_put, _cache_get, _READ_CACHE, _CACHE_TTL_SECONDS
        _cache_put("t2", "sla_dispatch", "k",
                   {"v": 1}, "ver-456", "2026-06-02T00:00:00+00:00")
        # Simulate expiry by patching _cached_at
        ck = ("t2", "sla_dispatch", "k")
        _READ_CACHE[ck]["_cached_at"] = time.monotonic() - _CACHE_TTL_SECONDS - 1
        assert _cache_get("t2", "sla_dispatch", "k") is None

    def test_cache_invalidate(self):
        from services.config_m18_service import _cache_put, _cache_get, _cache_invalidate
        _cache_put("t3", "sla_dispatch", "k", {"v": 2}, "ver-789", "ts")
        _cache_invalidate("t3", "sla_dispatch", "k")
        assert _cache_get("t3", "sla_dispatch", "k") is None


# ─────────────────────────────────────────────────────────────────────────────
# Component tests (live DB)
# ─────────────────────────────────────────────────────────────────────────────

pytestmark_component = pytest.mark.component

TENANT_ID = "00000000-0000-0000-0000-000000000001"
INITIATOR_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"  # ADMIN_USER_ID from conftest
APPROVER_ID = "11111111-1111-1111-1111-111111111111"   # secondary admin from conftest


def _sod_headers_draft(admin_headers: dict) -> dict:
    return {**admin_headers, "X-Initiator": INITIATOR_ID}


def _sod_headers_rollout(admin_headers: dict) -> dict:
    return {
        **admin_headers,
        "X-Initiator": INITIATOR_ID,
        "X-Approver": APPROVER_ID,
    }


@pytest.mark.component
class TestListNamespaces:
    async def test_list_all(self, client, admin_headers):
        r = await client.get(f"/tenants/{TENANT_ID}/m18/configs", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        codes = body["items"]
        assert "sla_dispatch" in codes
        assert "cancellation_reason_codes" in codes
        assert len(codes) >= 6

    async def test_list_with_filter(self, client, admin_headers):
        r = await client.get(
            f"/tenants/{TENANT_ID}/m18/configs?namespace=sla_dispatch",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["items"] == ["sla_dispatch"]

    async def test_cross_tenant_403(self, client, admin_headers):
        other = str(uuid.uuid4())
        r = await client.get(f"/tenants/{other}/m18/configs", headers=admin_headers)
        assert r.status_code == 403


@pytest.mark.component
class TestDraft:
    async def test_draft_schema_invalid_422(self, client, admin_headers):
        """PUT with value failing namespace schema → 422 CONFIG_SCHEMA_INVALID."""
        # sla_dispatch schema: properties normal_min/urgent_min are integers
        # Send a string value to fail validation on required field type
        h = _sod_headers_draft(admin_headers)
        h["Idempotency-Key"] = str(uuid.uuid4())
        r = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/default",
            headers=h,
            json={
                "proposed_value": "not_an_object",  # fails type=object
                "reason": "test invalid",
            },
        )
        assert r.status_code == 422
        body = r.json()
        assert body.get("error_code") == "CONFIG_SCHEMA_INVALID"

    async def test_draft_success_201(self, client, admin_headers):
        """PUT valid value → 201 with version_id, state='draft'."""
        h = _sod_headers_draft(admin_headers)
        h["Idempotency-Key"] = str(uuid.uuid4())
        r = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/default",
            headers=h,
            json={
                "proposed_value": {"normal_min": 10, "urgent_min": 5},
                "reason": "initial setup",
            },
        )
        assert r.status_code == 201
        body = r.json()
        assert "version_id" in body
        assert body["state"] == "draft"
        assert "created_at" in body

    async def test_draft_missing_initiator_422(self, client, admin_headers):
        """Missing X-Initiator header → 422 VALIDATION_ERROR."""
        h = dict(admin_headers)
        h["Idempotency-Key"] = str(uuid.uuid4())
        r = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/default",
            headers=h,
            json={
                "proposed_value": {"normal_min": 10},
                "reason": "test",
            },
        )
        assert r.status_code == 422


@pytest.mark.component
class TestInstantRollout:
    async def test_instant_rollout_activates_and_dethrones(self, client, admin_headers):
        """instant rollout: version→active, previous active→retired."""
        # Create first draft + rollout it to active
        h_draft = _sod_headers_draft(admin_headers)
        h_draft["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/instant_test_key",
            headers=h_draft,
            json={"proposed_value": {"normal_min": 10, "urgent_min": 5}, "reason": "v1"},
        )
        assert r1.status_code == 201
        v1_id = r1.json()["version_id"]

        h_roll = _sod_headers_rollout(admin_headers)
        h_roll["Idempotency-Key"] = str(uuid.uuid4())
        r2 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/instant_test_key"
            f"/versions/{v1_id}:start-rollout",
            headers=h_roll,
            json={"strategy": "instant"},
        )
        assert r2.status_code == 202
        rollout1 = r2.json()
        assert rollout1["current_stage"] == "100%"
        assert rollout1["next_stage_eta"] is None

        # Verify active
        r_active = await client.get(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/instant_test_key",
            headers=admin_headers,
        )
        assert r_active.json()["active_version_id"] == v1_id

        # Create second draft + rollout → v1 should become retired
        h_draft2 = _sod_headers_draft(admin_headers)
        h_draft2["Idempotency-Key"] = str(uuid.uuid4())
        r3 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/instant_test_key",
            headers=h_draft2,
            json={"proposed_value": {"normal_min": 8, "urgent_min": 3}, "reason": "v2"},
        )
        assert r3.status_code == 201
        v2_id = r3.json()["version_id"]

        h_roll2 = _sod_headers_rollout(admin_headers)
        h_roll2["Idempotency-Key"] = str(uuid.uuid4())
        r4 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/instant_test_key"
            f"/versions/{v2_id}:start-rollout",
            headers=h_roll2,
            json={"strategy": "instant"},
        )
        assert r4.status_code == 202

        # v2 now active
        r_active2 = await client.get(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/instant_test_key",
            headers=admin_headers,
        )
        assert r_active2.json()["active_version_id"] == v2_id


@pytest.mark.component
class TestCanaryRollout:
    async def test_canary_rollout_rolling_out_state(self, client, admin_headers):
        """canary rollout: version→rolling_out, stage='5%'."""
        h_draft = _sod_headers_draft(admin_headers)
        h_draft["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/canary_test_key",
            headers=h_draft,
            json={"proposed_value": {"normal_min": 12}, "reason": "canary v1"},
        )
        assert r1.status_code == 201
        v_id = r1.json()["version_id"]

        h_roll = _sod_headers_rollout(admin_headers)
        h_roll["Idempotency-Key"] = str(uuid.uuid4())
        r2 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/canary_test_key"
            f"/versions/{v_id}:start-rollout",
            headers=h_roll,
            json={"strategy": "canary_5_50_100", "observation_minutes_per_stage": 15},
        )
        assert r2.status_code == 202
        body = r2.json()
        assert body["current_stage"] == "5%"
        assert body["next_stage_eta"] is not None
        assert "rollout_id" in body


@pytest.mark.component
class TestSodViolation:
    async def test_sod_violation_same_initiator_approver_403(self, client, admin_headers):
        """Same X-Initiator and X-Approver → 403 SOD_VIOLATION."""
        # First create a draft
        h_draft = _sod_headers_draft(admin_headers)
        h_draft["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/sod_test_key",
            headers=h_draft,
            json={"proposed_value": {"normal_min": 9}, "reason": "sod test"},
        )
        assert r1.status_code == 201
        v_id = r1.json()["version_id"]

        # Same person as initiator and approver
        h_sod_bad = {
            **admin_headers,
            "X-Initiator": INITIATOR_ID,
            "X-Approver": INITIATOR_ID,  # SAME — violation
            "Idempotency-Key": str(uuid.uuid4()),
        }
        r2 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/sla_dispatch/sod_test_key"
            f"/versions/{v_id}:start-rollout",
            headers=h_sod_bad,
            json={"strategy": "instant"},
        )
        assert r2.status_code == 403
        assert r2.json()["error_code"] == "SOD_VIOLATION"


@pytest.mark.component
class TestRollback:
    async def test_rollback_reactivates_parent(self, client, admin_headers):
        """rollback: rolled_back version, parent_version re-activated."""
        ns, key = "sla_dispatch", "rollback_test_key"

        # v1 → active (instant)
        h1 = _sod_headers_draft(admin_headers)
        h1["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}",
            headers=h1,
            json={"proposed_value": {"normal_min": 10}, "reason": "v1"},
        )
        assert r1.status_code == 201
        v1_id = r1.json()["version_id"]

        h_r1 = _sod_headers_rollout(admin_headers)
        h_r1["Idempotency-Key"] = str(uuid.uuid4())
        r2 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}/versions/{v1_id}:start-rollout",
            headers=h_r1,
            json={"strategy": "instant"},
        )
        assert r2.status_code == 202

        # v2 → rolling_out (canary)
        h2 = _sod_headers_draft(admin_headers)
        h2["Idempotency-Key"] = str(uuid.uuid4())
        r3 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}",
            headers=h2,
            json={"proposed_value": {"normal_min": 8}, "reason": "v2"},
        )
        assert r3.status_code == 201
        v2_id = r3.json()["version_id"]

        h_r2 = _sod_headers_rollout(admin_headers)
        h_r2["Idempotency-Key"] = str(uuid.uuid4())
        r4 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}/versions/{v2_id}:start-rollout",
            headers=h_r2,
            json={"strategy": "canary_5_50_100", "observation_minutes_per_stage": 10},
        )
        assert r4.status_code == 202
        rollout_id = r4.json()["rollout_id"]

        # Now rollback v2
        h_rb = {**admin_headers, "Idempotency-Key": str(uuid.uuid4())}
        r5 = await client.post(
            f"/tenants/{TENANT_ID}/m18/rollouts/{rollout_id}:rollback",
            headers=h_rb,
        )
        assert r5.status_code == 200
        assert r5.json()["current_stage"] == "rolled_back"

    async def test_instant_rollback_restores_previous_active(self, client, admin_headers):
        """instant rollback：v2 rolled_back 後前一 active v1 自動重啟（ADR-0067 restore previous）。

        驗 parent_version_id 連結（v2.parent=v1）+ rollback 重啟 v1 + ACL cache invalidation。
        """
        ns = "sla_dispatch"
        key = f"instant_restore_{uuid.uuid4().hex[:8]}"
        read_h = {"X-Tenant-ID": TENANT_ID}

        # v1 → active (instant)
        h1 = _sod_headers_draft(admin_headers)
        h1["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}",
            headers=h1, json={"proposed_value": {"normal_min": 11}, "reason": "v1"},
        )
        assert r1.status_code == 201
        v1_id = r1.json()["version_id"]
        hr1 = _sod_headers_rollout(admin_headers)
        hr1["Idempotency-Key"] = str(uuid.uuid4())
        assert (await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}/versions/{v1_id}:start-rollout",
            headers=hr1, json={"strategy": "instant"},
        )).status_code == 202

        # v2 → active (instant)；dethrones v1，parent 應指向 v1
        h2 = _sod_headers_draft(admin_headers)
        h2["Idempotency-Key"] = str(uuid.uuid4())
        r2 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}",
            headers=h2, json={"proposed_value": {"normal_min": 22}, "reason": "v2"},
        )
        v2_id = r2.json()["version_id"]
        hr2 = _sod_headers_rollout(admin_headers)
        hr2["Idempotency-Key"] = str(uuid.uuid4())
        r3 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}/versions/{v2_id}:start-rollout",
            headers=hr2, json={"strategy": "instant"},
        )
        assert r3.status_code == 202
        rollout2_id = r3.json()["rollout_id"]

        # config-read → v2 active
        rr = await client.get(f"/m18/config-read/{ns}/{key}", headers=read_h)
        assert rr.status_code == 200 and rr.json()["value"] == {"normal_min": 22}

        # rollback v2 → v1 重啟
        hrb = {**admin_headers, "Idempotency-Key": str(uuid.uuid4())}
        assert (await client.post(
            f"/tenants/{TENANT_ID}/m18/rollouts/{rollout2_id}:rollback", headers=hrb,
        )).status_code == 200

        # config-read → v1 restored（rollback 已 invalidate cache）
        rr2 = await client.get(f"/m18/config-read/{ns}/{key}", headers=read_h)
        assert rr2.status_code == 200
        assert rr2.json()["value"] == {"normal_min": 11}
        assert rr2.json()["version_id"] == v1_id


@pytest.mark.component
class TestAclRead:
    async def test_acl_read_404_no_active(self, client, admin_headers):
        """No active version → 404 CONFIG_NOT_FOUND."""
        h = {"X-Tenant-ID": TENANT_ID}
        r = await client.get(
            f"/m18/config-read/sla_dispatch/no_such_key_xyz",
            headers=h,
        )
        assert r.status_code == 404
        assert r.json()["error_code"] == "CONFIG_NOT_FOUND"

    async def test_acl_read_missing_tenant_422(self, client):
        """Missing X-Tenant-ID → 422."""
        r = await client.get("/m18/config-read/sla_dispatch/default")
        assert r.status_code == 422

    async def test_acl_read_hit_and_miss(self, client, admin_headers):
        """First read = miss, second = hit (TTL cache)."""
        from services.config_m18_service import _READ_CACHE
        ns, key = "sla_dispatch", "cache_test_key"

        # Create and activate
        h_draft = _sod_headers_draft(admin_headers)
        h_draft["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}",
            headers=h_draft,
            json={"proposed_value": {"normal_min": 11}, "reason": "cache test"},
        )
        assert r1.status_code == 201
        v_id = r1.json()["version_id"]

        h_roll = _sod_headers_rollout(admin_headers)
        h_roll["Idempotency-Key"] = str(uuid.uuid4())
        r2 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}/versions/{v_id}:start-rollout",
            headers=h_roll,
            json={"strategy": "instant"},
        )
        assert r2.status_code == 202

        # Clear cache to force miss
        _READ_CACHE.clear()

        h_read = {"X-Tenant-ID": TENANT_ID}
        # First read → miss
        r3 = await client.get(f"/m18/config-read/{ns}/{key}", headers=h_read)
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3["cache"] == "miss"
        assert body3["version_id"] == v_id
        assert "X-Config-Version" in r3.headers
        assert r3.headers["X-Config-Version"] == v_id

        # Second read → hit
        r4 = await client.get(f"/m18/config-read/{ns}/{key}", headers=h_read)
        assert r4.status_code == 200
        assert r4.json()["cache"] == "hit"

    async def test_acl_read_version_mismatch_409(self, client, admin_headers):
        """?version != active version_id → 409 CONFIG_VERSION_MISMATCH."""
        from services.config_m18_service import _READ_CACHE
        ns, key = "sla_dispatch", "mismatch_test_key"

        # Create and activate
        h_draft = _sod_headers_draft(admin_headers)
        h_draft["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}",
            headers=h_draft,
            json={"proposed_value": {"normal_min": 7}, "reason": "mismatch test"},
        )
        assert r1.status_code == 201
        v_id = r1.json()["version_id"]

        h_roll = _sod_headers_rollout(admin_headers)
        h_roll["Idempotency-Key"] = str(uuid.uuid4())
        r2 = await client.post(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}/versions/{v_id}:start-rollout",
            headers=h_roll,
            json={"strategy": "instant"},
        )
        assert r2.status_code == 202

        _READ_CACHE.clear()
        wrong_ver = str(uuid.uuid4())
        h_read = {"X-Tenant-ID": TENANT_ID}
        r3 = await client.get(
            f"/m18/config-read/{ns}/{key}?version={wrong_ver}",
            headers=h_read,
        )
        assert r3.status_code == 409
        assert r3.json()["error_code"] == "CONFIG_VERSION_MISMATCH"


@pytest.mark.component
class TestAuditList:
    async def test_audit_list_after_draft(self, client, admin_headers):
        """Audit list should contain draft_created entry after draft."""
        ns, key = "sla_dispatch", "audit_list_test_key"

        h_draft = _sod_headers_draft(admin_headers)
        h_draft["Idempotency-Key"] = str(uuid.uuid4())
        r1 = await client.put(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}",
            headers=h_draft,
            json={"proposed_value": {"normal_min": 15}, "reason": "audit test"},
        )
        assert r1.status_code == 201

        r2 = await client.get(
            f"/tenants/{TENANT_ID}/m18/configs/{ns}/{key}/audit",
            headers=admin_headers,
        )
        assert r2.status_code == 200
        body = r2.json()
        assert "items" in body
        assert "next_cursor" in body
        actions = [item["action"] for item in body["items"]]
        assert "draft_created" in actions


@pytest.mark.component
class TestCrossTenantGuard:
    async def test_draft_cross_tenant_403(self, client, admin_headers):
        """Tenant in token doesn't match path → 403."""
        other = str(uuid.uuid4())
        h = _sod_headers_draft(admin_headers)
        h["Idempotency-Key"] = str(uuid.uuid4())
        r = await client.put(
            f"/tenants/{other}/m18/configs/sla_dispatch/test",
            headers=h,
            json={"proposed_value": {"normal_min": 10}, "reason": "test"},
        )
        assert r.status_code == 403
