/**
 * RainfallLegend Component
 * 
 * Color legend for rainfall intensity
 */

import React from 'react';

const LEGEND_ITEMS = [
  { label: 'None', color: 'rgba(255, 255, 255, 0)', textColor: '#fff' },
  { label: '< 1 mm/h', color: 'rgba(200, 230, 255, 0.6)', textColor: '#b8c5d6' },
  { label: '1-5 mm/h', color: 'rgba(100, 180, 255, 0.8)', textColor: '#fff' },
  { label: '5-10 mm/h', color: 'rgba(50, 150, 255, 0.9)', textColor: '#fff' },
  { label: '10-20 mm/h', color: 'rgba(50, 100, 255, 1)', textColor: '#fff' },
  { label: '20-50 mm/h', color: 'rgba(150, 50, 255, 1)', textColor: '#fff' },
  { label: '> 50 mm/h', color: 'rgba(200, 50, 200, 1)', textColor: '#fff' }
];

export function RainfallLegend() {
  return (
    <div className="rainfall-legend">
      <h4>Rainfall Intensity</h4>
      <div className="legend-items">
        {LEGEND_ITEMS.map((item, index) => (
          <div key={index} className="legend-item">
            <span 
              className="color-box"
              style={{ backgroundColor: item.color }}
            ></span>
            <span className="label" style={{ color: item.textColor }}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
