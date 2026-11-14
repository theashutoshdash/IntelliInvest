
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # Application configuration
    ENV_NAME = os.getenv("FLASK_ENV", "development")

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "local-development-only-change-before-deploy"
    )

    # Instance directory
    INSTANCE_DIR = (
        Path("/tmp/instance")
        if os.getenv("VERCEL")
        else BASE_DIR / "instance"
    )

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = (
            f"sqlite:///{(INSTANCE_DIR / 'intellinvest.db').as_posix()}"
        )

    # PostgreSQL URL compatibility
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://",
            "postgresql+psycopg://",
            1
        )

    elif SQLALCHEMY_DATABASE_URI.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True
    }

    # Google OAuth configuration
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

    # Session and cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_SECURE = _as_bool(
        os.getenv("SESSION_COOKIE_SECURE"),
        os.getenv("FLASK_ENV", "development") == "production"
    )

    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Security and request limits
    WTF_CSRF_TIME_LIMIT = 3600
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    # Application settings
    AUTO_CREATE_DB = _as_bool(
        os.getenv("AUTO_CREATE_DB"),
        True
    )

    TRUST_PROXY = _as_bool(
        os.getenv("TRUST_PROXY"),
        False
    )

    TRUSTED_HOSTS = [
        host.strip()
        for host in os.getenv(
            "TRUSTED_HOSTS",
            "localhost,127.0.0.1"
        ).split(",")
        if host.strip()
    ]

    RISK_FREE_RATE = float(
        os.getenv("RISK_FREE_RATE", "0.065")
    )

    MARKET_CACHE_SECONDS = 300
    JSON_SORT_KEYS = False
