import os
from typing import List, Optional


def _parse_cors_origins() -> List[str]:
    """
    Origins allowed for browser cross-origin requests (React, Swagger UI, etc.).

    With CORSMiddleware allow_credentials=True, allow_origins cannot be ["*"] —
    browsers block it, so fetches like GET /api/openapi.json from localhost:3000 fail.

    Set CORS_ORIGINS to a comma-separated list, e.g.:
      CORS_ORIGINS=http://localhost:3000,http://192.168.0.43:3000
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


class Settings():
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "RealSense REST API"

    # Security
    SECRET_KEY: str = "your-secret-key-here"  # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS (see _parse_cors_origins; do not use ["*"] with allow_credentials=True)
    CORS_ORIGINS: list = _parse_cors_origins()

    # WebRTC
    STUN_SERVER: Optional[str] = None
    TURN_SERVER: Optional[str] = None
    TURN_USERNAME: Optional[str] = None
    TURN_PASSWORD: Optional[str] = None

settings = Settings()