from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.routers import attendance, auth, locations, products, qr, users

app = FastAPI(
    title="AQUA Attendance API",
    version="2.0.0",
    description="Time & Attendance system for cram school (juku) — product-based tracking",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Liveness + database connectivity (for deploy health checks)."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc
    return {"status": "ok", "database": "ok"}
