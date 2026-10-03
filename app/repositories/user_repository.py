"""User repository for managing user operations."""

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import or_, select

from app.core.core import settings
from app.models.base import naive_utcnow
from app.models.enums import UserRole
from app.models.users import User

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user management operations."""

    async def create_user(
        self,
        db: AsyncSession,
        *,
        email: str,
        hashed_password: str,
        first_name: str,
        last_name: str,
        role: UserRole,
        phone_number: str | None = None,
        employee_id: str | None = None,
        branch_id: str | None = None,
        department: str | None = None,
        agent_code: str | None = None,
        created_by_id: UUID | None = None,
    ) -> User:
        """Create a new user."""

        user = User(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone_number=phone_number,
            employee_id=employee_id,
            branch_id=branch_id,
            department=department,
            agent_code=agent_code,
            created_by_id=created_by_id,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Created user: {email} with role {role}")
        return user

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> User | None:
        """Get user by ID."""

        statement = select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
        result = await db.execute(statement)
        return result.scalars().first()

    async def get_user_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> User | None:
        """Get user by email."""

        statement = select(User).where(
            func.lower(User.email) == email.strip().lower(),
            User.deleted_at.is_(None),
        )
        result = await db.execute(statement)
        return result.scalars().first()

    async def get_user_by_employee_id(
        self,
        db: AsyncSession,
        employee_id: str,
    ) -> User | None:
        """Get user by employee ID."""

        statement = select(User).where(
            User.employee_id == employee_id,
            User.deleted_at.is_(None),
        )
        result = await db.execute(statement)
        return result.scalars().first()

    async def get_user_by_agent_code(
        self,
        db: AsyncSession,
        agent_code: str,
    ) -> User | None:
        """Get user by agent code."""

        statement = select(User).where(
            User.agent_code == agent_code,
            User.deleted_at.is_(None),
        )
        result = await db.execute(statement)
        return result.scalars().first()

    async def get_users_by_role(
        self,
        db: AsyncSession,
        role: UserRole,
        active_only: bool = True,
    ) -> list[User]:
        """Get users by role."""

        statement = select(User).where(
            User.role == role,
            User.deleted_at.is_(None),
        )

        if active_only:
            statement = statement.where(User.is_active.is_(True))

        statement = statement.order_by(User.first_name, User.last_name)

        result = await db.execute(statement)
        return list(result.scalars().all())

    async def get_agents_by_sm(
        self,
        db: AsyncSession,
        sm_id: UUID,
        active_only: bool = True,
    ) -> list[User]:
        """Get agents assigned to a Sales Manager."""

        statement = select(User).where(
            User.role == UserRole.AGENT,
            User.sm_id == sm_id,
            User.deleted_at.is_(None),
        )

        if active_only:
            statement = statement.where(User.is_active.is_(True))

        statement = statement.order_by(User.first_name, User.last_name)

        result = await db.execute(statement)
        return list(result.scalars().all())

    async def get_agents_by_hoa(
        self,
        db: AsyncSession,
        hoa_id: UUID,
        active_only: bool = True,
    ) -> list[User]:
        """Get agents assigned to an HOA."""

        statement = select(User).where(
            User.role == UserRole.AGENT,
            User.hoa_id == hoa_id,
            User.deleted_at.is_(None),
        )

        if active_only:
            statement = statement.where(User.is_active.is_(True))

        statement = statement.order_by(User.first_name, User.last_name)

        result = await db.execute(statement)
        return list(result.scalars().all())

    async def update_last_login(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> None:
        """Update user's last login timestamp."""

        user = await self.get_user_by_id(db, user_id)
        if user:
            user.last_login_at = naive_utcnow()
            user.failed_login_attempts = 0  # Reset failed attempts on successful login
            user.locked_until = None  # Clear any lock
            await db.commit()
            logger.info(f"Updated last login for user {user_id}")

    async def update_password(
        self,
        db: AsyncSession,
        user_id: UUID,
        new_hashed_password: str,
    ) -> None:
        """Update user's password."""

        user = await self.get_user_by_id(db, user_id)
        if user:
            user.hashed_password = new_hashed_password
            user.last_password_change_at = naive_utcnow()
            user.is_password_changed = True
            await db.commit()
            logger.info(f"Updated password for user {user_id}")

    async def increment_failed_login_attempts(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """Increment failed login attempts and return new count."""

        user = await self.get_user_by_id(db, user_id)
        if user:
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
                user.locked_until = naive_utcnow() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                logger.warning(f"User {user_id} account locked due to failed login attempts")

            await db.commit()
            return user.failed_login_attempts

        return 0

    async def check_super_admin_exists(
        self,
        db: AsyncSession,
    ) -> bool:
        """Check if any Super Admin exists."""

        statement = select(User).where(
            User.role == UserRole.SUPER_ADMIN,
            User.deleted_at.is_(None),
        )
        result = await db.execute(statement)
        return result.scalars().first() is not None

    async def search_users(
        self,
        db: AsyncSession,
        search_term: str,
        roles: list[UserRole] | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        """Search users with pagination."""

        # Build base query
        statement = select(User).where(User.deleted_at.is_(None))

        if active_only:
            statement = statement.where(User.is_active.is_(True))

        if roles:
            statement = statement.where(User.role.in_(roles))

        # Add search conditions
        if search_term:
            search_filter = or_(
                User.first_name.ilike(f"%{search_term}%"),
                User.last_name.ilike(f"%{search_term}%"),
                User.email.ilike(f"%{search_term}%"),
                User.employee_id.ilike(f"%{search_term}%"),
                User.agent_code.ilike(f"%{search_term}%"),
            )
            statement = statement.where(search_filter)

        # Get total count
        count_result = await db.execute(select(func.count()).select_from(statement.subquery()))
        total = int(count_result.scalar_one())

        # Get paginated results
        statement = statement.order_by(User.first_name, User.last_name)
        statement = statement.offset(skip).limit(limit)

        result = await db.execute(statement)
        users = list(result.scalars().all())

        return users, total


# Create repository instance
user_repository = UserRepository()
