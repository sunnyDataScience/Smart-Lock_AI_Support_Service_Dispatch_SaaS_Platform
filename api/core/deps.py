"""FastAPI dependencies — 把 auth/tenant/db 注入到 router handler。"""

from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass

from fastapi import Depends, Header, Request

from core.auth import decode_token, is_jti_revoked, load_user_security_state, portal_for_role
from core.errors import ApiError
from core.oidc import OIDCError, oidc_enabled, verify_oidc_token
from core.tenant import resolve_tenant_id

logger = logging.getLogger("api.deps")


@dataclass
class CurrentUser:
    user_id: str
    role: str
    tenant_id: str
    jti: str
    token_type: str


# CR-0182（UAT-0723-F2）：跨面 token 守衛。三面共用 JWT secret，技師 token 過去可直接
# 讀 brand-api 客戶 PII/金流。本服務只接受 ALLOWED_TOKEN_PORTALS 列出的面向 token。
#   - env 未設/空 → None → 不強制（本機單體、pytest 之 API_SURFACE=all 沿用既有行為）
#   - 雲端各服務顯式設定：brand-api=brand、tech-api=tech、platform-api=platform（api.sh）
#   刻意獨立於 API_SURFACE（=部署塑形，all 同時是單體/測試模式，復用會自我失效）。
def _allowed_portals() -> frozenset[str] | None:
    raw = os.environ.get("ALLOWED_TOKEN_PORTALS", "").strip()
    if not raw:
        return None
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


# ACT-01 地基(CR-0141 D5):R2 薄回調 handler 會把 token 寫進 httpOnly cookie;
# 無 Authorization header 時退回讀此 cookie。CSRF 緩解:SameSite=Lax +
# tenant-scoped 端點強制 X-Tenant-ID 自訂 header(必觸發 CORS preflight)。
_ACCESS_TOKEN_COOKIE = "smartlock_access_token"


