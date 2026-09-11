from contextlib import asynccontextmanager
import logging
import re
import time
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Histogram, Counter, generate_latest
from sqlalchemy import text
from app.config import get_settings
from app.api.router import api_router
from app.db.session import dispose_engine, get_engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

REQUEST_LATENCY = Histogram(
    "nitivayu_http_request_seconds", "API request latency", ["method", "path", "status"]
)
REQUEST_COUNT = Counter(
    "nitivayu_http_requests_total", "API request count", ["method", "path", "status"]
)

_TOKEN_RE = re.compile(r"NITIVAYU-[A-Z0-9-]+", re.IGNORECASE)
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Nitivayu backend...")
    # A5: engine is created lazily here (not at import) so cold imports never
    # crash on missing env and the lifespan owns its lifecycle.
    try:
        get_engine()
    except Exception:
        logger.warning("Database engine init deferred; first request will retry", exc_info=True)
    # Best-effort object-storage bootstrap (no-op when S3 is disabled).
    try:
        from app.services import storage as storage_svc

        if storage_svc.enabled():
            storage_svc.ensure_bucket()
    except Exception:
        logger.warning("Object-storage bootstrap skipped", exc_info=True)
    yield
    logger.info("Shutting down Nitivayu backend...")
    try:
        await dispose_engine()
    except Exception:
        logger.warning("Engine dispose failed", exc_info=True)


app = FastAPI(title="Nitivayu Backend", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    # Low-cardinality path label: collapse IDs/tokens to keep series bounded.
    path = _TOKEN_RE.sub("{token}", _UUID_RE.sub("{id}", request.url.path))
    REQUEST_LATENCY.labels(request.method, path, response.status_code).observe(elapsed)
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    return response


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Stamp every request with an id (+ client IP) carried into audit rows."""
    from app.services import audit as audit_ctx

    request_id = request.headers.get("x-request-id") or audit_ctx.new_request_id()
    ip = request.client.host if request.client else None
    tokens = audit_ctx.set_request_context(request_id, ip)
    try:
        response = await call_next(request)
    finally:
        audit_ctx.reset_request_context(tokens)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        logger.warning("Validation failed on %s %s: %s", request.method, request.url.path, exc.errors())
    except Exception:
        pass
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation failed", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred"},
    )


app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health")
async def health_check():
    database = "ok"
    try:
        engine = get_engine()
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        database = "unreachable"
    checks: dict = {}
    try:
        from app.services import redis_client as redis_mod
        from app.services import storage as storage_mod

        checks["redis"] = "ok" if await redis_mod.ping() else "unavailable"
        checks["object_storage"] = "disabled" if not storage_mod.enabled() else ("ok" if await storage_mod.ping() else "unreachable")
    except Exception:
        logger.warning("Health check: dependency probe failed", exc_info=True)
    # B4.1: verdict includes dependencies — degraded unless DB *and* required
    # deps are healthy. Redis is required in compose: unavailable => degraded.
    # Object storage "disabled" is fine for dev; "unreachable" degrades.
    storage_ok = checks.get("object_storage", "disabled") in {"disabled", "ok"}
    healthy = database == "ok" and checks.get("redis") == "ok" and storage_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "healthy" if healthy else "degraded", "service": "nitivayu-backend", "version": "1.0.0", "database": database, "dependencies": checks},
    )


@app.get("/")
async def root():
    return {"message": "Welcome to Nitivayu Core API"}
