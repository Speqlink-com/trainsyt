"""Training management, public QR registration, and attendance export routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_client_ip, get_db, get_user_agent
from app.core.security import get_current_user, validate_csrf
from app.models.users import User
from app.schemas.training import (
    AttendanceMarkRequest,
    PublicRegistrationRequest,
    TrainingCreateRequest,
    TrainingStatusUpdateRequest,
    TrainingUpdateRequest,
)
from app.services.attendance_export import build_attendance_workbook
from app.services.training_service import training_service

router = APIRouter()
public_router = APIRouter()


@router.get("")
async def list_trainings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trainings = await training_service.list_trainings(db, current_user=current_user)
    return {"success": True, "data": {"trainings": trainings}}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_training(
    payload: TrainingCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    training = await training_service.create_training(db, creator=current_user, payload=payload)
    return {"success": True, "message": "Training programme created", "data": {"training": training}}


@router.get("/trainers")
async def list_trainer_options(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trainers = await training_service.trainer_options(db, current_user=current_user)
    return {"success": True, "data": {"trainers": trainers}}


@router.get("/attendance")
async def list_attendance(
    training_id: UUID | None = None,
    search: str = Query(default="", max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await training_service.attendance_rows(
        db,
        current_user=current_user,
        training_id=training_id,
        search=search,
    )
    return {"success": True, "data": {"rows": rows, "total": len(rows)}}


@router.get("/attendance/export.xlsx")
async def export_attendance(
    training_id: UUID | None = None,
    search: str = Query(default="", max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await training_service.attendance_rows(
        db,
        current_user=current_user,
        training_id=training_id,
        search=search,
    )
    workbook = build_attendance_workbook(rows)
    filename = f"jubilee-training-attendance-{datetime.now():%Y%m%d-%H%M}.xlsx"
    return Response(
        content=workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{training_id}")
async def get_training(
    training_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    training = await training_service.get_training_for_user(
        db,
        current_user=current_user,
        training_id=training_id,
    )
    return {"success": True, "data": {"training": training}}


@router.patch("/{training_id}/status")
async def update_training_status(
    training_id: UUID,
    payload: TrainingStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    training = await training_service.update_status(
        db,
        current_user=current_user,
        training_id=training_id,
        payload=payload,
    )
    return {"success": True, "message": "Training status updated", "data": {"training": training}}


@router.patch("/{training_id}")
async def update_training(
    training_id: UUID,
    payload: TrainingUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    training = await training_service.update_training(
        db,
        current_user=current_user,
        training_id=training_id,
        payload=payload,
    )
    return {"success": True, "message": "Training programme updated", "data": {"training": training}}


@router.delete("/{training_id}")
async def delete_training(
    training_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    registrations, attendance = await training_service.delete_training(
        db,
        current_user=current_user,
        training_id=training_id,
    )
    return {
        "success": True,
        "message": "Training programme deleted",
        "data": {
            "deleted_registrations": registrations,
            "deleted_attendance_records": attendance,
        },
    }


@public_router.get("/{public_code}")
async def get_public_training(
    public_code: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    training = await training_service.public_training(db, public_code=public_code)
    return {"success": True, "data": {"training": training}}


@public_router.post("/{public_code}/registrations", status_code=status.HTTP_201_CREATED)
async def join_public_training(
    public_code: str,
    payload: PublicRegistrationRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    registration = await training_service.join_training(
        db,
        public_code=public_code,
        payload=payload,
    )
    return {
        "success": True,
        "message": "Programme joined",
        "data": {"registration": registration},
    }


@public_router.post("/{public_code}/attendance")
async def mark_public_attendance(
    public_code: str,
    payload: AttendanceMarkRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    ip_address: str | None = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
):
    response.headers["Cache-Control"] = "no-store"
    attendance = await training_service.mark_attendance(
        db,
        public_code=public_code,
        registration_token=payload.registration_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return {
        "success": True,
        "message": "Attendance recorded",
        "data": {"attendance": attendance},
    }
