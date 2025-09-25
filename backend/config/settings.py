import os
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = os.getenv("APP_TITLE", "Emotion Insight Service")
APP_PORT = int(os.getenv("APP_PORT", "8894"))

MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024

_raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
if _raw_origins.strip() == "*":
    CORS_ALLOW_ORIGINS = ["*"]
else:
    CORS_ALLOW_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

__all__ = [
    "APP_TITLE",
    "APP_PORT",
    "MAX_UPLOAD_SIZE_BYTES",
    "CORS_ALLOW_ORIGINS",
]
