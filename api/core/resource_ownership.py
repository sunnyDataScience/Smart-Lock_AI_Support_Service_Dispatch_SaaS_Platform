"""ADR-035 API resource ownership contract matrix。

矩陣以 precedence rule 分類 FastAPI surface；CI 會對所有 mutation 與敏感
read/export 路由執行 completeness check。這是授權治理索引，不取代 router/service
的實際 require_tenant、role、resource-owner SQL。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class OwnershipContract(StrEnum):
    BRAND_TENANT = "brand_tenant_resource"
    TECHNICIAN = "technician_resource"
    PLATFORM = "platform_resource"
    INTERNAL_SERVICE = "internal_service_resource"
    PUBLIC_CAPABILITY = "public_capability_resource"
    PUBLIC_AUTH = "public_auth_resource"


@dataclass(frozen=True)
class OwnershipRule:
    rule_id: str
    contract: OwnershipContract
    path_pattern: str
    negative_test_ids: tuple[str, ...]
    required_checks: tuple[str, ...]

    def matches(self, path: str) -> bool:
        return re.search(self.path_pattern, path) is not None


# 規則由最窄到最廣；最後的 legacy-brand catch-all 讓舊 /api/v1 surface 也必須
# 明確歸入品牌契約，而不是落到「未分類＝沒人負責」。
OWNERSHIP_RULES: tuple[OwnershipRule, ...] = (
    OwnershipRule(
        "public-auth",
        OwnershipContract.PUBLIC_AUTH,
        r"^/(?:health|docs|openapi\.json|redoc)$|"
        r"/(?:login|register|request-password-reset|confirm-password-reset)$|"
        r"^/api/v1/platform/brand-applications$",
        ("api/tests/test_auth_guards.py::test_missing_authorization_returns_401",),
        ("rate_limit", "input_validation", "no_ambient_tenant"),
    ),
    OwnershipRule(
        "public-capability",
        OwnershipContract.PUBLIC_CAPABILITY,
        r"^/(?:api/v1/)?(?:public|consumer)(?:/|$)|"
        r"^/(?:quotes|track|consent|scope-change)(?:/|$)",
        ("api/tests/test_public_token.py::test_verify_expired_token_raises",),
        ("capability_scope", "expiry", "usage_state", "resource_owner"),
    ),
    OwnershipRule(
        "platform",
        OwnershipContract.PLATFORM,
        r"^/api/v1/platform(?:/|$)",
        ("api/tests/test_platform_vendor_create.py::test_create_requires_platform_admin",),
        ("platform_principal", "capability", "ignore_request_tenant_for_grant"),
    ),
    OwnershipRule(
        "internal-service",
        OwnershipContract.INTERNAL_SERVICE,
        r"(?:^|/)internal(?:/|$)",
        ("api/tests/test_internal_ingest.py::test_ingest_missing_token_401",),
        ("service_principal", "audience", "scope", "request_id", "brand_scope"),
    ),
    OwnershipRule(
        "technician",
        OwnershipContract.TECHNICIAN,
        r"(?:^|/)(?:technicians|tech-statements)(?:/|$)|"
        r"^/api/v1/work-orders(?:/|$)|^/realtime/pool/",
        ("api/tests/test_technicians_v2_endpoint.py::test_get_technician_v2_cross_tenant_403",),
        ("tech_principal_or_brand_role", "brand_entitlement", "assignee_or_projection"),
    ),
    OwnershipRule(
        "brand-tenant-v2",
        OwnershipContract.BRAND_TENANT,
        r"^/tenants/\{tenantId\}(?:/|$)",
        ("api/tests/test_auth_guards.py::test_tenant_mismatch_returns_403",),
        ("path_tenant", "claim_tenant", "resource_tenant", "active_membership"),
    ),
    OwnershipRule(
        "brand-legacy",
        OwnershipContract.BRAND_TENANT,
        r"^/(?:api/v1/)?",
        ("api/tests/test_cr_0182_portal_guard.py::test_tech_token_denied_on_brand_service",),
        ("portal_principal", "claim_tenant", "resource_owner", "role"),
    ),
)

_SENSITIVE_READ_MARKERS = (
    "customer",
    "work-order",
    "problem-card",
    "technician",
    "refund",
    "settlement",
    "reconciliation",
    "invoice",
    "voucher",
    "warranty",
    "dispute",
    "audit",
    "report",
    "export",
    "media",
    "conversation",
    "notification",
    "config",
    "role",
    "statement",
)


def classify_route(path: str) -> OwnershipRule:
    for rule in OWNERSHIP_RULES:
        if rule.matches(path):
            return rule
    raise LookupError(f"Unclassified API route: {path}")


def is_governed_route(methods: set[str], path: str) -> bool:
    normalized = {method.upper() for method in methods}
    if normalized.intersection({"POST", "PUT", "PATCH", "DELETE"}):
        return True
    if "GET" not in normalized:
        return False
    lowered = path.lower()
    return any(marker in lowered for marker in _SENSITIVE_READ_MARKERS)


def matrix_record(methods: set[str], path: str) -> dict:
    rule = classify_route(path)
    return {
        "methods": sorted(methods),
        "path": path,
        "rule_id": rule.rule_id,
        "contract": rule.contract.value,
        "required_checks": list(rule.required_checks),
        "negative_test_ids": list(rule.negative_test_ids),
    }
