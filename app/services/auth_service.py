"""Authentication, invitation, password, and persistent-session workflows."""

import logging
import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.core import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    create_temp_token,
    decode_token,
    generate_otp,
    generate_temporary_password,
    hash_otp,
    hash_password,
    hash_token,
    utcnow,
    validate_password_strength,
    verify_password,
)
from app.models.enums import OTPPurpose, UserRole
from app.models.users import User
from app.repositories.otp_repository import otp_repository
from app.repositories.session_repository import session_repository
from app.repositories.user_repository import user_repository
from app.schemas.auth import TokenPair, UserResponse
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoginOutcome:
    user: User
    password_change_required: bool
    temporary_token: str | None = None
    tokens: TokenPair | None = None


@dataclass(slots=True)
class ProvisionOutcome:
    user: User
    invitation_sent: bool


class AuthService:
    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _validate_new_password(password: str) -> None:
        valid, message = validate_password_strength(password)
        if not valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

    @staticmethod
    async def _require_admin_capacity(db: AsyncSession) -> None:
        """Serialize administrator changes and enforce the active-account ceiling."""

        admin_roles = (UserRole.SUPER_ADMIN, UserRole.ADMIN)
        await db.execute(
            select(User.id)
            .where(
                User.role.in_(admin_roles),
                User.deleted_at.is_(None),
            )
            .with_for_update()
        )
        active_admin_count = await db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role.in_(admin_roles),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        if int(active_admin_count or 0) >= settings.MAX_ADMIN_ACCOUNTS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"The maximum of {settings.MAX_ADMIN_ACCOUNTS} active administrator "
                    "accounts has been reached"
                ),
            )

    async def register_initial_admin(
        self,
        db: AsyncSession,
        *,
        secret_key: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone_number: str | None = None,
    ) -> User:
        expected_secret = settings.INITIAL_ADMIN_SECRET_KEY.get_secret_value()
        if not secrets.compare_digest(secret_key, expected_secret):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid setup secret")
        if await user_repository.check_super_admin_exists(db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Initial setup is complete")

        normalized_email = self.normalize_email(email)
        if await user_repository.get_user_by_email(db, normalized_email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
        self._validate_new_password(password)

        user = User(
            email=normalized_email,
            hashed_password=hash_password(password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            role=UserRole.SUPER_ADMIN,
            phone_number=phone_number,
            is_password_changed=True,
            is_email_verified=True,
            verified_at=utcnow(),
            last_password_change_at=utcnow(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def _issue_session(
        self,
        db: AsyncSession,
        user: User,
        *,
        ip_address: str | None,
        user_agent: str | None,
        device_type: str | None,
        session_id: UUID | None = None,
    ) -> TokenPair:
        sid = session_id or uuid4()
        access_token = create_access_token(
            user.id,
            user.email,
            user.role,
            session_id=sid,
            token_version=user.token_version,
        )
        refresh_token = create_refresh_token(
            user.id,
            session_id=sid,
            token_version=user.token_version,
        )

        if session_id:
            session = await session_repository.get_session_by_id(db, sid)
            if not session:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is unavailable")
            await session_repository.rotate_session_tokens(
                db,
                session=session,
                access_token_hash=hash_token(access_token),
                refresh_token_hash=hash_token(refresh_token),
                expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
                refresh_expires_in_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
            )
        else:
            await session_repository.create_session(
                db,
                session_id=sid,
                user_id=user.id,
                access_token_hash=hash_token(access_token),
                refresh_token_hash=hash_token(refresh_token),
                expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
                refresh_expires_in_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
                ip_address=ip_address,
                user_agent=user_agent,
                device_type=device_type,
            )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    async def login(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_type: str | None = None,
    ) -> LoginOutcome:
        normalized_email = self.normalize_email(email)
        user = await user_repository.get_user_by_email(db, normalized_email)
        if not user:
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if user.locked_until and user.locked_until > utcnow():
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account is temporarily locked")
        if not verify_password(password, user.hashed_password):
            await user_repository.increment_failed_login_attempts(db, user.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()

        if not user.is_password_changed:
            temporary_token = create_temp_token(
                user.id,
                user.email,
                stage="password_change",
                token_version=user.token_version,
            )
            return LoginOutcome(
                user=user,
                password_change_required=True,
                temporary_token=temporary_token,
            )

        tokens = await self._issue_session(
            db,
            user,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
        )
        user.last_login_at = utcnow()
        await db.commit()
        return LoginOutcome(user=user, password_change_required=False, tokens=tokens)

    async def first_time_password_change(
        self,
        db: AsyncSession,
        *,
        temporary_token: str,
        new_password: str,
        ip_address: str | None,
        user_agent: str | None,
        device_type: str | None,
    ) -> TokenPair:
        payload = decode_token(temporary_token, expected_type="temporary")
        if payload.get("stage") != "password_change":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password-change session"
            )
        try:
            user_id = UUID(payload["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password-change session"
            ) from exc

        user = await user_repository.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable"
            )
        if user.is_password_changed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Password has already been changed"
            )
        if payload.get("ver") != user.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Password-change session is no longer valid"
            )
        self._validate_new_password(new_password)
        if verify_password(new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New password must differ from the temporary password",
            )

        user.hashed_password = hash_password(new_password)
        user.is_password_changed = True
        user.is_email_verified = True
        user.verified_at = utcnow()
        user.token_version += 1
        user.last_password_change_at = utcnow()
        await session_repository.revoke_all_user_sessions(db, user.id)
        db.add(user)
        await db.commit()
        await db.refresh(user)

        tokens = await self._issue_session(
            db,
            user,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
        )
        user.last_login_at = utcnow()
        await db.commit()
        return tokens

    async def refresh_session(
        self,
        db: AsyncSession,
        *,
        refresh_token: str,
        ip_address: str | None,
        user_agent: str | None,
        device_type: str | None,
    ) -> TokenPair:
        payload = decode_token(refresh_token, expected_type="refresh")
        try:
            user_id = UUID(payload["sub"])
            session_id = UUID(payload["sid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token claims"
            ) from exc

        session = await session_repository.get_session_by_id(db, session_id, for_update=True)
        if not session or not session.is_active or session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is invalid")
        if not secrets.compare_digest(session.refresh_token_hash, hash_token(refresh_token)):
            await session_repository.revoke_session(db, session)
            logger.warning("Refresh-token replay detected for session %s", session_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected"
            )
        if session.refresh_expires_at <= utcnow():
            await session_repository.revoke_session(db, session)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session has expired"
            )

        user = await user_repository.get_user_by_id(db, user_id)
        if (
            not user
            or not user.is_active
            or not user.is_password_changed
            or payload.get("ver") != user.token_version
        ):
            await session_repository.revoke_session(db, session)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User session is unavailable"
            )

        return await self._issue_session(
            db,
            user,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
        )

    async def logout(self, db: AsyncSession, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
            session_id = UUID(payload["sid"])
        except (HTTPException, KeyError, TypeError, ValueError):
            return
        session = await session_repository.get_session_by_id(db, session_id)
        if session:
            await session_repository.revoke_session(db, session)

    async def change_password(
        self,
        db: AsyncSession,
        *,
        user: User,
        current_password: str,
        new_password: str,
        ip_address: str | None,
        user_agent: str | None,
        device_type: str | None,
    ) -> TokenPair:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect"
            )
        self._validate_new_password(new_password)
        if verify_password(new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be different"
            )

        user.hashed_password = hash_password(new_password)
        user.token_version += 1
        user.last_password_change_at = utcnow()
        await session_repository.revoke_all_user_sessions(db, user.id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return await self._issue_session(
            db,
            user,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
        )

    async def forgot_password(self, db: AsyncSession, email: str) -> None:
        user = await user_repository.get_user_by_email(db, self.normalize_email(email))
        if not user or not user.is_active:
            return
        recent_count = await otp_repository.get_recent_otp_count(
            db,
            user.id,
            OTPPurpose.PASSWORD_RESET,
            settings.OTP_RATE_WINDOW_MINUTES,
        )
        if recent_count >= settings.OTP_RATE_LIMIT:
            return

        code = generate_otp()
        otp = await otp_repository.create_otp(
            db,
            user_id=user.id,
            hashed_code=hash_otp(code),
            purpose=OTPPurpose.PASSWORD_RESET,
            expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        )
        sent = await email_service.send_password_reset_code(
            email=user.email,
            full_name=user.full_name,
            code=code,
        )
        if not sent:
            otp.is_active = False
            db.add(otp)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password reset email could not be sent",
            )

    async def reset_password(
        self,
        db: AsyncSession,
        *,
        email: str,
        otp_code: str,
        new_password: str,
    ) -> None:
        user = await user_repository.get_user_by_email(db, self.normalize_email(email))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password reset request"
            )
        self._validate_new_password(new_password)
        otp = await otp_repository.get_valid_otp(db, user.id, OTPPurpose.PASSWORD_RESET)
        code_matches = bool(otp and secrets.compare_digest(otp.hashed_code, hash_otp(otp_code)))
        if not otp or not code_matches or otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            if otp and otp.attempts < settings.OTP_MAX_ATTEMPTS:
                await otp_repository.increment_otp_attempt(db, otp)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code"
            )
        if verify_password(new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be different"
            )

        otp.mark_as_used()
        db.add(otp)
        user.hashed_password = hash_password(new_password)
        user.is_password_changed = True
        user.token_version += 1
        user.last_password_change_at = utcnow()
        await session_repository.revoke_all_user_sessions(db, user.id)
        db.add(user)
        await db.commit()

    async def provision_user(
        self,
        db: AsyncSession,
        *,
        creator: User,
        email: str,
        first_name: str,
        last_name: str,
        role: UserRole,
        phone_number: str | None,
        employee_id: str | None,
        agent_code: str | None,
        branch_id: str | None,
        department: str | None,
    ) -> ProvisionOutcome:
        if creator.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
        if role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Super administrators cannot be invited",
            )
        if role == UserRole.ADMIN:
            await self._require_admin_capacity(db)
        normalized_email = self.normalize_email(email)
        identifier = agent_code or employee_id
        conflicts = [func.lower(User.email) == normalized_email]
        if phone_number:
            conflicts.append(User.phone_number == phone_number)
        if identifier:
            conflicts.append(or_(User.employee_id == identifier, User.agent_code == identifier))
        conflict_result = await db.execute(select(User).where(or_(*conflicts)))
        conflict = conflict_result.scalars().first()
        if conflict:
            if conflict.email.lower() == normalized_email:
                detail = "Email is already registered"
            elif phone_number and conflict.phone_number == phone_number:
                detail = "Phone number is already assigned to another user"
            else:
                detail = "Employee or agent code is already assigned to another user"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

        temporary_password = generate_temporary_password()
        user = User(
            email=normalized_email,
            hashed_password=hash_password(temporary_password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            role=role,
            phone_number=phone_number,
            employee_id=employee_id,
            agent_code=agent_code,
            branch_id=branch_id,
            department=department,
            created_by_id=creator.id,
            is_active=True,
            is_email_verified=False,
            is_password_changed=False,
        )
        db.add(user)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email, phone number, or personnel code is already in use",
            ) from exc
        await db.refresh(user)

        sent = await email_service.send_temporary_password(
            email=user.email,
            full_name=user.full_name,
            temporary_password=temporary_password,
        )
        if not sent:
            logger.warning(
                "User %s was created, but temporary credentials could not be delivered",
                user.email,
            )
        return ProvisionOutcome(user=user, invitation_sent=sent)

    async def resend_invitation(self, db: AsyncSession, *, creator: User, user_id: UUID) -> User:
        if creator.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
        if not settings.smtp_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Email delivery is not configured"
            )
        user = await user_repository.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if user.is_password_changed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="User has already activated the account"
            )

        temporary_password = generate_temporary_password()
        user.hashed_password = hash_password(temporary_password)
        user.token_version += 1
        db.add(user)
        await db.flush()
        sent = await email_service.send_temporary_password(
            email=user.email,
            full_name=user.full_name,
            temporary_password=temporary_password,
        )
        if not sent:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Credentials email could not be sent"
            )
        await db.commit()
        await db.refresh(user)
        return user

    async def set_user_status(
        self,
        db: AsyncSession,
        *,
        creator: User,
        user_id: UUID,
        is_active: bool,
    ) -> User:
        if creator.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
        user = await user_repository.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if user.id == creator.id and not is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="You cannot deactivate your own account",
            )
        if user.role == UserRole.SUPER_ADMIN and creator.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a super administrator can update this account",
            )
        if (
            is_active
            and not user.is_active
            and user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
        ):
            await self._require_admin_capacity(db)

        user.is_active = is_active
        if not is_active:
            user.token_version += 1
            await session_repository.revoke_all_user_sessions(db, user.id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


auth_service = AuthService()
