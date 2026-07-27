"""Auth router — 登入/登出/token/密碼/個資自助 + 技師註冊與文件上傳 + 廠商登入。

廠商自助註冊（registerVendor）已於 2026-07-18 依 UAT R2 W3-2 裁決移除，
廠商帳號由平台代建（routers/platform_vendors.py）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field

from core.auth_cookie import (
    REFRESH_COOKIE,
    clear_session_cookies,
    set_access_cookie,
    set_refresh_cookie,
)
from core.config import load_config
from core.deps import CurrentUser, get_current_user, role_required
from core.errors import ApiError
from core.idempotency import (
    IdempotencyContext,
    PUBLIC_TENANT_NAMESPACE,
    make_idempotency_guard,
)
from services import auth_service, password_reset_service, technician_kyc_service

logger = logging.getLogger("api.routers.auth")
router = APIRouter()

# CR-0165 F12：公開無登入註冊端點——缺 X-Tenant-ID 時 fallback 公共命名空間去重
_public_register_idem = make_idempotency_guard(default_tenant=PUBLIC_TENANT_NAMESPACE)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TechnicianLoginBody(BaseModel):
    # CR-0099：技師可用手機號（09xxxxxxxx）或 Email 登入，故收通用 identifier 而非 EmailStr。
    identifier: str = Field(min_length=1, max_length=255, description="手機號（09xxxxxxxx）或 Email")
    password: str = Field(min_length=8)


class RefreshBody(BaseModel):
    refresh_token: str | None = None


class LogoutBody(BaseModel):
    refresh_token: str | None = None


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class UpdateProfileBody(BaseModel):
    # 皆選填：只更新有帶入的欄位（自助個人資料）
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=50)


class AdminResetPasswordBody(BaseModel):
    email: EmailStr


class RequestPasswordResetBody(BaseModel):
    email: EmailStr


class ConfirmPasswordResetBody(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)  # bcrypt 72 byte 上限


class TechnicianCertInput(BaseModel):
    """註冊時自填的專業證照（CR-0115 Tier 1；落 technician_certification 表）。"""

    cert_name: str = Field(min_length=1, max_length=120)
    brand: str | None = Field(default=None, max_length=100)
    obtained_at: str | None = Field(default=None, description="YYYY-MM-DD")
    expires_at: str | None = Field(default=None, description="YYYY-MM-DD")


class TechnicianRegisterBody(BaseModel):
    """師傅自助註冊（CR-0115 擴充為 KYC 等級）。

    既有 6 欄（name/phone/email/password/capabilities/regions）不變；新欄一律
    **選填**（加性非破壞，§4）—— 「最小必填」由新版 /tech-register 多步驟表單
    層強制（§8-4），敏感 PII 與文件可於核准前補件。
    """

    # ── 既有 6 欄 ──
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^09\d{8}$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt 72 byte 上限
    capabilities: list[str] | None = None
    regions: list[str] | None = None

    # ── Tier 1 非敏感（CR-0115）──
    years_experience: int | None = Field(default=None, ge=0, le=80)
    bio: str | None = Field(default=None, max_length=1000)
    vehicle_type: str | None = Field(default=None, max_length=20)
    availability_note: str | None = Field(default=None, max_length=40)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = Field(default=None, pattern=r"^09\d{8}$")
    certifications: list[TechnicianCertInput] | None = None
    terms_accepted: bool | None = Field(
        default=None, description="服務條款/隱私權/背景查核授權同意（新表單必勾）"
    )

    # ── Tier 2 敏感 PII（CR-0115 §8-1；獨立表加密儲存）──
    national_id: str | None = Field(
        default=None, pattern=r"^[A-Z][12]\d{8}$", description="身分證字號（加密儲存）"
    )
    birth_date: str | None = Field(default=None, description="YYYY-MM-DD")
    address: str | None = Field(default=None, max_length=300)
    bank_code: str | None = Field(default=None, pattern=r"^\d{3,4}$")
    bank_account: str | None = Field(
        default=None, pattern=r"^\d{6,16}$", description="撥款帳號（加密儲存）"
    )
    tax_id: str | None = Field(default=None, pattern=r"^\d{8}$")


# admin web 可登入的後台角色（CR-0021 Q2）。technician 走 /technicians/login。
# 放寬只是讓這些後台角色能取得 admin-web token;各 endpoint 仍受後端 role_required 守衛。
_ADMIN_WEB_ROLES = [
    "admin",
    "reviewer",
    "operations_manager",
    "dispatcher",
    "customer_service",
]


def _set_login_cookies(response: Response, payload: dict) -> None:
    """登入/刷新成功後，access/refresh 都寫 HttpOnly cookie。"""
    data = (payload or {}).get("data") or {}
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if access:
        set_access_cookie(response, access, int(data.get("expires_in") or 3600))
    if refresh:
        days = int(load_config().auth.get("refresh_token_ttl_days", 30))
        set_refresh_cookie(response, refresh, days * 86400)


def _auth_response_payload(request: Request, payload: dict) -> dict:
    """Browser 明示 cookie mode 時不把 bearer/refresh secret 暴露給 JS。

    CLI／mobile 未帶 header 時維持既有 token response，相容外部 API consumer。
    """
    if request.headers.get("X-Auth-Response-Mode", "").lower() != "cookie":
        return payload
    data = (payload or {}).get("data") or {}
    return {
        "data": {
            "authenticated": True,
            "token_type": "HttpOnly-Cookie",
            "expires_in": int(data.get("expires_in") or 3600),
        },
        "message": payload.get("message", "Authentication successful"),
    }


def _refresh_from_request(body: RefreshBody | None, request: Request) -> str:
    token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise ApiError("UNAUTHENTICATED", "Missing refresh token", 401)
    return token


@router.post(
    "/auth/login",
    operation_id="loginAdmin",
    summary="管理員登入",
    status_code=200,
)
async def login_admin(body: LoginBody, request: Request, response: Response) -> dict:
    payload = await auth_service.login(
        email=body.email, password=body.password, allowed_roles=_ADMIN_WEB_ROLES
    )
    _set_login_cookies(response, payload)
    return _auth_response_payload(request, payload)


@router.post(
    "/technicians/login",
    operation_id="loginTechnician",
    summary="技師登入（手機號或 Email）",
    status_code=200,
)
async def login_technician(
    body: TechnicianLoginBody, request: Request, response: Response
) -> dict:
    # CR-0099：identifier 解析手機/email；手機多筆相符 → 409（改用 Email）。
    payload = await auth_service.login_with_identifier(
        body.identifier, body.password, allowed_roles=["technician"]
    )
    _set_login_cookies(response, payload)
    return _auth_response_payload(request, payload)


@router.post(
    "/auth/refresh",
    operation_id="refreshToken",
    summary="換發 access token",
    status_code=200,
)
async def refresh_token(
    request: Request,
    response: Response,
    body: RefreshBody | None = None,
) -> dict:
    payload = await auth_service.refresh(_refresh_from_request(body, request))
    _set_login_cookies(response, payload)
    return _auth_response_payload(request, payload)


@router.post(
    "/auth/logout",
    operation_id="logout",
    summary="登出",
    status_code=204,
)
async def logout(
    request: Request,
    body: LogoutBody | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    await auth_service.logout(
        access_jti=user.jti,
        access_user_id=user.user_id,
        access_exp_iso=None,
        refresh_token=(body.refresh_token if body else None)
        or request.cookies.get(REFRESH_COOKIE),
    )
    resp = Response(status_code=204)
    clear_session_cookies(resp)
    return resp


@router.post(
    "/auth/change-password",
    operation_id="changePassword",
    summary="變更密碼（需要當前密碼驗證）",
    status_code=204,
)
async def change_password(
    body: ChangePasswordBody,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    await auth_service.change_password(
        user_id=user.user_id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return Response(status_code=204)


@router.get(
    "/auth/session",
    operation_id="getBrowserSession",
    summary="由 HttpOnly cookie／Bearer 取得最小 session claims",
)
async def get_browser_session(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    return {
        "data": {
            "user_id": user.user_id,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    }


@router.get(
    "/auth/me",
    operation_id="getMyProfile",
    summary="取得目前登入者個人資料（自助）",
)
async def get_my_profile(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"data": await auth_service.get_profile(user_id=user.user_id)}


@router.patch(
    "/auth/me",
    operation_id="updateMyProfile",
    summary="更新目前登入者個人資料（display_name / phone）（自助）",
)
async def update_my_profile(
    body: UpdateProfileBody,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    return {
        "data": await auth_service.update_profile(
            user_id=user.user_id,
            display_name=body.display_name,
            phone=body.phone,
        )
    }


@router.post(
    "/auth/admin-reset-password",
    operation_id="adminResetPassword",
    summary="管理員代為重設使用者密碼（回傳臨時密碼,免 email）",
    status_code=200,
)
async def admin_reset_password(
    body: AdminResetPasswordBody,
    user: CurrentUser = Depends(role_required("admin")),
) -> dict:
    """admin 限定：重設同租戶使用者密碼為臨時密碼,回傳明文供轉達。

    機制由 2026-06-10 會議裁決（Action #7）：免 email 基礎設施。tenant_id 取自
    已認證 admin（role_required 已綁 require_tenant）,service 層限同租戶。
    """
    temp = await auth_service.admin_reset_password(
        email=body.email, tenant_id=user.tenant_id
    )
    return {"data": {"email": body.email, "temp_password": temp}}


@router.post(
    "/auth/request-password-reset",
    operation_id="requestPasswordReset",
    summary="申請密碼重設（自助，寄送重設連結到 email）",
    status_code=200,
)
async def request_password_reset(body: RequestPasswordResetBody, request: Request) -> dict:
    """自助忘記密碼 step 1（CR-0025 / ADR-0114）。

    **帳號枚舉防護**：不論 email 是否存在，一律回 200 同一訊息；實際是否寄出由
    service 端決定（不存在 / 停用 / rate-limit / SMTP 未配置皆安靜略過）。
    """
    client_ip = request.client.host if request.client else None
    await password_reset_service.request_reset(email=body.email, request_ip=client_ip)
    return {"data": None, "message": "若該帳號存在，重設連結已寄出，請於 30 分鐘內使用"}


@router.post(
    "/auth/confirm-password-reset",
    operation_id="confirmPasswordReset",
    summary="以重設 token 設定新密碼",
    status_code=204,
)
async def confirm_password_reset(body: ConfirmPasswordResetBody) -> Response:
    """自助忘記密碼 step 2：驗 token（未過期/未用）→ 設新密碼 → 標 token 已用。"""
    await password_reset_service.confirm_reset(token=body.token, new_password=body.new_password)
    return Response(status_code=204)


@router.post(
    "/technicians/register",
    operation_id="registerTechnician",
    summary="技師註冊",
    status_code=201,
)
async def register_technician(
    request: Request,
    body: TechnicianRegisterBody,
    idem: IdempotencyContext | None = Depends(_public_register_idem),
) -> dict:
    payload = await auth_service.register_technician(body.model_dump())
    if idem is not None:
        # CR-0115 §8-2a「token 明文不落庫」:idempotency cache 存品牌庫,不可
        # 收錄 upload_token 明文 → 存清洗副本(重放回應拿不到 token,屬可接受
        # 邊界;首個回應已送達 token)。
        sanitized = {
            **payload,
            "data": {**payload["data"], "upload_token": None},
        }
        await idem.save(201, sanitized)
    return payload


@router.post(
    "/technicians/registration-documents",
    operation_id="uploadTechnicianRegistrationDocument",
    summary="師傅註冊文件上傳（兩階段 token，CR-0115 §8-2a）",
    status_code=201,
)
async def upload_registration_document(
    request: Request,
    # UAT R3（契約 4）：不在 Form 層驗長度——格式不合法的 token 也要走
    # 403 UPLOAD_TOKEN_INVALID 統一回應（Form 驗證會變 422 VALIDATION_ERROR，
    # 前端失效畫面收不到 code）；長度檢查移到 _resolve_token。
    token: str = Form(description="註冊 response 回傳的一次性上傳 token"),
    doc_type: str = Form(description="id_front / id_back / license / insurance"),
    file: UploadFile = File(...),
) -> dict:
    """公開前帳號態文件上傳（Tier 3：身分證正反面/證照掃描/保險證明或良民證）。

    無登入態 —— 授權完全憑註冊時簽發的短期 token（48h、次數上限、師傅離開
    pending_approval 即失效）+ per-IP 限流。檔案與 metadata 落師傅身分域，
    不入品牌庫（§8-1 最小揭露）。
    """
    # 代理/Cloud Run 後 request.client 是 LB IP → 取 X-Forwarded-For 最左端，
    # 否則全部請求共用一個限流桶互相鎖死。
    forwarded = request.headers.get("x-forwarded-for", "")
    client_ip = (
        forwarded.split(",")[0].strip()
        or (request.client.host if request.client else None)
    )
    # 順序:先限流、再上限截讀 —— 不在任何檢查前把無上限 body 整包讀進記憶體。
    technician_kyc_service.rate_limit_check(client_ip)
    file_bytes = await file.read(technician_kyc_service.MAX_DOC_BYTES + 1)
    result = await technician_kyc_service.upload_registration_document(
        token=token,
        doc_type=doc_type,
        file_bytes=file_bytes,
        filename=file.filename or "",
        content_type=file.content_type,
        client_ip=None,  # 已在上方限流,不重複計數
    )
    return {"data": result}


# 公開 POST /vendors/register（registerVendor）已依 UAT R2 W3-2 業主裁決
# （2026-07-18）整條移除：廠商帳號改由平台代建（POST /platform/vendors，
# 建立即 active）。登入端點保留（代建帳號沿用 /vendors/login）。


@router.post(
    "/vendors/login",
    operation_id="loginVendor",
    summary="廠商/品牌商登入（發案者，CR-0029；與後台角色隔離）",
    status_code=200,
)
async def login_vendor(body: LoginBody, request: Request, response: Response) -> dict:
    payload = await auth_service.login(
        email=body.email, password=body.password, allowed_roles=["vendor"]
    )
    _set_login_cookies(response, payload)
    return _auth_response_payload(request, payload)
