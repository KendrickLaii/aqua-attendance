from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import attendance, auth, qr, users

app = FastAPI(
    title="Juku Attendance API",
    version="1.0.0",
    description="Time & Attendance system for cram school (juku)",
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
app.include_router(qr.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
