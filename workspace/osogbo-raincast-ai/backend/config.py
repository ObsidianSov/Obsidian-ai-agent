"""
Osogbo RainCast AI - Backend Configuration

Configuration management for the FastAPI backend server.

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from functools import lru_cache


class City(BaseModel):
    """Predefined city location."""
    name: str
    lat: float
    lon: float
    state: Optional[str] = None


class Settings(BaseModel):
    """Application settings."""
    
    # API Settings
    app_name: str = "Osogbo RainCast AI"
    app_version: str = "v1.0.0"
    api_prefix: str = "/api"
    
    # CORS Settings
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # Forecast Directory
    forecast_dir: str = "data/forecasts/latest"
    
    # Model Settings
    model_version: str = "v1.0.0"
    forecast_horizon: int = 6
    
    # Grid Settings
    grid_shape: List[int] = [81, 81]
    lat_min: float = 4.0
    lat_max: float = 8.0
    lon_min: float = 2.0
    lon_max: float = 6.0
    
    # Predefined Cities
    cities: List[City] = [
        City(name="Osogbo", lat=7.7675, lon=4.0673, state="Osun"),
        City(name="Ibadan", lat=7.3775, lon=3.9470, state="Oyo"),
        City(name="Ilorin", lat=8.5000, lon=4.5500, state="Kwara"),
        City(name="Abeokuta", lat=7.1500, lon=3.3500, state="Ogun"),
        City(name="Ondo", lat=7.2500, lon=4.8333, state="Ondo"),
        City(name="Ekiti", lat=7.6500, lon=5.3000, state="Ekiti"),
        City(name="Akure", lat=7.2500, lon=5.2000, state="Ondo"),
        City(name="Oyo", lat=7.8500, lon=3.9500, state="Oyo"),
        City(name="Ikeja", lat=6.6059, lon=3.3491, state="Lagos"),
        City(name="Abuja", lat=9.0765, lon=7.3986, state="FCT"),
    ]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_city_by_name(name: str) -> Optional[City]:
    """Get city by name (case-insensitive)."""
    settings = get_settings()
    name_lower = name.lower()
    
    for city in settings.cities:
        if city.name.lower() == name_lower:
            return city
    
    return None
