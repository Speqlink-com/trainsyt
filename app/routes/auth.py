"""Cookie-based authentication and administrator invitation routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.core import settings
from app.core.dependencies import get_client_ip, get_db, get_device_type, get_user_agent
from app.core.security import generate_csrf_token, get_current_user, validate_csrf
from app.models.enums import UserRole
from app.models.users import User
from app.repositories.user_repository import user_repository
from app.schemas.auth import (
    AdminCreateUserRequest,
    FirstTimePasswordChangeRequest,
    InitialAdminRegisterRequest,
    LoginRequest,
    OTPSendRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    TokenPair,
    UserStatusUpdateRequest,
)
from app.services.auth_service import auth_service

router = APIRouter()
logger = logging.getLogger(__name__)


def user_data(user: object) -> dict:
    role = user.role
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": getattr(user, "phone_number", None),
        "profile_pic_url": getattr(user, "profile_pic_url", None),
        "role": role.value if isinstance(role, UserRole) else role,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "is_password_changed": user.is_password_changed,
        "employee_id": getattr(user, "employee_id", None),
        "branch_id": getattr(user, "branch_id", None),
        "department": getattr(user, "department", None),
        "agent_code": getattr(user, "agent_code", None),
        "territory": getattr(user, "territory", None),
        "specializations": getattr(user, "specializations", None),
        "date_appointed": (
            user.date_appointed.isoformat() if getattr(user, "date_appointed", None) else None
        ),
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        "updated_at": user.updated_at.isoformat() if getattr(user, "updated_at", None) else None,
        "last_login_at": (user.last_login_at.isoformat() if getattr(user, "last_login_at", None) else None),
    }


def set_cookie(
    response: JSONResponse,
    *,
    key: str,
    value: str,
    max_age: int,
    httponly: bool = True,
) -> None:
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        httponly=httponly,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def delete_cookie(response: JSONResponse, key: str) -> None:
    response.delete_cookie(
        key=key,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def set_session_cookies(response: JSONResponse, tokens: TokenPair) -> None:
    set_cookie(
        response,
        key="access_token",
        value=tokens.access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    set_cookie(
        response,
        key="refresh_token",
        value=tokens.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    delete_cookie(response, "temp_token")
    set_csrf_cookie(response)


def set_csrf_cookie(response: JSONResponse) -> None:
    set_cookie(
        response,
        key=settings.CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=False,
    )


def clear_auth_cookies(response: JSONResponse) -> None:
    delete_cookie(response, "access_token")
    delete_cookie(response, "refresh_token")
    delete_cookie(response, "temp_token")
    delete_cookie(response, settings.CSRF_COOKIE_NAME)


@router.post("/register-initial-admin", status_code=status.HTTP_201_CREATED)
async def register_initial_admin(
    payload: InitialAdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.register_initial_admin(
        db,
        secret_key=payload.secret_key,
        email=str(payload.email),
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_number=payload.phone_number,
    )
    return {"success": True, "message": "Initial administrator created", "data": {"user": user_data(user)}}


@router.post("/login")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    ip_address: str | None = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
    device_type: str | None = Depends(get_device_type),
):
    outcome = await auth_service.login(
        db,
        email=str(payload.email),
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
        device_type=device_type,
    )

    if outcome.password_change_required and outcome.temporary_token:
        response = JSONResponse(
            content={
                "success": True,
                "message": "Password change required",
                "data": {"password_change_required": True},
            }
        )
        clear_auth_cookies(response)
        set_cookie(
            response,
            key="temp_token",
            value=outcome.temporary_token,
            max_age=settings.TEMP_TOKEN_EXPIRE_MINUTES * 60,
        )
        set_csrf_cookie(response)
        return response

    if not outcome.tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Session could not be created"
        )
    response = JSONResponse(
        content={
            "success": True,
            "message": "Login successful",
            "data": {"password_change_required": False, "user": user_data(outcome.user)},
        }
    )
    set_session_cookies(response, outcome.tokens)
    return response


@router.post("/first-time-password-change")
async def first_time_password_change(
    payload: FirstTimePasswordChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ip_address: str | None = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
    device_type: str | None = Depends(get_device_type),
    _: None = Depends(validate_csrf),
):
    temporary_token = request.cookies.get("temp_token")
    if not temporary_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password-change session is missing or expired"
        )
    tokens = await auth_service.first_time_password_change(
        db,
        temporary_token=temporary_token,
        new_password=payload.new_password,
        ip_address=ip_address,
        user_agent=user_agent,
        device_type=device_type,
    )
    response = JSONResponse(
        content={
            "success": True,
            "message": "Password changed successfully",
            "data": {"user": user_data(tokens.user)},
        }
    )
    set_session_cookies(response, tokens)
    return response


@router.post("/refresh")
async def refresh_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ip_address: str | None = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
    device_type: str | None = Depends(get_device_type),
    _: None = Depends(validate_csrf),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is missing")
    try:
        tokens = await auth_service.refresh_session(
            db,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
        )
    except HTTPException as exc:
        response = JSONResponse(
            status_code=exc.status_code, content={"success": False, "message": exc.detail}
        )
        clear_auth_cookies(response)
        return response
    response = JSONResponse(
        content={
            "success": True,
            "message": "Session refreshed",
            "data": {"user": user_data(tokens.user)},
        }
    )
    set_session_cookies(response, tokens)
    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    await auth_service.logout(db, request.cookies.get("refresh_token"))
    response = JSONResponse(content={"success": True, "message": "Logged out successfully"})
    clear_auth_cookies(response)
    return response


@router.get("/check-auth")
async def check_auth(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "message": "Authenticated",
        "data": {"user": user_data(current_user)},
    }


@router.put("/change-password")
async def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ip_address: str | None = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
    device_type: str | None = Depends(get_device_type),
    _: None = Depends(validate_csrf),
):
    tokens = await auth_service.change_password(
        db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip_address=ip_address,
        user_agent=user_agent,
        device_type=device_type,
    )
    response = JSONResponse(content={"success": True, "message": "Password changed successfully"})
    set_session_cookies(response, tokens)
    return response


@router.post("/forgot-password")
async def forgot_password(payload: OTPSendRequest, db: AsyncSession = Depends(get_db)):
    try:
        await auth_service.forgot_password(db, str(payload.email))
    except HTTPException as exc:
        if exc.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
            raise
        logger.error("Password reset email delivery failed")
    return {
        "success": True,
        "message": "If the account exists, a password reset code has been sent",
    }


@router.post("/reset-password")
async def reset_password(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(
        db,
        email=str(payload.email),
        otp_code=payload.otp_code,
        new_password=payload.new_password,
    )
    return {"success": True, "message": "Password reset successfully"}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminCreateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    outcome = await auth_service.provision_user(
        db,
        creator=current_user,
        email=str(payload.email),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
        phone_number=payload.phone_number,
        employee_id=payload.employee_id,
        branch_id=payload.branch_id,
        department=payload.department,
    )
    return {
        "success": True,
        "message": (
            "User created and temporary credentials emailed"
            if outcome.invitation_sent
            else "User created, but the credentials email was not delivered. Resend the invitation after email service is restored."
        ),
        "data": {
            "user": user_data(outcome.user),
            "invitation_sent": outcome.invitation_sent,
        },
    }


@router.post("/users/{user_id}/resend-invitation")
async def resend_invitation(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    user = await auth_service.resend_invitation(db, creator=current_user, user_id=user_id)
    return {
        "success": True,
        "message": "A new temporary password has been emailed",
        "data": {"user": user_data(user)},
    }


@router.get("/users")
async def list_users(
    search: str = Query(default="", max_length=100),
    role: UserRole | None = None,
    active_only: bool = True,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    users, total = await user_repository.search_users(
        db,
        search_term=search.strip(),
        roles=[role] if role else None,
        active_only=active_only,
        skip=(page - 1) * limit,
        limit=limit,
    )
    return {
        "success": True,
        "data": {
            "users": [user_data(user) for user in users],
            "page": page,
            "limit": limit,
            "total": total,
        },
    }


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    user = await auth_service.set_user_status(
        db,
        creator=current_user,
        user_id=user_id,
        is_active=payload.is_active,
    )
    return {
        "success": True,
        "message": "User activated" if user.is_active else "User deactivated",
        "data": {"user": user_data(user)},
    }
