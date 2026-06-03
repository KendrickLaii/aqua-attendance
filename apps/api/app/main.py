from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import async_session_factory
from app.routers import attendance, auth, locations, products, qr, users

app = FastAPI(
    title="Juku Attendance API",
    version="2.0.0",
    description="Time & Attendance system for cram school (juku) — product-based tracking",
)

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
app.include_router(products.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(qr.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    """Liveness + database connectivity (for deploy health checks)."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc
    return {"status": "ok", "database": "ok"}
