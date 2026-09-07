/**
 * Header Component
 */

import React from 'react';

export function Header({ forecastData, loading }) {
  const formatTime = (isoString) => {
    if (!isoString) return '--:--';
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  };

  return (
    <header className="header">
      <div className="header-content">
        <div className="logo">
          <div className="logo-icon">
            <svg viewBox="0 0 100 100" width="40" height="40">
              <rect width="100" height="100" rx="20" fill="#0a1628"/>
              <path d="M25 50 Q30 35 45 40 Q50 25 65 35 Q75 30 80 45 Q90 50 75 60 Q70 75 55 65 Q50 80 35 70 Q20 65 25 50Z" fill="#38b6ff" opacity="0.8"/>
              <circle cx="35" cy="72" r="3" fill="#38b6ff"/>
              <circle cx="50" cy="78" r="4" fill="#667eea"/>
              <circle cx="65" cy="70" r="3" fill="#38b6ff"/>
            </svg>
          </div>
          <div className="logo-text">
            <h1>RainCast <span>AI</span></h1>
            <span className="location">
              <i className="icon">📍</i> Osogbo, Nigeria
            </span>
          </div>
        </div>
        
        <div className="header-status">
          {forecastData && (
            <>
              <div className="status-item">
                <span className="label">Last Updated</span>
                <span className="value">{formatTime(forecastData.run_time)}</span>
              </div>
              <div className="status-item">
                <span className="label">Model Version</span>
                <span className="value">{forecastData.model_version}</span>
              </div>
              <div className="status-item">
                <span className="label">Coverage</span>
                <span className="value">6 Hours</span>
              </div>
            </>
          )}
          
          <div className={`live-indicator ${loading ? 'loading' : ''}`}>
            <span className="dot"></span>
            <span>{loading ? 'Updating...' : 'LIVE'}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
