"""
Network Management Platform - Main FastAPI Application
Enterprise-grade network management with AI automation and Ray cluster integration
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import ray
import logging
import os
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.core.redis_client import init_redis
from app.core.ray_cluster import init_ray_cluster
from app.core.init_admin import init_admin_data
from app.api.v1 import api_router
from app.core.websocket_manager import WebSocketManager
from app.core.api_docs import API_TITLE, API_VERSION, API_DESCRIPTION, TAGS_METADATA, custom_openapi_schema
from app.core.rate_limit import rate_limit_middleware
from app.core.validation import validation_middleware
from app.core.logging_config import setup_logging, get_logger
from app.middleware.logging import LoggingMiddleware, AuditLoggingMiddleware

# Configure logging
setup_logging()
logger = get_logger(__name__)

# Initialize WebSocket manager
websocket_manager = WebSocketManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    logger.info("Starting Network Management Platform...")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Initialize Redis
    logger.info("Initializing Redis...")
    await init_redis()
    
    # Initialize admin data
    logger.info("Initializing admin data...")
    await init_admin_data()
    
    # Initialize Ray cluster
    logger.info("Initializing Ray cluster...")
    await init_ray_cluster()
    
    logger.info("Platform startup complete!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down platform...")
    if ray.is_initialized():
        ray.shutdown()
    logger.info("Platform shutdown complete!")

# Create FastAPI application
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan
)

# Set custom OpenAPI schema
app.openapi = lambda: custom_openapi_schema(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Add validation middleware
app.middleware("http")(validation_middleware)

# Add logging middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuditLoggingMiddleware)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "ray_initialized": ray.is_initialized(),
        "gpu_available": ray.available_resources().get("GPU", 0) > 0 if ray.is_initialized() else False
    }

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket_manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

# Serve static files (for development)
if settings.ENVIRONMENT == "development":
    app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.ENVIRONMENT == "development" else False,
        log_level="info"
    )