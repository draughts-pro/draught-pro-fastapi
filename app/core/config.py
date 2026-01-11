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
            origins = [i.strip() for i in v.split(",")]
            cleaned_origins = []
            for o in origins:
                o = o.rstrip("/")
                if not o.startswith("http"):
                    if "localhost" in o or "127.0.0.1" in o:
                        cleaned_origins.append(f"http://{o}")
                    else:
                        cleaned_origins.append(f"https://{o}")
                else:
                    cleaned_origins.append(o)
            return cleaned_origins
        return v

    REDIS_URL: str | None = None

    SECRET_KEY: str = "dev-secret-key-change-in-production"

    MAX_ROOMS: int = 1000
    ROOM_CLEANUP_INTERVAL_SECONDS: int = 3600
    INACTIVE_ROOM_TIMEOUT_SECONDS: int = 7200

    SENTRY_DSN: str | None = "https://3de78001d6efde50d11fa59d32009fe4@o4508014103232512.ingest.de.sentry.io/4510693152522320"
    SENTRY_TRACES_SAMPLE_RATE: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
