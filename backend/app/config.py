from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    # Optional pooled URL (PgBouncer, transaction mode). Falls back to DATABASE_URL.
    PGBOUNCER_URL: str = ""
    TEMPORAL_HOST: str = "temporal:7233"
    TEMPORAL_NAMESPACE: str = "default"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b"
    LLM_CACHE: bool = True
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    DEDUP_SIMILARITY_THRESHOLD: float = 0.92
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    MAX_UPLOAD_BYTES: int = 5_000_000

    # --- Phase-1 identity (nitivayu.md §5.5) ---
    # OTP delivery: "log" writes codes to the backend log (dev/demo);
    # "msg91"/"twilio" select a real SMS provider (see services/auth.py).
    SMS_PROVIDER: str = "log"
    OTP_TTL_SECONDS: int = 600
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_SECONDS: int = 60
    # Demo escape hatch: when true, request-otp echoes the code back in the
    # response body so the flow is testable without an SMS provider.
    # MUST be false in any production deployment.
    ALLOW_DEV_OTP: bool = True
    INVITE_TTL_DAYS: int = 7

    # --- Social login (env-gated; 501 until configured) ---
    OAUTH_CALLBACK_BASE: str = "http://localhost:8000"
    OAUTH_FRONTEND_BASE: str = "http://localhost:3000"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""

    # --- Object storage (S3-compatible; MinIO for self-hosted) ---
    S3_ENABLED: bool = False
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = "nitivayu-media"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_PRESIGN_TTL_SECONDS: int = 3600
    # Local mirror used when S3 is disabled (mounted output_data volume).
    MEDIA_DIR: str = "/app/output/media"

    # --- Redis (cache / sessions / rate-limit / SSE fan-out) ---
    REDIS_URL: str = ""
    ANALYTICS_CACHE_TTL_SECONDS: int = 60
    RATE_LIMIT_AUTH_PER_MIN: int = 20
    RATE_LIMIT_SUBMIT_PER_MIN: int = 30

    # --- Media pipeline ---
    ASR_ENABLED: bool = False  # local Whisper-class transcription (open decision §10)
    MODERATION_ENABLED: bool = False  # virus/NSFW scanning provider hook

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def effective_database_url(self) -> str:
        return self.PGBOUNCER_URL or self.DATABASE_URL

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
