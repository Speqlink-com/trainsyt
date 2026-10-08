"""Environment-backed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Validated configuration for the TrainSyt API."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "Jubilee Learning Hub"
    APP_VERSION: str = "1.0.0"
    SERVICE_NAME: str = "trainsyt"
    ENVIRONMENT: Literal["local", "development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "sqlite+aiosqlite:///./training_platform.db"
    DATABASE_ECHO: bool = False
    AUTO_MIGRATE: bool = False

    JWT_SECRET: SecretStr = SecretStr("development-jwt-secret-change-before-production")
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    JWT_ISSUER: str = "trainsyt-api"
    JWT_AUDIENCE: str = "trainsyt-web"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    TEMP_TOKEN_EXPIRE_MINUTES: int = 15
    ATTENDANCE_TOKEN_EXPIRE_HOURS: int = 72
    JWT_LEEWAY_SECONDS: int = 5

    INITIAL_ADMIN_SECRET_KEY: SecretStr = SecretStr("development-bootstrap-secret")
    SEED_ADMIN_EMAIL: str | None = None
    SEED_ADMIN_PASSWORD: SecretStr | None = None
    SEED_ADMIN_FIRST_NAME: str = "System"
    SEED_ADMIN_LAST_NAME: str = "Administrator"
    SEED_ADMIN_FORCE_PASSWORD_CHANGE: bool = False
    MAX_ADMIN_ACCOUNTS: int = 6

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    CSRF_COOKIE_NAME: str = "csrf_token"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    CORS_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,http://192.168.0.101:3000,http://192.168.0.104:3000"
    )
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,192.168.0.101,192.168.0.104"

    SMTP_HOST: str = "smtp.zoho.com"
    SMTP_PORT: int = 587
    SMTP_STARTTLS: bool = True
    ZOHO_EMAIL: str | None = None
    ZOHO_APP_PASSWORD: SecretStr | None = None
    EMAIL_FROM: str | None = None
    EMAIL_FROM_NAME: str = "Jubilee Learning Hub"
    EMAIL_DELIVERY_MODE: Literal["smtp", "console"] = "smtp"
    FRONTEND_URL: str = "http://localhost:3000"
    APP_TIMEZONE: str = "Africa/Nairobi"
    TRAINING_REMINDERS_ENABLED: bool = True
    TRAINING_REMINDER_MINUTES: int = 60
    TRAINING_REMINDER_POLL_SECONDS: int = 60

    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RATE_LIMIT: int = 3
    OTP_RATE_WINDOW_MINUTES: int = 10
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 30

    @field_validator(
        "DEBUG",
        "DATABASE_ECHO",
        "AUTO_MIGRATE",
        "COOKIE_SECURE",
        "SMTP_STARTTLS",
        "TRAINING_REMINDERS_ENABLED",
        "SEED_ADMIN_FORCE_PASSWORD_CHANGE",
        mode="before",
    )
    @classmethod
    def parse_bool(cls, value: object) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        jwt_secret = self.JWT_SECRET.get_secret_value()
        bootstrap_secret = self.INITIAL_ADMIN_SECRET_KEY.get_secret_value()
        if len(jwt_secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        if len(bootstrap_secret) < 32:
            raise ValueError("INITIAL_ADMIN_SECRET_KEY must contain at least 32 characters")
        if self.ENVIRONMENT in {"staging", "production"}:
            if "development" in jwt_secret or "change" in jwt_secret:
                raise ValueError("JWT_SECRET must be replaced outside development")
            if "development" in bootstrap_secret or "bootstrap" in bootstrap_secret:
                raise ValueError("INITIAL_ADMIN_SECRET_KEY must be replaced outside development")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be true outside development")
            if self.EMAIL_DELIVERY_MODE != "smtp" or not self.smtp_configured:
                raise ValueError("SMTP credentials are required outside development")
            if not self.SEED_ADMIN_EMAIL or not self.SEED_ADMIN_PASSWORD:
                raise ValueError("Seed administrator credentials are required outside development")
            seed_password = self.SEED_ADMIN_PASSWORD.get_secret_value()
            minimum_seed_length = 8 if self.SEED_ADMIN_FORCE_PASSWORD_CHANGE else 12
            if len(seed_password) < minimum_seed_length:
                raise ValueError(
                    f"SEED_ADMIN_PASSWORD must contain at least {minimum_seed_length} characters"
                )
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("SameSite=None cookies require COOKIE_SECURE=true")
        if (
            self.ACCESS_TOKEN_EXPIRE_MINUTES < 1
            or self.REFRESH_TOKEN_EXPIRE_DAYS < 1
            or self.ATTENDANCE_TOKEN_EXPIRE_HOURS < 1
        ):
            raise ValueError("Token expiry values must be positive")
        if self.LOGIN_MAX_ATTEMPTS < 1 or self.LOGIN_LOCKOUT_MINUTES < 1:
            raise ValueError("Login lockout values must be positive")
        if self.MAX_ADMIN_ACCOUNTS < 1:
            raise ValueError("MAX_ADMIN_ACCOUNTS must be positive")
        if self.TRAINING_REMINDER_MINUTES < 1 or self.TRAINING_REMINDER_POLL_SECONDS < 10:
            raise ValueError("Training reminder timing values must be positive")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(
            self.ZOHO_EMAIL
            and self.ZOHO_APP_PASSWORD
            and self.EMAIL_FROM
        )

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT in {"local", "development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
