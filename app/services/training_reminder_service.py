"""Automated one-hour reminders for trainers and registered participants."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.core import settings
from app.core.database import async_session
from app.core.security import utcnow
from app.models.enums import TrainingStatus
from app.models.trainings import Training, TrainingRegistration
from app.models.users import User
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReminderDispatchResult:
    trainer_emails: int = 0
    participant_emails: int = 0


class TrainingReminderService:
    """Poll for programmes entering the reminder window and email each recipient once."""

    async def dispatch_due_reminders(self, db: AsyncSession) -> ReminderDispatchResult:
        now = utcnow()
        reminder_cutoff = now + timedelta(minutes=settings.TRAINING_REMINDER_MINUTES)
        result = await db.execute(
            select(Training)
            .where(
                Training.status == TrainingStatus.SCHEDULED,
                Training.scheduled_at > now,
                Training.scheduled_at <= reminder_cutoff,
            )
            .order_by(Training.scheduled_at)
            .with_for_update(skip_locked=True)
        )
        trainings = list(result.scalars().all())
        dispatched = ReminderDispatchResult()

        for training in trainings:
            notified_emails: set[str] = set()
            trainer = await db.get(User, training.trainer_id)
            if trainer and trainer.is_active and not training.trainer_reminder_sent_at:
                sent = await email_service.send_training_reminder(
                    email=trainer.email,
                    full_name=trainer.full_name,
                    training_title=training.title,
                    scheduled_at=training.scheduled_at,
                    location=training.location,
                    public_code=training.public_code,
                    is_trainer=True,
                )
                if sent:
                    training.trainer_reminder_sent_at = utcnow()
                    db.add(training)
                    dispatched.trainer_emails += 1
                    notified_emails.add(trainer.email.casefold())
            elif trainer and training.trainer_reminder_sent_at:
                notified_emails.add(trainer.email.casefold())

            registration_result = await db.execute(
                select(TrainingRegistration)
                .where(
                    TrainingRegistration.training_id == training.id,
                    TrainingRegistration.email.is_not(None),
                    TrainingRegistration.reminder_sent_at.is_(None),
                )
                .with_for_update(skip_locked=True)
            )
            for registration in registration_result.scalars().all():
                recipient = registration.email or ""
                if recipient.casefold() in notified_emails:
                    registration.reminder_sent_at = utcnow()
                    db.add(registration)
                    continue
                sent = await email_service.send_training_reminder(
                    email=recipient,
                    full_name=registration.participant_name,
                    training_title=training.title,
                    scheduled_at=training.scheduled_at,
                    location=training.location,
                    public_code=training.public_code,
                    is_trainer=False,
                )
                if sent:
                    registration.reminder_sent_at = utcnow()
                    db.add(registration)
                    dispatched.participant_emails += 1
                    notified_emails.add(recipient.casefold())

            await db.commit()

        return dispatched

    async def run(self) -> None:
        logger.info(
            "Training reminder scheduler started: %s-minute window, %s-second poll",
            settings.TRAINING_REMINDER_MINUTES,
            settings.TRAINING_REMINDER_POLL_SECONDS,
        )
        while True:
            try:
                async with async_session() as db:
                    dispatched = await self.dispatch_due_reminders(db)
                if dispatched.trainer_emails or dispatched.participant_emails:
                    logger.info(
                        "Training reminders sent: %s trainer, %s participant",
                        dispatched.trainer_emails,
                        dispatched.participant_emails,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Training reminder scheduler iteration failed")
            await asyncio.sleep(settings.TRAINING_REMINDER_POLL_SECONDS)


training_reminder_service = TrainingReminderService()