def _extract_bearer(authorization: str | None, request: Request | None = None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if request is not None:
        cookie_token = request.cookies.get(_ACCESS_TOKEN_COOKIE, "").strip()
        if cookie_token:
            return cookie_token
    raise ApiError(
        error_code="UNAUTHENTICATED",
        message="Missing or invalid Authorization header",
        status_code=401,
    )


def _decode_any_token(token: str) -> dict:
    """依 JWT header `alg` 路由驗證器（CR-0177 S1，HD-5 dual-accept）。

    cutover 目標態＝Casdoor **RS256 為第一級公民**；過渡期仍接受自簽 **HS256**
    （S5 過渡期滿後移除 HS256 分支）。取代原「HS256 先試、失敗才試 OIDC」的優先序：
    各 token 直達對應驗證器，不必先失敗一次（省一次解碼、log 不再有誤導性失敗）。

    **無 alg-confusion 風險**：兩條路徑各自釘死演算法——`decode_token` →
    `algorithms=[HS256]`、`verify_oidc_token` → `algorithms=["RS256"]`；偽造 header 的
    alg 只會被導到對應驗證器並因簽章不符而失敗，無法用公鑰當 HMAC secret 繞過。

    OIDC payload 已由 core.oidc 正規化為同形 dict（sub=users.id 映射），
    下游 jti 撤銷/A2/A3 重查/role_required 零改動。
    alg 不可判讀（壞 token）→ 保守雙試（沿舊序），行為同舊版。
    """
    from jose import jwt as _jwt

    alg = ""
    try:
        alg = str((_jwt.get_unverified_header(token) or {}).get("alg", "")).upper()
    except Exception:  # noqa: BLE001 — 壞 token 交由下方驗證器統一報錯
        alg = ""

    if alg == "RS256":
        if not oidc_enabled():
            # 明確錯誤（原版會回傳誤導性的 HS256 解碼失敗）
            raise OIDCError("收到 RS256 token 但 OIDC 未配置（CASDOOR_* 缺）")
        try:
            return verify_oidc_token(token)
        except OIDCError as e:
            logger.debug("OIDC 驗證失敗: %s", e)
            raise
    if alg == "HS256":
        return decode_token(token)

    # alg 不可判讀 → 保守雙試（自簽 → OIDC），與舊版一致
    try:
        return decode_token(token)
    except Exception:
        if not oidc_enabled():
            raise
        try:
            return verify_oidc_token(token)
        except OIDCError as e:
            logger.debug("OIDC 驗證失敗: %s", e)
            raise


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    token = _extract_bearer(authorization, request)
    try:
        payload = _decode_any_token(token)
    except Exception:
        raise ApiError(
            error_code="UNAUTHENTICATED",
            message="Invalid or expired token",
            status_code=401,
        )

    if payload.get("type") != "access":
        raise ApiError(
            error_code="UNAUTHENTICATED",
            message="Refresh token cannot be used for API access",
            status_code=401,
        )

    token_role = payload.get("role")

    # CR-0182（UAT-0723-F2）：跨面守衛。缺 portal 的 token（部署後 1h 內舊 access token、
    # 或 SSO token——oidc.verify_oidc_token 不經 create_token）由 role 即時推導（braces）。
    # portal 為 None（空/未知 role）或不在本服務允許集 → 403，不落最敏感的 brand。
    # 掛在 get_current_user 單點即涵蓋所有受保護 HTTP 端點（含 F2 目標 bare require_tenant）。
    # 範圍＝HTTP-only；WS 授權由 verify_ws_token/authorize_channel 另行把關。
    _allowed = _allowed_portals()
    if _allowed is not None:
        portal = payload.get("portal") or portal_for_role(token_role)
        if portal not in _allowed:
            raise ApiError(
                error_code="CROSS_PORTAL_FORBIDDEN",
                message="Token is not valid for this service surface",
                status_code=403,
            )

    # CR-0114：platform_admin 的 revoked_jti/users 住平台庫 → 依 token role 路由查詢
    # （未配置平台庫時 fallback 主連線，行為同舊版）。
    jti = payload.get("jti")
    if jti and await is_jti_revoked(jti, token_role):
        raise ApiError(
            error_code="TOKEN_REVOKED",
            message="Token has been revoked",
            status_code=401,
        )

    # A2/A3：每請求重查使用者狀態（停權即時失效 + 改密碼後撤既有 session）。
    # fail-open：查無/無 DB → None → 維持 claims-only（見 load_user_security_state）。
    # 例外（UAT-0718 R2）：technician 於雙庫模式讀權威庫且 fail-closed（503）。
    state = await load_user_security_state(payload["sub"], token_role)
    if state is not None:
        if not state["is_active"]:
            raise ApiError(
                error_code="ACCOUNT_DISABLED",
                message="Account has been disabled",
                status_code=403,
            )
        pwd_changed = state["password_changed_at"]
        iat = payload.get("iat")
        if pwd_changed and iat is not None and int(iat) < int(pwd_changed.timestamp()):
            raise ApiError(
                error_code="TOKEN_STALE",
                message="Session invalidated by password change; please log in again",
                status_code=401,
            )

    return CurrentUser(
        user_id=payload["sub"],
        role=payload.get("role", ""),
        tenant_id=payload.get("tenant_id", ""),
        jti=jti or "",
        token_type=payload.get("type", "access"),
    )


async def get_current_user_with_tenant(
    user: CurrentUser = ...,  # filled at runtime via Depends chain below
) -> CurrentUser:
    """Placeholder — 實際 chain 在 require_tenant 中組合。"""
    return user


async def require_tenant(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> CurrentUser:
    """同時驗 JWT + 比對 X-Tenant-ID 與 claim 一致。"""
    user = await get_current_user(request, authorization)
    tenant = await resolve_tenant_id(x_tenant_id)
    if user.tenant_id and user.tenant_id != tenant:
        raise ApiError(
            error_code="TENANT_MISMATCH",
            message="X-Tenant-ID does not match token claim",
            status_code=403,
        )
    return user


async def require_admin(user: CurrentUser) -> CurrentUser:
    if user.role != "admin":
        raise ApiError(
            error_code="FORBIDDEN",
            message="Admin role required",
            status_code=403,
        )
    return user


async def require_platform_admin(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """平台方 console 專用守衛（CR-0114）。

    非 tenant-scoped：不收 X-Tenant-ID（platform console 跨品牌視角）。
    只放行 role=platform_admin —— 該角色不在任何品牌 gate 集合
    （FULL_ACCESS/OPS/DISPATCH…），品牌 token 打平台端點、平台 token 打
    品牌端點皆 deny-by-default。
    """
    user = await get_current_user(request, authorization)
    if user.role != "platform_admin":
        raise ApiError(
            error_code="FORBIDDEN",
            message="Platform admin role required",
            status_code=403,
        )
    return user


@dataclass
class SodActors:
    """SoD 三維行為人（BR-M17-01 / ADR-0102 §D）。"""

    initiator: str
    approver: str
    executor: str | None


async def require_sod_actors(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
    x_approver: str | None = Header(default=None, alias="X-Approver"),
    x_executor: str | None = Header(default=None, alias="X-Executor"),
) -> SodActors:
    """解析 X-Initiator / X-Approver / X-Executor headers。

    spec（openapi-smart-lock-saas.yaml）: X-Initiator + X-Approver required，
    X-Executor optional。任二相同 → 403 SOD_VIOLATION。
    """
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    if not x_approver:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Approver", 422)
    actors = [a for a in (x_initiator, x_approver, x_executor) if a]
    if len(actors) != len(set(actors)):
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: X-Initiator / X-Approver / X-Executor must be distinct",
            403,
        )
    return SodActors(initiator=x_initiator, approver=x_approver, executor=x_executor)


# ---------------------------------------------------------------------------
# CR-0092 — 標準角色集合（單一真相源）
#
# 為什麼集中在此：稽核發現 407 端點中 80 個敏感寫入只用 require_tenant（不檢查
# 角色），任何登入者含 technician/vendor 皆可寫金流/設定/派工。各 router 原本
# 各自定義 _BILLING_ROLES / _APPROVE_ROLES / _DISPATCH_ALLOWED_ROLES，集合不一
# 且常漏掛。以下常數為「既有 gated 端點角色集的超集 + super_admin」：
#   - 不破既有存取（既有集合皆為子集，只多放行 super_admin，修正其被誤擋的潛在 bug）
#   - 對齊前端 web/src/lib/rolePolicy.ts 意圖（後台頁 admin/ops/dispatcher/cs）
# ---------------------------------------------------------------------------

#: 全權管理角色（admin governance：config / roles / audit / GDPR / data-correction）
# SA-01（CR-0130 業主裁決 2026-07-09）：死角色 tenant_admin/super_admin 全面移除——
# 7 角色正典（13_Security §3.1）；殘存死角色 token 不再放行任何守衛（與 SA-06 前端一致）。
FULL_ACCESS_ROLES: tuple[str, ...] = ("admin",)
#: 營運後台寫入（accounting / billing / pricing / vendor-mgmt / warranty / 結算）
OPS_ROLES: tuple[str, ...] = FULL_ACCESS_ROLES + ("operations_manager",)
#: 派工寫入（dispatch / 自動媒合 / 技師生命週期管理）
DISPATCH_ROLES: tuple[str, ...] = OPS_ROLES + ("dispatcher",)
#: 後台唯讀／一般後台操作（含客服）
BACKOFFICE_ROLES: tuple[str, ...] = DISPATCH_ROLES + ("customer_service",)
#: 審核寫入（退款 / 保固 / 爭議）—— 對齊 role_service._MATRIX：reviewer 於此三域可寫（CR-0094）
REVIEW_ROLES: tuple[str, ...] = OPS_ROLES + ("reviewer",)
#: 技師現場動作（接單/完工/簽名/到場/門況/延誤/用料/現場修正）＋後台代操作（SA-01/CR-0130）
#: —— 對齊矩陣 technician.work_orders.write；vendor / line_user 一律 403
TECH_ACTION_ROLES: tuple[str, ...] = BACKOFFICE_ROLES + ("technician",)


def role_required(*roles: str, fail_closed: bool = False):
    """Dependency factory 限制角色。

    fail_closed（SA-05 / CR-0131 關鍵金流/派工寫入白名單）：安全狀態不可驗
    （DB 不可用 → revoked_jti / is_active 查不到）時拒絕請求（503），不退
    claims-only。一般端點維持 C-05 fail-open 取捨（可用性換安全）。
    """
    async def _dep(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> CurrentUser:
        user = await require_tenant(request, authorization, x_tenant_id)
        if roles and user.role not in roles:
            raise ApiError(
                error_code="FORBIDDEN",
                message=f"Requires one of roles: {', '.join(roles)}",
                status_code=403,
            )
        if fail_closed:
            from core.auth import security_state_verifiable

            if not await security_state_verifiable(user.role):
                raise ApiError(
                    error_code="SECURITY_STATE_UNAVAILABLE",
                    message="安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）",
                    status_code=503,
                )
        return user
    return _dep


def permission_shadow(resource: str, action: str):
    """Shadow-mode RBAC 稽核 dependency（CR-0111 後續 · log-only · 永不擋）。

    掛在既有 role_required / require_tenant 守衛**之外**當額外 side-effect：計算「權限
    矩陣是否允許此 user 的 (resource, action)」，若矩陣會拒但端點放行 → 記一筆
    RBAC_SHADOW_DENY，蒐集『矩陣 vs 現行寫死 role_required』的落差資料，供未來把授權
    收斂到矩陣（CIA / CR-0092 rbac-hardening）時安全 rollout。

    **絕不 raise、絕不改變請求結果**（授權仍由既有守衛決定）。接端點真正強制授權
    是另一步、需先對帳 195 條 role_required（見 role_service.has_permission docstring）。
    """

    async def _dep(user: CurrentUser = Depends(require_tenant)) -> None:
        try:
            from services import role_service  # lazy import：避免 import 期循環

            allowed = await role_service.has_permission(
                tenant_id=user.tenant_id,
                role=user.role,
                resource=resource,
                action=action,
            )
            if not allowed:
                logger.warning(
                    "RBAC_SHADOW_DENY resource=%s action=%s role=%s tenant=%s "
                    "— 矩陣會拒但目前放行（接強制前需對帳）",
                    resource,
                    action,
                    user.role,
                    user.tenant_id,
                )
        except Exception:  # noqa: BLE001 — shadow 稽核絕不影響請求
            logger.exception(
                "permission_shadow check failed (resource=%s action=%s)",
                resource,
                action,
            )
        return None

    return _dep


# HD-VCH-003：platform keeper role — X-Keeper-Role header + user.role 屬平台管理員集合
_KEEPER_ROLES: frozenset[str] = frozenset({"admin", "platform_admin", "platform_keeper"})


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """服務間（service-to-service）internal token 驗證。

    用於非人類發動、無 JWT 的內部寫入路徑（如 LINE agent gateway 把對話旁路
    持久化到 conversations/messages，方案 A）。期望 token 來自環境變數
    `INTERNAL_API_TOKEN`。

    **Fail closed**：env 未設定時一律拒絕（503），絕不放行無認證的 DB 寫入端點。
    比對用 `hmac.compare_digest` 做常數時間比較，避免 timing attack。
    """
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 留 \n）；
    # 兩邊都 strip 才能正確比對（agent 端送 header 前亦 strip）。
    expected = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if not expected:
        raise ApiError(
            error_code="INTERNAL_AUTH_NOT_CONFIGURED",
            message="Internal API token not configured on server",
            status_code=503,
        )
    incoming = (x_internal_token or "").strip()
    if not incoming or not hmac.compare_digest(incoming, expected):
        raise ApiError(
            error_code="INTERNAL_AUTH_FAILED",
            message="Missing or invalid X-Internal-Token",
            status_code=401,
        )


async def require_keeper_role(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_keeper_role: str | None = Header(default=None, alias="X-Keeper-Role"),
) -> CurrentUser:
    """Voucher void 專用 dependency（HD-VCH-003）。

    檢查：
      1. Bearer token 有效（get_current_user）
      2. X-Keeper-Role header 必填
      3. user.role 屬 platform admin 集合（_KEEPER_ROLES）

    flat path（/vouchers/{id}/void）不做 tenant 綁定；keeper 可跨租戶操作，
    voucher 自帶 tenant_id 做隔離。
    """
    user = await get_current_user(request, authorization)
    if not x_keeper_role:
        raise ApiError(
            error_code="KEEPER_ROLE_REQUIRED",
            message="Missing X-Keeper-Role header",
            status_code=403,
        )
    if user.role not in _KEEPER_ROLES:
        raise ApiError(
            error_code="KEEPER_FORBIDDEN",
            message="Voucher void requires platform keeper role",
            status_code=403,
        )
    return user
