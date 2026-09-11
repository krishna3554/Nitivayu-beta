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
    # MUST be false in any production deployment (default; dev .env files
    # opt in explicitly).
    ALLOW_DEV_OTP: bool = False
    INVITE_TTL_DAYS: int = 7
    # Reversible citizen-phone encryption key for opt-in status SMS (WP-9).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Empty = no citizen SMS channel (hash-only PII stays hash-only).
    PHONE_FERNET_KEY: str = ""

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
    # File-report root (CSV/PDF/audit). B4: promoted to Settings so .env is
    # the single source of truth instead of a stray os.getenv in outputs.py.
    OUTPUT_ROOT: str = "/app/output"

    # --- Redis (cache / sessions / rate-limit / SSE fan-out) ---
    REDIS_URL: str = ""
    ANALYTICS_CACHE_TTL_SECONDS: int = 60
    RATE_LIMIT_AUTH_PER_MIN: int = 20
    RATE_LIMIT_SUBMIT_PER_MIN: int = 30

    # --- Media pipeline ---
    ASR_ENABLED: bool = False  # local Whisper-class transcription (open decision §10)
    MODERATION_ENABLED: bool = False  # virus/NSFW scanning provider hook

    # --- Batch triage ---
    # Cosine-similarity threshold for dedup/duplicate clustering (worker).
    DEDUP_SIMILARITY_THRESHOLD: float = 0.85
    # Safety cap per on-demand batch run (clustering is O(n^2)).
    BATCH_MAX_SUBMISSIONS: int = 500

    # --- Reporter notifications (mail + SMS) ---
    # Email via SMTP (stdlib, no extra deps). Empty SMTP_HOST = log-only dev
    # mode (message written to backend logs, nothing sent).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@nitivayu.local"
    SMTP_USE_TLS: bool = True
    # SMS via Twilio (stable REST API) or MSG91 (authkey API). Reuses the
    # SMS_PROVIDER switch ("log" default); "msg91"/"twilio" select delivery.
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM: str = ""
    MSG91_AUTH_KEY: str = ""
    MSG91_SENDER: str = "NITIVU"
    MSG91_ROUTE: str = "4"
    MSG91_DLT_TEMPLATE_ID: str = ""

    # --- Pipeline tuning (single source of truth; served to the UI via /meta/config) ---
    OFFICER_SLA_HOURS: int = 72
    UNIVERSITY_SLA_HOURS: int = 168  # 7 days
    SCORE_WEIGHT_THEME: float = 0.4
    SCORE_WEIGHT_SEMANTIC: float = 0.3
    SCORE_WEIGHT_CAPACITY: float = 0.2
    SCORE_WEIGHT_GEO: float = 0.1
    # Milestone due-date offsets (days after a university accepts).
    MILESTONE_M1_DAYS: int = 14
    MILESTONE_M2_DAYS: int = 45
    MILESTONE_M3_DAYS: int = 90
    # Demo mode: when true, /meta/demo-accounts lists the seeded credentials on
    # the login page. MUST be false in production.
    DEMO_MODE: bool = False

    # --- Outbound notifications (WP-9; log-only until configured) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@nitivayu.in"
    MSG91_AUTH_KEY: str = ""
    MSG91_SENDER_ID: str = "NTIVYU"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def effective_database_url(self) -> str:
        return self.PGBOUNCER_URL or self.DATABASE_URL

@lru_cache
def get_settings() -> Settings:
    return Settings()
