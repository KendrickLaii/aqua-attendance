import pytest

from app.config import validate_production_secrets


def test_development_allows_placeholder_secrets():
    validate_production_secrets(
        env="development",
        secret_key="change-me-in-production",
        qr_secret="change-me-qr-secret",
    )


def test_production_rejects_placeholder_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_production_secrets(
            env="production",
            secret_key="change-me-in-production-use-openssl-rand-hex-32",
            qr_secret="a" * 64,
        )


def test_production_rejects_short_secret():
    with pytest.raises(RuntimeError, match="QR_SECRET"):
        validate_production_secrets(
            env="production",
            secret_key="a" * 64,
            qr_secret="too-short",
        )


def test_production_accepts_random_secrets():
    validate_production_secrets(
        env="production",
        secret_key="f" * 64,
        qr_secret="e" * 64,
    )
