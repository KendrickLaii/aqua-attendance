from pydantic import model_validator
from pydantic_settings import BaseSettings

# Known placeholders from .env.example / deploy templates — must not be used when ENV=production
_INSECURE_SECRET_VALUES = frozenset({
    "change-me-in-production",
    "change-me-in-production-use-openssl-rand-hex-32",
    "change-me-qr-secret",
    "change-me-qr-secret-use-openssl-rand-hex-32",
    "change-this-secret-key",
    "change-this-qr-secret",
})

_MIN_PRODUCTION_SECRET_LEN = 32


def _is_production_env(env: str) -> bool:
    return env.strip().lower() in ("production", "prod")


def validate_production_secrets(
    *,
    env: str,
    secret_key: str,
    qr_secret: str,
) -> None:
    """Refuse to start in production with default or weak signing keys."""
    if not _is_production_env(env):
        return

    def check(name: str, value: str) -> None:
        trimmed = value.strip()
        if len(trimmed) < _MIN_PRODUCTION_SECRET_LEN:
            raise RuntimeError(
                f"{name} must be at least {_MIN_PRODUCTION_SECRET_LEN} characters when ENV=production. "
                "Generate one with: openssl rand -hex 32"
            )
        if trimmed in _INSECURE_SECRET_VALUES or trimmed.lower() in _INSECURE_SECRET_VALUES:
            raise RuntimeError(
                f"{name} must not use the example placeholder when ENV=production. "
                "Generate a unique value with: openssl rand -hex 32"
            )

    check("SECRET_KEY", secret_key)
    check("QR_SECRET", qr_secret)


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

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        validate_production_secrets(
            env=self.ENV,
            secret_key=self.SECRET_KEY,
            qr_secret=self.QR_SECRET,
        )
        return self


settings = Settings()
