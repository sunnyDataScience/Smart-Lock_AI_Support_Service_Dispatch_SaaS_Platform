"""ADR-035：resource ownership matrix completeness 與負向證據索引。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.routing import APIRoute

import main
from core.resource_ownership import (
    OWNERSHIP_RULES,
    OwnershipContract,
    classify_route,
    is_governed_route,
    matrix_record,
)


@pytest.mark.unit
def test_every_mutation_and_sensitive_read_has_contract():
    missing = []
    records = []
    for route in main.app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = set(route.methods or ())
        if not is_governed_route(methods, route.path):
            continue
        try:
            records.append(matrix_record(methods, route.path))
        except LookupError:
            missing.append(f"{','.join(sorted(methods))} {route.path}")

    assert not missing, "ownership matrix 未分類:\n" + "\n".join(missing)
    assert records
    # 防止 catch-all 意外把所有端點都吞成同一 contract。
    assert {
        record["contract"] for record in records
    }.issuperset(
        {
            OwnershipContract.BRAND_TENANT.value,
            OwnershipContract.TECHNICIAN.value,
            OwnershipContract.PLATFORM.value,
            OwnershipContract.INTERNAL_SERVICE.value,
        }
    )


@pytest.mark.unit
def test_each_contract_rule_has_real_negative_test_evidence():
    root = Path(__file__).parents[2]
    missing = []
    for rule in OWNERSHIP_RULES:
        assert rule.required_checks
        assert rule.negative_test_ids
        for node_id in rule.negative_test_ids:
            file_name, test_name = node_id.split("::", 1)
            path = root / file_name
            if not path.exists() or f"def {test_name.split('[')[0]}" not in path.read_text(
                encoding="utf-8"
            ):
                missing.append(node_id)
    assert not missing, "matrix 引用不存在的負向測試:\n" + "\n".join(missing)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path", "contract"),
    [
        ("/tenants/{tenantId}/work-orders/{woId}", OwnershipContract.BRAND_TENANT),
        ("/tenants/{tenantId}/customers", OwnershipContract.BRAND_TENANT),
        ("/api/v1/platform/tenants", OwnershipContract.PLATFORM),
        ("/api/v1/internal/conversations/ingest", OwnershipContract.INTERNAL_SERVICE),
        ("/api/v1/auth/login", OwnershipContract.PUBLIC_AUTH),
    ],
)
def test_representative_surface_classification(path, contract):
    assert classify_route(path).contract == contract
