/**
 * Osogbo RainCast AI - API Client
 * 
 * Functions for fetching forecast data from the backend API.
 * 
 * Author: Ahmad Suleiman
 * Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
 */

import axios from 'axios';

// Create axios instance with default config
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

/**
 * Fetch the latest forecast metadata
 */
export async function fetchLatestForecast() {
  const response = await api.get('/nowcast/latest');
  return response.data;
}

/**
 * Fetch rainfall field for a specific hour
 */
export async function fetchForecastField(hour) {
  const response = await api.get(`/nowcast/field/${hour}`);
  return response.data;
}

/**
 * Fetch rainfall at a specific point
 */
export async function fetchPointForecast(lat, lon, hour) {
  const response = await api.get('/nowcast/point', {
    params: { lat, lon, hour }
  });
  return response.data;
}

/**
 * Fetch city forecast time series
 */
export async function fetchCityForecast(cityName) {
  const response = await api.get(`/nowcast/city/${cityName.toLowerCase()}`);
  return response.data;
}

/**
 * Fetch list of available cities
 */
export async function fetchCities() {
  const response = await api.get('/nowcast/cities');
  return response.data;
}

/**
 * Health check
 */
export async function healthCheck() {
  const response = await api.get('/health');
  return response.data;
}

export default api;
