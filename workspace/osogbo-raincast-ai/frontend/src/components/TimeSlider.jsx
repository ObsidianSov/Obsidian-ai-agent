/**
 * TimeSlider Component
 * 
 * Slider to select forecast hour
 */

import React from 'react';

export function TimeSlider({ selectedHour, onHourChange, maxHours }) {
  return (
    <div className="time-slider">
      <div className="slider-header">
        <span className="label">Forecast Hour</span>
        <span className="value">+{selectedHour}h</span>
      </div>
      
      <input
        type="range"
        min={1}
        max={maxHours}
        value={selectedHour}
        onChange={(e) => onHourChange(parseInt(e.target.value))}
        className="slider"
      />
      
      <div className="slider-labels">
        {[...Array(maxHours)].map((_, i) => (
          <span 
            key={i + 1} 
            className={selectedHour === i + 1 ? 'active' : ''}
          >
            +{i + 1}h
          </span>
        ))}
      </div>
    </div>
  );
}
