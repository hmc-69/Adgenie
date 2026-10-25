import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "AdGenie API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost:3306/adgenie")

    JWT_SECRET_KEY: str | None = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock").lower()
    AI_FALLBACK_TO_MOCK: bool = os.getenv("AI_FALLBACK_TO_MOCK", "true").lower() in {"1", "true", "yes", "on"}
    AUDIENCE_CLASSIFIER_ENABLED: bool = os.getenv("AUDIENCE_CLASSIFIER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    IMAGE_PROVIDER: str = os.getenv("IMAGE_PROVIDER", "cloudflare").lower()
    CLOUDFLARE_IMAGE_API_URL: str | None = os.getenv("CLOUDFLARE_IMAGE_API_URL")
    CLOUDFLARE_API_KEY: str | None = os.getenv("CLOUDFLARE_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    JSON2VIDEO_API_KEY: str | None = os.getenv("JSON2VIDEO_API_KEY")
    JSON2VIDEO_API_URL: str = "https://api.json2video.com/v2"
    PEXELS_API_KEY: str | None = os.getenv("PEXELS_API_KEY")
    SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "adgenie-images")


settings = Settings()


def validate_security_configuration() -> None:
    """Fail startup rather than signing tokens with a known or weak secret."""
    secret = settings.JWT_SECRET_KEY
    if (
        not secret
        or len(secret) < 32
        or len(set(secret)) < 16
        or secret == "adgenie_jwt_super_secret_key_2026_marketing_intel_secure_key"
        or secret.lower().startswith(("replace-with", "changeme", "change-me", "your-"))
    ):
        raise RuntimeError(
            "JWT_SECRET_KEY must be explicitly configured with at least 32 random characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
