"""
Backend application entry point for Automated Literature Review
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import routes
from backend.api import health, papers

BACKEND_ENV = os.getenv("APP_ENV", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown logic."""
    logger.info("Backend starting up...")
    logger.info(f"Environment: {BACKEND_ENV}")
    logger.info(f"Frontend URL: {FRONTEND_URL}")
    yield
    logger.info("Backend shutting down...")


# Initialize FastAPI application
app = FastAPI(
    title="Automated Literature Review",
    description="AI-powered research paper analysis system",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for development
if BACKEND_ENV == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS enabled for development")

# Include routes
app.include_router(health.router)
app.include_router(papers.router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BACKEND_PORT", 8000))
    debug = BACKEND_ENV == "development"

    logger.info(f"Starting server on port {port} (debug={debug})")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=debug)
