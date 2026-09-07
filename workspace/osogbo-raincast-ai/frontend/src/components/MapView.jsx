/**
 * MapView Component
 * 
 * Interactive Leaflet map showing rainfall overlay
 */

import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, ImageOverlay, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Color scale for rainfall intensity (mm/h)
const RAINFALL_COLORS = [
  { threshold: 0, color: [255, 255, 255, 0] },      // Transparent
  { threshold: 0.1, color: [200, 230, 255, 150] }, // Very light
  { threshold: 1, color: [100, 180, 255, 200] },   // Light
  { threshold: 5, color: [50, 150, 255, 230] },    // Moderate
  { threshold: 10, color: [50, 100, 255, 250] },  // Heavy
  { threshold: 20, color: [150, 50, 255, 255] },   // Very heavy
  { threshold: 50, color: [200, 50, 200, 255] }    // Extreme
];

function getRainfallColor(value) {
  for (let i = RAINFALL_COLORS.length - 1; i >= 0; i--) {
    if (value >= RAINFALL_COLORS[i].threshold) {
      const c = RAINFALL_COLORS[i].color;
      return `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${c[3] / 255})`;
    }
  }
  return 'rgba(255, 255, 255, 0)';
}

function createCanvasFromGrid(grid, width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  
  const gridHeight = grid.length;
  const gridWidth = grid[0].length;
  
  const cellW = width / gridWidth;
  const cellH = height / gridHeight;
  
  for (let y = 0; y < gridHeight; y++) {
    for (let x = 0; x < gridWidth; x++) {
      const value = grid[y][x];
      ctx.fillStyle = getRainfallColor(value);
      ctx.fillRect(x * cellW, y * cellH, cellW + 1, cellH + 1);
    }
  }
  
  return canvas.toDataURL();
}

function RainfallOverlay({ forecastData, selectedHour }) {
  const map = useMap();
  const overlayRef = useRef(null);
  
  useEffect(() => {
    if (!forecastData || !forecastData.forecasts) return;
    
    const hourKey = `h${selectedHour}`;
    const fieldData = forecastData.forecasts[hourKey];
    
    if (!fieldData) return;
    
    // Remove existing overlay
    if (overlayRef.current) {
      map.removeLayer(overlayRef.current);
    }
    
    // Create image from grid
    const grid = fieldData.grid;
    const imageUrl = createCanvasFromGrid(grid, 810, 810);
    
    // Calculate bounds (Southwest Nigeria)
    const bounds = forecastData.metadata?.bounds || {
      lat_min: 4.0,
      lat_max: 8.0,
      lon_min: 2.0,
      lon_max: 6.0
    };
    
    const imageBounds = [
      [bounds.lat_min, bounds.lon_min],
      [bounds.lat_max, bounds.lon_max]
    ];
    
    // Add new overlay
    const overlay = L.imageOverlay(imageUrl, imageBounds, {
      opacity: 0.7,
      interactive: false
    });
    
    overlay.addTo(map);
    overlayRef.current = overlay;
    
    return () => {
      if (overlayRef.current) {
        map.removeLayer(overlayRef.current);
      }
    };
  }, [forecastData, selectedHour, map]);
  
  return null;
}

export function MapView({ forecastData, selectedHour }) {
  // Center on Southwest Nigeria
  const center = [6.0, 4.0];
  const zoom = 7;
  
  const bounds = forecastData?.metadata?.bounds || {
    lat_min: 4.0,
    lat_max: 8.0,
    lon_min: 2.0,
    lon_max: 6.0
  };
  
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      className="rainfall-map"
      maxBounds={[[bounds.lat_min - 1, bounds.lon_min - 1], [bounds.lat_max + 1, bounds.lon_max + 1]]}
      minZoom={6}
      maxZoom={10}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        subdomains={['a', 'b', 'c']}
      />
      
      {forecastData && (
        <RainfallOverlay 
          forecastData={forecastData} 
          selectedHour={selectedHour} 
        />
      )}
    </MapContainer>
  );
}
