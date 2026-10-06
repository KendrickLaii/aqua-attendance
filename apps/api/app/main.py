import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.limiter import limiter
from app.services.audit_log import set_request_context
from app.routers import (
    attendance,
    attendance_summaries,
    audit_logs,
    auth,
    auto_checkout,
    course_enrollments,
    course_skus,
    course_spus,
    location_attachments,
    locations,
    notifications,
    payroll_records,
    qr,
    shifts,
    staff_shifts,
    staff_profiles,
    student_profiles,
    tuition_invoices,
    tuition_receipts,
    units,
    uploads,
    users,
)

logger = logging.getLogger(__name__)


async def _attachment_purge_loop() -> None:
    from app.services.attachments import purge_expired_attachments

    while True:
        try:
            async with async_session_factory() as db:
                await purge_expired_attachments(db)
        except Exception:
            logger.exception("Attachment purge failed")
        await asyncio.sleep(24 * 60 * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_attachment_purge_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="AQUA Attendance API",
    version=settings.APP_VERSION,
    description="Multi-location QR time & attendance — unit-based tracking for staff and students",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def audit_request_context(request: Request, call_next):
    set_request_context(request)
    return await call_next(request)


origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(units.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(location_attachments.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(qr.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(student_profiles.router, prefix="/api")
app.include_router(staff_profiles.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(attendance_summaries.router, prefix="/api")
app.include_router(payroll_records.router, prefix="/api")
app.include_router(audit_logs.router, prefix="/api")
app.include_router(auto_checkout.router, prefix="/api")
app.include_router(course_spus.router, prefix="/api")
app.include_router(course_skus.router, prefix="/api")
app.include_router(course_enrollments.router, prefix="/api")
app.include_router(tuition_invoices.router, prefix="/api")
app.include_router(tuition_receipts.router, prefix="/api")  # receipts settle issued invoices
app.include_router(shifts.templates_router, prefix="/api")
app.include_router(shifts.router, prefix="/api")
app.include_router(staff_shifts.router, prefix="/api")
app.include_router(staff_shifts.admin_router, prefix="/api")



@app.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Liveness + database connectivity (for deploy health checks)."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc
    return {"status": "ok", "database": "ok", "version": settings.APP_VERSION}
