"""Dependency injection for FastAPI routes."""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as get_database_session
from app.core.security import decode_token, get_current_user
from app.models.users import User

# ========================================================================
# DATABASE DEPENDENCIES
# ========================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    Yields:
        Database session
    """
    async for session in get_database_session():
        yield session


# ========================================================================
# REQUEST METADATA DEPENDENCIES
# ========================================================================


def get_client_ip(request: Request) -> str | None:
    """
    Extract client IP address from request.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address or None
    """
    # Check for forwarded IP first (if behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check for real IP (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct connection IP
    if request.client:
        return request.client.host

    return None


def get_user_agent(request: Request) -> str | None:
    """
    Extract user agent from request.

    Args:
        request: FastAPI request object

    Returns:
        User agent string or None
    """
    return request.headers.get("User-Agent")


def get_device_type(user_agent: str | None = Depends(get_user_agent)) -> str | None:
    """
    Determine device type from user agent.

    Args:
        user_agent: User agent string

    Returns:
        Device type: mobile, tablet, desktop, or None
    """
    if not user_agent:
        return None

    user_agent_lower = user_agent.lower()

    if any(mobile in user_agent_lower for mobile in ["mobile", "android", "iphone", "ipod"]):
        return "mobile"

    if any(tablet in user_agent_lower for tablet in ["ipad", "tablet"]):
        return "tablet"

    return "desktop"


# ========================================================================
# AUTHENTICATION DEPENDENCIES (from security.py)
# ========================================================================


# Re-export for convenience
async def get_current_active_user(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active authenticated user.

    Args:
        db: Database session
        current_user: Current user from token

    Returns:
        Current user instance
    """
    return current_user


# ========================================================================
# TEMP TOKEN DEPENDENCIES (for OTP stage)
# ========================================================================


async def get_temp_token_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get user from temporary token (used during OTP verification stage).
    Reads ONLY from HTTP-only cookie - NO Authorization header support.

    Args:
        request: FastAPI request (to read cookies)
        db: Database session

    Returns:
        User instance from temp token

    Raises:
        HTTPException: If token is invalid or not a temp token
    """
    # Read temp_token from HTTP-only cookie ONLY
    token = request.cookies.get("temp_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Temporary token not found in cookie. Please login again.",
        )

    payload = decode_token(token, expected_type="temporary")

    if payload.get("stage") != "password_change":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password-change session",
        )

    # Extract user info
    from uuid import UUID

    from sqlmodel import select

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user from database
    try:
        parsed_user_id = UUID(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        ) from exc

    statement = select(User).where(User.id == parsed_user_id)
    result = await db.execute(statement)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if payload.get("ver") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password-change session is no longer valid",
        )

    return user


# ========================================================================
# PAGINATION DEPENDENCIES
# ========================================================================


def get_pagination(
    page: int = 1,
    limit: int = 20,
) -> dict:
    """
    Common pagination parameters.

    Args:
        page: Page number (1-indexed)
        limit: Items per page

    Returns:
        Dict with skip and limit values
    """
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100

    skip = (page - 1) * limit

    return {
        "page": page,
        "limit": limit,
        "skip": skip,
    }
