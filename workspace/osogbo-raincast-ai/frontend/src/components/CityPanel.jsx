/**
 * CityPanel Component
 * 
 * Sidebar showing list of cities and their forecasts
 */

import React from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const CITIES = [
  { name: 'Osogbo', lat: 7.7675, lon: 4.0673, state: 'Osun' },
  { name: 'Ibadan', lat: 7.3775, lon: 3.9470, state: 'Oyo' },
  { name: 'Ilorin', lat: 8.5000, lon: 4.5500, state: 'Kwara' },
  { name: 'Abeokuta', lat: 7.1500, lon: 3.3500, state: 'Ogun' },
  { name: 'Ondo', lat: 7.2500, lon: 4.8333, state: 'Ondo' },
  { name: 'Akure', lat: 7.2500, lon: 5.2000, state: 'Ondo' },
  { name: 'Oyo', lat: 7.8500, lon: 3.9500, state: 'Oyo' },
  { name: 'Ekiti', lat: 7.6500, lon: 5.3000, state: 'Ekiti' }
];

export function CityPanel({ onCitySelect, selectedCity, cityForecast }) {
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.parsed.y.toFixed(2)} mm/h`
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: '#b8c5d6',
          font: { size: 10 }
        }
      },
      y: {
        grid: { color: 'rgba(255,255,255,0.1)' },
        ticks: {
          color: '#b8c5d6',
          callback: (v) => v + ' mm'
        },
        beginAtZero: true
      }
    }
  };

  const chartData = {
    labels: cityForecast?.forecast?.map(f => `+${f.hour}h`) || [],
    datasets: [{
      data: cityForecast?.forecast?.map(f => f.rainfall) || [],
      backgroundColor: cityForecast?.forecast?.map(f => 
        f.rainfall > 10 ? 'rgba(150, 50, 255, 0.8)' :
        f.rainfall > 5 ? 'rgba(50, 150, 255, 0.8)' :
        'rgba(100, 180, 255, 0.6)'
      ) || [],
      borderRadius: 4,
      borderWidth: 0
    }]
  };

  return (
    <div className="city-panel">
      <h2>🌡️ Cities</h2>
      
      <div className="city-list">
        {CITIES.map((city) => (
          <button
            key={city.name}
            className={`city-item ${selectedCity?.name === city.name ? 'selected' : ''}`}
            onClick={() => onCitySelect(city)}
          >
            <div className="city-info">
              <span className="city-name">{city.name}</span>
              <span className="city-state">{city.state}</span>
            </div>
            <i className="icon">→</i>
          </button>
        ))}
      </div>
      
      {selectedCity && (
        <div className="city-forecast">
          <h3>{selectedCity.name} Forecast</h3>
          
          {cityForecast ? (
            <>
              <div className="forecast-summary">
                <div className="summary-item">
                  <span className="label">Total (6h)</span>
                  <span className="value">{cityForecast.total_6h.toFixed(1)} mm</span>
                </div>
                <div className="summary-item">
                  <span className="label">Peak</span>
                  <span className="value">
                    {Math.max(...(cityForecast.forecast?.map(f => f.rainfall) || [0])).toFixed(1)} mm/h
                  </span>
                </div>
              </div>
              
              <div className="chart-container">
                <Bar data={chartData} options={chartOptions} />
              </div>
              
              <div className="forecast-table">
                <table>
                  <thead>
                    <tr>
                      <th>Hour</th>
                      <th>Rainfall</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cityForecast.forecast?.map((f) => (
                      <tr key={f.hour}>
                        <td>+{f.hour}h</td>
                        <td className={f.rainfall > 10 ? 'heavy' : f.rainfall > 5 ? 'moderate' : ''}>
                          {f.rainfall.toFixed(2)} mm/h
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="loading">Loading forecast...</div>
          )}
        </div>
      )}
    </div>
  );
}
