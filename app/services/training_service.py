"""Training programme, public QR registration, and attendance workflows."""

import secrets
from datetime import UTC
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import create_attendance_token, decode_token, utcnow
from app.models.enums import ParticipantRole, TrainingStatus, UserRole
from app.models.trainings import Training, TrainingAttendance, TrainingRegistration
from app.models.users import User
from app.schemas.training import (
    AttendanceConfirmationResponse,
    AttendanceRowResponse,
    PublicRegistrationRequest,
    PublicTrainingResponse,
    RegistrationResponse,
    TrainerOptionResponse,
    TrainingCreateRequest,
    TrainingResponse,
    TrainingStatusUpdateRequest,
    TrainingUpdateRequest,
)

MANAGER_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.TRAINER}
ADMIN_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


def user_participant_role(role: UserRole) -> ParticipantRole:
    if role in ADMIN_ROLES:
        return ParticipantRole.ADMIN
    return ParticipantRole(role.value)


class TrainingService:
    @staticmethod
    def _require_manager(user: User) -> None:
        if user.role not in MANAGER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Trainer or administrator access required",
            )

    @staticmethod
    def _can_manage_training(user: User, training: Training) -> bool:
        return user.role in ADMIN_ROLES or (user.role == UserRole.TRAINER and training.trainer_id == user.id)

    def _require_training_manager(self, user: User, training: Training) -> None:
        self._require_manager(user)
        if not self._can_manage_training(user, training):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage programmes assigned to you",
            )

    @staticmethod
    async def _get_training(db: AsyncSession, training_id: UUID) -> Training:
        training = await db.get(Training, training_id)
        if not training:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training not found")
        return training

    @staticmethod
    async def _get_training_for_update(db: AsyncSession, training_id: UUID) -> Training:
        result = await db.execute(
            select(Training).where(Training.id == training_id).with_for_update()
        )
        training = result.scalars().first()
        if not training:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training not found")
        return training

    @staticmethod
    async def _trainer(db: AsyncSession, trainer_id: UUID) -> User:
        trainer = await db.get(User, trainer_id)
        if not trainer or not trainer.is_active or trainer.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Trainer is unavailable"
            )
        if trainer.role != UserRole.TRAINER:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The assigned user must have the trainer role",
            )
        return trainer

    @staticmethod
    async def _counts(db: AsyncSession, training_id: UUID) -> tuple[int, int]:
        registration_count = await db.scalar(
            select(func.count())
            .select_from(TrainingRegistration)
            .where(TrainingRegistration.training_id == training_id)
        )
        attendance_count = await db.scalar(
            select(func.count())
            .select_from(TrainingAttendance)
            .where(TrainingAttendance.training_id == training_id)
        )
        return int(registration_count or 0), int(attendance_count or 0)

    async def _response(self, db: AsyncSession, training: Training) -> TrainingResponse:
        trainer = await db.get(User, training.trainer_id)
        registrations, attendance = await self._counts(db, training.id)
        return TrainingResponse(
            id=training.id,
            public_code=training.public_code,
            title=training.title,
            description=training.description,
            trainer_id=training.trainer_id,
            trainer_name=trainer.full_name if trainer else "Unassigned",
            scheduled_at=training.scheduled_at,
            duration_hours=training.duration_hours,
            location=training.location,
            audience_roles=[ParticipantRole(role) for role in training.audience_roles],
            capacity=training.capacity,
            status=training.status,
            attendance_open=training.attendance_open,
            registration_count=registrations,
            attendance_count=attendance,
            created_at=training.created_at,
            updated_at=training.updated_at,
        )

    async def create_training(
        self,
        db: AsyncSession,
        *,
        creator: User,
        payload: TrainingCreateRequest,
    ) -> TrainingResponse:
        self._require_manager(creator)
        if creator.role == UserRole.TRAINER:
            trainer_id = creator.id
        elif payload.trainer_id:
            trainer_id = payload.trainer_id
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An administrator must assign a trainer",
            )
        await self._trainer(db, trainer_id)

        scheduled_at = (
            payload.scheduled_at.astimezone(UTC).replace(tzinfo=None)
            if payload.scheduled_at.tzinfo
            else payload.scheduled_at
        )
        if scheduled_at <= utcnow():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Programme date and time must be in the future",
            )

        training = Training(
            public_code=secrets.token_urlsafe(18),
            title=payload.title,
            description=payload.description,
            trainer_id=trainer_id,
            created_by_id=creator.id,
            scheduled_at=scheduled_at,
            duration_hours=payload.duration_hours,
            location=payload.location,
            audience_roles=[role.value for role in payload.audience_roles],
            capacity=payload.capacity,
            status=TrainingStatus.SCHEDULED,
            attendance_open=True,
        )
        db.add(training)
        await db.commit()
        await db.refresh(training)
        return await self._response(db, training)

    async def list_trainings(self, db: AsyncSession, *, current_user: User) -> list[TrainingResponse]:
        statement = select(Training).order_by(Training.scheduled_at.desc())
        if current_user.role == UserRole.TRAINER:
            statement = statement.where(Training.trainer_id == current_user.id)
        result = await db.execute(statement)
        trainings = list(result.scalars().all())

        if current_user.role not in MANAGER_ROLES:
            participant_role = user_participant_role(current_user.role).value
            trainings = [training for training in trainings if participant_role in training.audience_roles]
        return [await self._response(db, training) for training in trainings]

    async def get_training_for_user(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        training_id: UUID,
    ) -> TrainingResponse:
        training = await self._get_training(db, training_id)
        if current_user.role == UserRole.TRAINER and training.trainer_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Training is not assigned to you"
            )
        if current_user.role not in MANAGER_ROLES:
            participant_role = user_participant_role(current_user.role).value
            if participant_role not in training.audience_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Training is not assigned to your role"
                )
        return await self._response(db, training)

    async def update_status(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        training_id: UUID,
        payload: TrainingStatusUpdateRequest,
    ) -> TrainingResponse:
        training = await self._get_training_for_update(db, training_id)
        self._require_training_manager(current_user, training)
        if payload.status is not None:
            training.status = payload.status
            if payload.status in {TrainingStatus.COMPLETED, TrainingStatus.CANCELLED}:
                training.attendance_open = False
        if payload.attendance_open is not None:
            if (
                training.status in {TrainingStatus.COMPLETED, TrainingStatus.CANCELLED}
                and payload.attendance_open
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Attendance cannot be reopened for a completed or cancelled programme",
                )
            training.attendance_open = payload.attendance_open
        db.add(training)
        try:
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The programme status could not be saved",
            ) from exc
        await db.refresh(training)
        return await self._response(db, training)

    async def update_training(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        training_id: UUID,
        payload: TrainingUpdateRequest,
    ) -> TrainingResponse:
        if current_user.role not in ADMIN_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access required",
            )
        training = await self._get_training_for_update(db, training_id)

        if payload.expected_updated_at is not None:
            expected_updated_at = payload.expected_updated_at.astimezone(UTC).replace(tzinfo=None)
            if expected_updated_at != training.updated_at:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This programme was changed by another administrator. Reload and try again.",
                )

        if "trainer_id" in payload.model_fields_set and payload.trainer_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A training programme must have an assigned trainer",
            )

        if payload.trainer_id is not None and payload.trainer_id != training.trainer_id:
            await self._trainer(db, payload.trainer_id)
            training.trainer_id = payload.trainer_id
            training.trainer_reminder_sent_at = None

        reset_participant_reminders = False
        if payload.scheduled_at is not None:
            scheduled_at = payload.scheduled_at.astimezone(UTC).replace(tzinfo=None)
            if scheduled_at != training.scheduled_at:
                if scheduled_at <= utcnow():
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="A changed programme date and time must be in the future",
                    )
                training.scheduled_at = scheduled_at
                training.trainer_reminder_sent_at = None
                reset_participant_reminders = True

        if payload.capacity is not None:
            registration_count, _ = await self._counts(db, training.id)
            if payload.capacity < registration_count:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Capacity cannot be lower than the current registration count",
                )
            training.capacity = payload.capacity

        if payload.audience_roles is not None:
            registered_roles_result = await db.execute(
                select(TrainingRegistration.role)
                .where(TrainingRegistration.training_id == training.id)
                .distinct()
            )
            registered_roles = set(registered_roles_result.scalars().all())
            requested_roles = set(payload.audience_roles)
            if not registered_roles.issubset(requested_roles):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Audience roles cannot exclude participants who are already registered",
                )
            training.audience_roles = [role.value for role in payload.audience_roles]

        for field in ("title", "description", "duration_hours", "location"):
            value = getattr(payload, field)
            if value is not None and value != getattr(training, field):
                setattr(training, field, value)
                if field in {"title", "location"}:
                    training.trainer_reminder_sent_at = None
                    reset_participant_reminders = True

        next_status = payload.status if payload.status is not None else training.status
        next_attendance_open = (
            payload.attendance_open
            if payload.attendance_open is not None
            else training.attendance_open
        )
        if next_status in {TrainingStatus.COMPLETED, TrainingStatus.CANCELLED}:
            if payload.attendance_open is True:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Attendance cannot be opened for a completed or cancelled programme",
                )
            next_attendance_open = False
        training.status = next_status
        training.attendance_open = next_attendance_open

        if reset_participant_reminders:
            await db.execute(
                update(TrainingRegistration)
                .where(TrainingRegistration.training_id == training.id)
                .values(reminder_sent_at=None)
            )
        db.add(training)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The programme conflicts with existing training data",
            ) from exc
        except SQLAlchemyError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The programme update could not be saved",
            ) from exc
        await db.refresh(training)
        return await self._response(db, training)

    async def delete_training(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        training_id: UUID,
    ) -> tuple[int, int]:
        if current_user.role not in ADMIN_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access required",
            )
        training = await self._get_training_for_update(db, training_id)
        registration_count, attendance_count = await self._counts(db, training.id)
        try:
            await db.execute(
                delete(TrainingAttendance).where(TrainingAttendance.training_id == training.id)
            )
            await db.execute(
                delete(TrainingRegistration).where(TrainingRegistration.training_id == training.id)
            )
            await db.delete(training)
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The programme could not be deleted",
            ) from exc
        return registration_count, attendance_count

    async def trainer_options(
        self,
        db: AsyncSession,
        *,
        current_user: User,
    ) -> list[TrainerOptionResponse]:
        self._require_manager(current_user)
        statement = select(User).where(
            User.role == UserRole.TRAINER,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        if current_user.role == UserRole.TRAINER:
            statement = statement.where(User.id == current_user.id)
        statement = statement.order_by(User.first_name, User.last_name)
        result = await db.execute(statement)
        return [
            TrainerOptionResponse(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
            )
            for user in result.scalars().all()
        ]

    async def public_training(
        self,
        db: AsyncSession,
        *,
        public_code: str,
    ) -> PublicTrainingResponse:
        result = await db.execute(select(Training).where(Training.public_code == public_code))
        training = result.scalars().first()
        if not training:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme link not found")
        trainer = await db.get(User, training.trainer_id)
        registrations, _ = await self._counts(db, training.id)
        return PublicTrainingResponse(
            public_code=training.public_code,
            title=training.title,
            description=training.description,
            trainer_name=trainer.full_name if trainer else "Unassigned",
            scheduled_at=training.scheduled_at,
            duration_hours=training.duration_hours,
            location=training.location,
            audience_roles=[ParticipantRole(role) for role in training.audience_roles],
            capacity=training.capacity,
            status=training.status,
            attendance_open=training.attendance_open,
            registration_count=registrations,
        )

    async def join_training(
        self,
        db: AsyncSession,
        *,
        public_code: str,
        payload: PublicRegistrationRequest,
    ) -> RegistrationResponse:
        result = await db.execute(
            select(Training).where(Training.public_code == public_code).with_for_update()
        )
        training = result.scalars().first()
        if not training:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme link not found")
        if training.status in {TrainingStatus.COMPLETED, TrainingStatus.CANCELLED}:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Programme registration is closed")
        if payload.role.value not in training.audience_roles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="This programme is not open to the selected role",
            )

        normalized_code = payload.participant_code
        normalized_email = str(payload.email).lower() if payload.email else None
        existing_result = await db.execute(
            select(TrainingRegistration).where(
                TrainingRegistration.training_id == training.id,
                TrainingRegistration.participant_code == normalized_code,
            )
        )
        registration = existing_result.scalars().first()
        if registration:
            same_identity = (
                registration.participant_name.casefold() == payload.participant_name.casefold()
                and registration.role == payload.role
                and registration.email == normalized_email
                and registration.phone == payload.phone
            )
            if not same_identity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Participant code is already registered to different details",
                )
        else:
            contact_conditions = [TrainingRegistration.phone == payload.phone]
            if normalized_email:
                contact_conditions.append(func.lower(TrainingRegistration.email) == normalized_email)
            contact_result = await db.execute(
                select(TrainingRegistration).where(
                    TrainingRegistration.training_id == training.id,
                    or_(*contact_conditions),
                )
            )
            contact_conflict = contact_result.scalars().first()
            if contact_conflict:
                detail = (
                    "Phone number is already registered for this programme"
                    if contact_conflict.phone == payload.phone
                    else "Email is already registered for this programme"
                )
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

            registration_count = await db.scalar(
                select(func.count())
                .select_from(TrainingRegistration)
                .where(TrainingRegistration.training_id == training.id)
            )
            if int(registration_count or 0) >= training.capacity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This programme has reached its participant capacity",
                )
            registration = TrainingRegistration(
                training_id=training.id,
                participant_name=payload.participant_name,
                participant_code=normalized_code,
                role=payload.role,
                email=normalized_email,
                phone=payload.phone,
                joined_at=utcnow(),
                source="qr_link",
            )
            db.add(registration)
            try:
                await db.commit()
            except IntegrityError as exc:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Participant code, phone number, or email is already registered",
                ) from exc
            await db.refresh(registration)

        attendance_result = await db.execute(
            select(TrainingAttendance).where(TrainingAttendance.registration_id == registration.id)
        )
        attendance = attendance_result.scalars().first()
        return RegistrationResponse(
            id=registration.id,
            training_id=registration.training_id,
            participant_name=registration.participant_name,
            participant_code=registration.participant_code,
            role=registration.role,
            email=registration.email,
            phone=registration.phone,
            joined_at=registration.joined_at,
            attendance_marked=attendance is not None,
            checked_in_at=attendance.checked_in_at if attendance else None,
            registration_token=create_attendance_token(
                registration.id,
                training_id=registration.training_id,
            ),
        )

    async def mark_attendance(
        self,
        db: AsyncSession,
        *,
        public_code: str,
        registration_token: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AttendanceConfirmationResponse:
        payload = decode_token(registration_token, expected_type="attendance")
        try:
            registration_id = UUID(payload["sub"])
            training_id = UUID(payload["tid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid attendance receipt",
            ) from exc

        training_result = await db.execute(
            select(Training).where(
                Training.id == training_id,
                Training.public_code == public_code,
            )
        )
        training = training_result.scalars().first()
        if not training:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid attendance receipt")
        if utcnow() < training.scheduled_at:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attendance can only be marked from the scheduled meeting time",
            )
        if not training.attendance_open or training.status in {
            TrainingStatus.COMPLETED,
            TrainingStatus.CANCELLED,
        }:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attendance is closed")

        registration_result = await db.execute(
            select(TrainingRegistration)
            .where(
                TrainingRegistration.id == registration_id,
                TrainingRegistration.training_id == training_id,
            )
            .with_for_update()
        )
        registration = registration_result.scalars().first()
        if not registration:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid attendance receipt")

        attendance_result = await db.execute(
            select(TrainingAttendance).where(TrainingAttendance.registration_id == registration.id)
        )
        attendance = attendance_result.scalars().first()
        if not attendance:
            attendance = TrainingAttendance(
                training_id=training.id,
                registration_id=registration.id,
                checked_in_at=utcnow(),
                source="qr",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(attendance)
            await db.commit()
            await db.refresh(attendance)

        return AttendanceConfirmationResponse(
            id=attendance.id,
            registration_id=registration.id,
            participant_name=registration.participant_name,
            participant_code=registration.participant_code,
            role=registration.role,
            status=attendance.status,
            checked_in_at=attendance.checked_in_at,
        )

    async def attendance_rows(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        training_id: UUID | None = None,
        search: str = "",
    ) -> list[AttendanceRowResponse]:
        self._require_manager(current_user)
        statement = (
            select(TrainingRegistration, Training, TrainingAttendance, User)
            .join(Training, Training.id == TrainingRegistration.training_id)
            .join(User, User.id == Training.trainer_id)
            .outerjoin(
                TrainingAttendance,
                TrainingAttendance.registration_id == TrainingRegistration.id,
            )
        )
        if current_user.role == UserRole.TRAINER:
            statement = statement.where(Training.trainer_id == current_user.id)
        if training_id:
            statement = statement.where(Training.id == training_id)
        normalized_search = search.strip()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    Training.title.ilike(pattern),
                    TrainingRegistration.participant_name.ilike(pattern),
                    TrainingRegistration.participant_code.ilike(pattern),
                    TrainingRegistration.email.ilike(pattern),
                    TrainingRegistration.phone.ilike(pattern),
                )
            )
        statement = statement.order_by(
            Training.scheduled_at.desc(),
            TrainingRegistration.participant_name,
        )
        result = await db.execute(statement)
        rows: list[AttendanceRowResponse] = []
        for registration, training, attendance, trainer in result.all():
            rows.append(
                AttendanceRowResponse(
                    registration_id=registration.id,
                    training_id=training.id,
                    training_title=training.title,
                    trainer_name=trainer.full_name,
                    scheduled_at=training.scheduled_at,
                    location=training.location,
                    participant_name=registration.participant_name,
                    participant_code=registration.participant_code,
                    role=registration.role,
                    email=registration.email,
                    phone=registration.phone,
                    joined_at=registration.joined_at,
                    attendance_status="present" if attendance else "joined_not_present",
                    checked_in_at=attendance.checked_in_at if attendance else None,
                )
            )
        return rows


training_service = TrainingService()
