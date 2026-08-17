"""
Health check endpoints for the backend
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from backend.config.database import check_database_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

class HealthResponse(BaseModel):
    status: str

class HealthDbResponse(BaseModel):
    status: str
    database: str

@router.get("", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint - verifies backend is running
    
    Returns:
        HealthResponse: Status indicator
    """
    return HealthResponse(status="ok")

@router.get("/db", response_model=HealthDbResponse)
async def health_db():
    """
    Database health check endpoint - verifies database connectivity
    
    Returns:
        HealthDbResponse: Status and database connection status
        
    Raises:
        HTTPException: If database connection fails
    """
    try:
        is_connected = await check_database_connection()
        if is_connected:
            return HealthDbResponse(status="ok", database="connected")
        else:
            raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")
