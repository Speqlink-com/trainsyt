"""Jubilee Learning Hub API application."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.core import settings
from app.core.database import database_ready, dispose_database
from app.routes.auth import router as auth_router
from app.routes.trainings import public_router as public_training_router
from app.routes.trainings import router as training_router
from app.services.training_reminder_service import training_reminder_service

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema changes are owned by the one-shot Alembic service in Compose.
    reminder_task = None
    if settings.TRAINING_REMINDERS_ENABLED:
        reminder_task = asyncio.create_task(
            training_reminder_service.run(),
            name="training-reminder-scheduler",
        )
    try:
        yield
    finally:
        if reminder_task:
            reminder_task.cancel()
            with suppress(asyncio.CancelledError):
                await reminder_task
        await dispose_database()


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="Training Platform with secure, persistent authentication",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", settings.CSRF_HEADER_NAME],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(training_router, prefix="/api/trainings", tags=["Training attendance"])
app.include_router(
    public_training_router,
    prefix="/api/public/trainings",
    tags=["Public training attendance"],
)


@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} API", "status": "running"}


@app.get("/health/live")
async def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness(response: Response):
    ready = await database_ready()
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "database": ready}


@app.get("/health")
async def health(response: Response):
    return await readiness(response)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.is_development,
    )
