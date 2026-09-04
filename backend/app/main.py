import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.config import get_settings
from app.api.router import api_router
from temporalio.client import Client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()


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


@app.get("/api/health")
async def health_check():
    database = "ok"
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        database = "unreachable"
    healthy = database == "ok"
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "healthy" if healthy else "degraded", "service": "nitivayu-backend", "version": "1.0.0", "database": database},
    )


@app.get("/")
async def root():
    return {"message": "Welcome to Nitivayu Core API"}
