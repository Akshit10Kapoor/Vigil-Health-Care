import os
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Vigil Clinical Event Verification"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Secret Key for JWT auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "vigil_secret_key_change_in_production_2026_super_secure")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/vigil_db"
    )
    
    # Upload Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    SIGNATURE_DIR: Path = BASE_DIR / "uploads" / "signatures"
    
    class Config:
        case_sensitive = True

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
