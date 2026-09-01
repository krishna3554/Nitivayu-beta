from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Nitivayu backend...")
    yield
    logger.info("Shutting down Nitivayu backend...")

app = FastAPI(title="Nitivayu Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO: Include routers when they are created
# from app.api.routes import api_router
# app.include_router(api_router, prefix="/api/v1")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "nitivayu-backend", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"message": "Welcome to Nitivayu Core API"}
