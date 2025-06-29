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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    title="Network Management Platform",
    description="Enterprise-grade network management with AI automation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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