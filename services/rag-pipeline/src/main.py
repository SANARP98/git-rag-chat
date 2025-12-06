"""Main FastAPI application entry point."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Set log level from settings
logging.getLogger().setLevel(settings.log_level)

# Create FastAPI app
app = FastAPI(
    title="Git RAG Pipeline",
    description="RAG pipeline for Git repository code analysis",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting Git RAG Pipeline service...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"ChromaDB: {settings.chroma_host}:{settings.chroma_port}")
    logger.info(f"Metadata DB: {settings.metadata_db_path}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down Git RAG Pipeline service...")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Git RAG Pipeline",
        "version": "0.1.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
