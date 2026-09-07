/**
 * Osogbo RainCast AI - Main Application Component
 * 
 * Interactive rainfall nowcasting dashboard for Southwest Nigeria
 * 
 * Author: Ahmad Suleiman
 * Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
 */

import React, { useState, useEffect, useCallback } from 'react';
import { MapContainer } from 'react-leaflet';
import { Header } from './components/Header';
import { MapView } from './components/MapView';
import { CityPanel } from './components/CityPanel';
import { TimeSlider } from './components/TimeSlider';
import { RainfallLegend } from './components/RainfallLegend';
import { fetchLatestForecast, fetchCityForecast } from './api/nowcast';

function App() {
  const [forecastData, setForecastData] = useState(null);
  const [selectedHour, setSelectedHour] = useState(1);
  const [selectedCity, setSelectedCity] = useState(null);
  const [cityForecast, setCityForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch latest forecast on mount
  useEffect(() => {
    const loadForecast = async () => {
      try {
        setLoading(true);
        const data = await fetchLatestForecast();
        setForecastData(data);
        setError(null);
      } catch (err) {
        setError('Failed to load forecast data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadForecast();

    // Refresh every 15 minutes
    const interval = setInterval(loadForecast, 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch city forecast when city is selected
  useEffect(() => {
    if (!selectedCity) {
      setCityForecast(null);
      return;
    }

    const loadCityForecast = async () => {
      try {
        const data = await fetchCityForecast(selectedCity.name);
        setCityForecast(data);
      } catch (err) {
        console.error('Failed to load city forecast:', err);
        setCityForecast(null);
      }
    };

    loadCityForecast();
  }, [selectedCity]);

  const handleHourChange = useCallback((hour) => {
    setSelectedHour(hour);
  }, []);

  const handleCitySelect = useCallback((city) => {
    setSelectedCity(city);
  }, []);

  if (error) {
    return (
      <div className="app error-state">
        <div className="error-content">
          <h1>⚠️ Error</h1>
          <p>{error}</p>
          <p className="hint">Make sure the backend server is running.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <Header 
        forecastData={forecastData} 
        loading={loading} 
      />
      
      <main className="main-content">
        <aside className="sidebar">
          <CityPanel 
            onCitySelect={handleCitySelect}
            selectedCity={selectedCity}
            cityForecast={cityForecast}
          />
        </aside>
        
        <div className="map-container">
          {forecastData && (
            <>
              <MapView 
                forecastData={forecastData}
                selectedHour={selectedHour}
              />
              
              <TimeSlider
                selectedHour={selectedHour}
                onHourChange={handleHourChange}
                maxHours={6}
              />
              
              <RainfallLegend />
            </>
          )}
          
          {loading && !forecastData && (
            <div className="loading-overlay">
              <div className="loading-spinner"></div>
              <p>Loading forecast data...</p>
            </div>
          )}
        </div>
      </main>
      
      <footer className="footer">
        <p>
          Osogbo RainCast AI &copy; 2024 | 
          Developed by <strong>Ahmad Suleiman</strong> | 
          UMYU, Katsina, Nigeria
        </p>
        <p className="disclaimer">
          Experimental research project. Not for operational use.
        </p>
      </footer>
    </div>
  );
}

export default App;
