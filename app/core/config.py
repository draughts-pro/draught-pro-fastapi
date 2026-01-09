from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Any


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENV: str = "development"

    # CORS - Use Any to prevent Pydantic from forcing JSON parsing for List types
    CORS_ORIGINS: Any = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",")]
        return v

    REDIS_URL: str | None = None

    SECRET_KEY: str = "dev-secret-key-change-in-production"

    MAX_ROOMS: int = 1000
    ROOM_CLEANUP_INTERVAL_SECONDS: int = 3600
    INACTIVE_ROOM_TIMEOUT_SECONDS: int = 7200

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
