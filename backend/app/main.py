import asyncio
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
from app.db.session import engine
from temporalio.client import Client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()

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
    app.state.temporal_client = None
    try:
        app.state.temporal_client = await asyncio.wait_for(
            Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE),
            timeout=5,
        )
        logger.info("Temporal client connected at %s", settings.TEMPORAL_HOST)
    except Exception:
        logger.warning("Temporal unavailable at startup; API calls will retry per request", exc_info=True)
    # Best-effort object-storage bootstrap (no-op when S3 is disabled).
    try:
        from app.services import storage as storage_svc

        if storage_svc.enabled():
            storage_svc.ensure_bucket()
    except Exception:
        logger.warning("Object-storage bootstrap skipped", exc_info=True)
    yield
    client = getattr(app.state, "temporal_client", None)
    close = getattr(client, "close", None)
    if callable(close):
        try:
            await close()
        except Exception:
            logger.warning("Error while closing Temporal client", exc_info=True)
    app.state.temporal_client = None
    logger.info("Shutting down Nitivayu backend...")
    await engine.dispose()


app = FastAPI(title="Nitivayu Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
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


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/health")
async def health_check():
    database = "ok"
    try:
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
    healthy = database == "ok"
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "healthy" if healthy else "degraded", "service": "nitivayu-backend", "version": "1.0.0", "database": database, "dependencies": checks},
    )


@app.get("/")
async def root():
    return {"message": "Welcome to Nitivayu Core API"}
