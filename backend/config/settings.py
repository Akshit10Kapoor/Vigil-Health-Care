import os
import secrets
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_ENVIRONMENT = os.getenv("VIGIL_ENV", "development").strip().lower()
_SECRET_KEY_ENV = os.getenv("SECRET_KEY", "").strip()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vigil Clinical Event Verification"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Deployment environment: development, test, staging, production
    ENVIRONMENT: str = _ENVIRONMENT

    # Secret Key for JWT auth. Production must supply SECRET_KEY explicitly so
    # tokens survive restarts. Development gets an ephemeral key.
    SECRET_KEY: str = _SECRET_KEY_ENV or secrets.token_urlsafe(48)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/vigil_db"
    )

    # Startup seeding. Disabled by default in production.
    AUTO_SEED: bool = _env_bool("VIGIL_AUTO_SEED", _ENVIRONMENT != "production")
    SEED_DEMO_USERS: bool = _env_bool("VIGIL_SEED_DEMO_USERS", _ENVIRONMENT != "production")
    SEED_DEMO_PATIENTS: bool = _env_bool("VIGIL_SEED_DEMO_PATIENTS", _ENVIRONMENT != "production")
    SEED_ADMIN_PASSWORD: str = os.getenv("VIGIL_SEED_ADMIN_PASSWORD", "")
    SEED_DEMO_PASSWORD: str = os.getenv("VIGIL_SEED_DEMO_PASSWORD", "")

    # Comma-separated list; "*" is intended for local development only.
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # 0 disables the background verifier. Values are seconds.
    INTEGRITY_CHECK_INTERVAL_SECONDS: int = int(
        os.getenv("VIGIL_INTEGRITY_CHECK_INTERVAL_SECONDS", "0") or "0"
    )

    # Upload Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    SIGNATURE_DIR: Path = BASE_DIR / "uploads" / "signatures"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        case_sensitive = True


if _ENVIRONMENT == "production" and not _SECRET_KEY_ENV:
    raise RuntimeError(
        "SECRET_KEY must be set explicitly when VIGIL_ENV=production"
    )

settings = Settings()

# Ensure uploads directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)

def load_hospital_settings():
    config_path = BASE_DIR / "config" / "hospital_settings.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {}
