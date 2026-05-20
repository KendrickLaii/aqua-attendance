from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://attendance:attendance@localhost:5432/attendance"
    DATABASE_URL_SYNC: str = "postgresql+psycopg://attendance:attendance@localhost:5432/attendance"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    QR_SECRET: str = "change-me-qr-secret"
    # QR tokens have no expiry; rotation happens via the refresh endpoint
    # which bumps Product.qr_token_version.  Same token toggles check-in/out.
    SCAN_DEBOUNCE_SECONDS: int = 3

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8081"

    ENV: str = "development"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
