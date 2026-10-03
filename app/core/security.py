"""Password, JWT, and authenticated-session security utilities."""

import hashlib
import hmac
import logging
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.core import settings
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.sessions import Session
from app.models.users import User

logger = logging.getLogger(__name__)
TokenType = Literal["access", "refresh", "temporary", "attendance"]


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (TypeError, ValueError):
        return False


# Used only to make unknown-email logins perform the same expensive password
# check as known accounts. It is generated once when the worker starts.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def generate_temporary_password(length: int = 16) -> str:
    if length < 12:
        raise ValueError("Temporary passwords must contain at least 12 characters")
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    password.extend(secrets.choice(characters) for _ in range(length - len(password)))
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    if len(password) < 10:
        return False, "Password must be at least 10 characters long"
    if not any(character.isupper() for character in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(character.islower() for character in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(character.isdigit() for character in password):
        return False, "Password must contain at least one digit"
    if not any(character in "!@#$%^&*()-_=+[]{}|;:,.<>?/" for character in password):
        return False, "Password must contain at least one special character"
    return True, None


def _encode_token(payload: dict, token_type: TokenType) -> str:
    type_headers = {
        "access": "at+jwt",
        "refresh": "rt+jwt",
        "temporary": "temp+jwt",
        "attendance": "attendance+jwt",
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
        headers={"typ": type_headers[token_type]},
    )


def _base_claims(*, user_id: UUID, token_type: TokenType, expires_delta: timedelta) -> dict:
    now = datetime.now(UTC)
    return {
        "sub": str(user_id),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + expires_delta,
        "jti": str(uuid4()),
        "type": token_type,
    }


def create_access_token(
    user_id: UUID,
    email: str,
    role: UserRole,
    *,
    session_id: UUID,
    token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    payload = _base_claims(
        user_id=user_id,
        token_type="access",
        expires_delta=expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    payload.update(
        {
            "email": email,
            "role": role.value if isinstance(role, UserRole) else role,
            "sid": str(session_id),
            "ver": token_version,
        }
    )
    return _encode_token(payload, "access")


def create_refresh_token(
    user_id: UUID,
    *,
    session_id: UUID,
    token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    payload = _base_claims(
        user_id=user_id,
        token_type="refresh",
        expires_delta=expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    payload.update({"sid": str(session_id), "ver": token_version})
    return _encode_token(payload, "refresh")


def create_temp_token(
    user_id: UUID,
    email: str,
    *,
    stage: str,
    token_version: int,
    expires_minutes: int | None = None,
) -> str:
    payload = _base_claims(
        user_id=user_id,
        token_type="temporary",
        expires_delta=timedelta(minutes=expires_minutes or settings.TEMP_TOKEN_EXPIRE_MINUTES),
    )
    payload.update({"email": email, "stage": stage, "ver": token_version})
    return _encode_token(payload, "temporary")


def create_attendance_token(
    registration_id: UUID,
    *,
    training_id: UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived bearer receipt for public attendance confirmation."""

    payload = _base_claims(
        user_id=registration_id,
        token_type="attendance",
        expires_delta=expires_delta or timedelta(hours=settings.ATTENDANCE_TOKEN_EXPIRE_HOURS),
    )
    payload.update({"tid": str(training_id)})
    return _encode_token(payload, "attendance")


def decode_token(token: str, *, expected_type: TokenType | None = None) -> dict:
    type_headers = {
        "access": "at+jwt",
        "refresh": "rt+jwt",
        "temporary": "temp+jwt",
        "attendance": "attendance+jwt",
    }
    try:
        header = jwt.get_unverified_header(token)
        if expected_type and header.get("typ") != type_headers[expected_type]:
            raise jwt.InvalidTokenError("JWT typ header does not match the expected token type")
        required_claims = ["sub", "iss", "aud", "iat", "nbf", "exp", "jti", "type"]
        if expected_type in {"access", "refresh"}:
            required_claims.extend(["sid", "ver"])
        if expected_type == "temporary":
            required_claims.extend(["stage", "ver"])
        if expected_type == "attendance":
            required_claims.append("tid")
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            leeway=settings.JWT_LEEWAY_SECONDS,
            options={"require": required_claims},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        logger.warning("Rejected invalid JWT: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if expected_type and payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_otp(code: str) -> str:
    return hmac.new(
        settings.JWT_SECRET.get_secret_value().encode("utf-8"),
        f"otp:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def validate_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    header_token = request.headers.get(settings.CSRF_HEADER_NAME)
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def generate_otp(length: int | None = None) -> str:
    code_length = length or settings.OTP_LENGTH
    return "".join(str(secrets.randbelow(10)) for _ in range(code_length))


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(token, expected_type="access")
    try:
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims") from exc

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalars().first()
    if (
        not session
        or not session.is_active
        or session.user_id != user_id
        or session.expires_at <= utcnow()
        or not secrets.compare_digest(session.access_token_hash, hash_token(token))
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired")

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable")
    if payload.get("ver") != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")
    if not user.is_password_changed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    return user
