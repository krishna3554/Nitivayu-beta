import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(title="Nitivayu Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "nitivayu-backend", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"message": "Welcome to Nitivayu Core API"}
