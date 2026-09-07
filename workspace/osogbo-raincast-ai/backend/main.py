"""
Osogbo RainCast AI - FastAPI Backend

This module implements the FastAPI backend for serving
AI-generated rainfall forecasts.

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import get_settings, get_city_by_name, City

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-based rainfall nowcasting API for Southwest Nigeria",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# ============================================================================
# Pydantic Models
# ============================================================================

class ForecastMetadata(BaseModel):
    """Metadata about the latest forecast run."""
    run_time: str
    model_version: str
    forecast_hours: List[int]
    grid_shape: List[int]
    bounds: Dict[str, float]
    units: str = "mm/h"


class GridField(BaseModel):
    """Rainfall field for a specific forecast hour."""
    hour: int
    grid: List[List[float]]
    lat: List[float]
    lon: List[float]
    units: str = "mm/h"


class PointForecast(BaseModel):
    """Rainfall forecast at a specific point."""
    lat: float
    lon: float
    hour: int
    rainfall: float
    units: str = "mm/h"


class CityTimeSeries(BaseModel):
    """Time series of rainfall forecasts for a city."""
    city: str
    lat: float
    lon: float
    forecast: List[Dict[str, Any]]
    total_6h: float
    units: str = "mm"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str


# ============================================================================
# Helper Functions
# ============================================================================

def load_latest_forecast() -> Dict:
    """Load the latest forecast from disk."""
    forecast_path = Path(settings.forecast_dir) / "latest_forecast.json"
    
    if not forecast_path.exists():
        raise HTTPException(
            status_code=503,
            detail="No forecast available. Run inference first."
        )
    
    with open(forecast_path, 'r') as f:
        return json.load(f)


def load_forecast_metadata() -> Dict:
    """Load forecast metadata."""
    metadata_path = Path(settings.forecast_dir) / "metadata.json"
    
    if not metadata_path.exists():
        raise HTTPException(
            status_code=503,
            detail="No forecast metadata available."
        )
    
    with open(metadata_path, 'r') as f:
        return json.load(f)


def get_rainfall_at_point(
    grid: List[List[float]],
    lat_array: List[float],
    lon_array: List[float],
    target_lat: float,
    target_lon: float
) -> float:
    """
    Get rainfall value at a specific lat/lon point.
    
    Uses nearest-neighbor interpolation.
    """
    # Find nearest indices
    lat_idx = min(range(len(lat_array)), 
                  key=lambda i: abs(lat_array[i] - target_lat))
    lon_idx = min(range(len(lon_array)),
                  key=lambda i: abs(lon_array[i] - target_lon))
    
    return grid[lat_idx][lon_idx]


def calculate_6h_total(forecast: List[Dict]) -> float:
    """Calculate total rainfall over 6 hours."""
    return sum(f.get('rainfall', 0) for f in forecast)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )


@app.get("/api/nowcast/latest", response_model=ForecastMetadata, tags=["Nowcast"])
async def get_latest_forecast():
    """
    Get metadata about the latest forecast run.
    
    Returns:
        - run_time: Timestamp of the forecast run
        - model_version: Version of the model used
        - forecast_hours: List of available forecast hours
        - grid_shape: Shape of the forecast grid
        - bounds: Geographic bounds of the forecast
    """
    try:
        metadata = load_forecast_metadata()
        return ForecastMetadata(**metadata)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading forecast metadata: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/nowcast/field/{hour}", response_model=GridField, tags=["Nowcast"])
async def get_forecast_field(hour: int = Field(..., ge=1, le=6)):
    """
    Get the rainfall field for a specific forecast hour.
    
    Args:
        hour: Forecast hour (1-6)
    
    Returns:
        Grid field with rainfall values and coordinates
    """
    try:
        forecast_data = load_latest_forecast()
        
        hour_key = f"h{hour}"
        if hour_key not in forecast_data['forecasts']:
            raise HTTPException(
                status_code=404,
                detail=f"Forecast hour {hour} not found"
            )
        
        field_data = forecast_data['forecasts'][hour_key]
        
        return GridField(
            hour=hour,
            grid=field_data['grid'],
            lat=field_data['lat'],
            lon=field_data['lon']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading forecast field: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/nowcast/point", response_model=PointForecast, tags=["Nowcast"])
async def get_point_forecast(
    lat: float = Query(..., ge=4.0, le=8.0, description="Latitude"),
    lon: float = Query(..., ge=2.0, le=6.0, description="Longitude"),
    hour: int = Query(..., ge=1, le=6, description="Forecast hour")
):
    """
    Get rainfall forecast at a specific point.
    
    Args:
        lat: Latitude (4.0-8.0)
        lon: Longitude (2.0-6.0)
        hour: Forecast hour (1-6)
    
    Returns:
        Rainfall value at the specified point
    """
    try:
        forecast_data = load_latest_forecast()
        
        hour_key = f"h{hour}"
        if hour_key not in forecast_data['forecasts']:
            raise HTTPException(
                status_code=404,
                detail=f"Forecast hour {hour} not found"
            )
        
        field_data = forecast_data['forecasts'][hour_key]
        
        rainfall = get_rainfall_at_point(
            field_data['grid'],
            field_data['lat'],
            field_data['lon'],
            lat,
            lon
        )
        
        return PointForecast(
            lat=lat,
            lon=lon,
            hour=hour,
            rainfall=round(rainfall, 4)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting point forecast: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/nowcast/city/{name}", response_model=CityTimeSeries, tags=["Nowcast"])
async def get_city_forecast(name: str):
    """
    Get time series of rainfall forecasts for a predefined city.
    
    Args:
        name: City name (osogbo, ibadan, ilorin, etc.)
    
    Returns:
        Time series of rainfall forecasts for the next 6 hours
    """
    try:
        # Find city
        city = get_city_by_name(name)
        if not city:
            raise HTTPException(
                status_code=404,
                detail=f"City '{name}' not found. Available cities: "
                       f"{', '.join(c.name for c in settings.cities)}"
            )
        
        # Load forecast
        forecast_data = load_latest_forecast()
        
        # Extract forecast for each hour
        forecast_list = []
        for h in range(1, 7):
            hour_key = f"h{h}"
            if hour_key not in forecast_data['forecasts']:
                continue
            
            field_data = forecast_data['forecasts'][hour_key]
            
            rainfall = get_rainfall_at_point(
                field_data['grid'],
                field_data['lat'],
                field_data['lon'],
                city.lat,
                city.lon
            )
            
            forecast_list.append({
                'hour': h,
                'rainfall': round(rainfall, 4)
            })
        
        # Calculate 6-hour total
        total_6h = calculate_6h_total(forecast_list)
        
        return CityTimeSeries(
            city=city.name,
            lat=city.lat,
            lon=city.lon,
            forecast=forecast_list,
            total_6h=round(total_6h, 2)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting city forecast: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/nowcast/cities", response_model=List[City], tags=["Nowcast"])
async def list_cities():
    """
    Get list of all available cities.
    
    Returns:
        List of predefined city locations
    """
    return settings.cities


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ============================================================================
# Application Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Forecast directory: {settings.forecast_dir}")
    
    # Check if forecast data exists
    forecast_path = Path(settings.forecast_dir) / "latest_forecast.json"
    if forecast_path.exists():
        logger.info("Latest forecast found")
    else:
        logger.warning("No forecast data found. Run inference first.")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down...")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
