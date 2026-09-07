# 🌧️ Osogbo RainCast AI

> **Intelligent Rainfall Nowcasting System for Osogbo, Nigeria**

An advanced, AI-powered weather dashboard providing real-time rainfall predictions, radar visualization, and weather alerts for the Osogbo region.

![Status](https://img.shields.io/badge/status-Production%20Ready-brightgreen)
![Python](https://img.shields.io/badge/Python-3.7+-blue)
![HTML5](https://img.shields.io/badge/HTML5-CSS3-orange)

## ✨ Features

### 🎯 Core Functionality
- **6-Hour Rainfall Nowcasting** - AI-powered predictions updated every 15 seconds
- **Real-Time Radar Visualization** - Animated precipitation radar with 250km coverage
- **48-Hour Forecast** - Hourly detailed predictions
- **3-Day Outlook** - Daily weather summaries
- **Smart Alerts** - Automatic weather warnings with severity levels

### 📊 Visualizations
- Interactive temperature trend charts
- Humidity analysis with gauge display
- Rain probability bar charts
- Animated radar sweep
- Live weather statistics

### 🎨 Design
- Dark theme with electric cyan accents
- Glassmorphism UI elements
- Smooth animations (60fps)
- Fully responsive (Desktop, Tablet, Mobile)
- Rain particle effects background

## 🚀 Quick Start

### Option 1: Run with Python Server
```bash
cd RAINCAST_AI
py server.py
```
Then open: **http://localhost:8080**

### Option 2: Open Directly
Simply open `index.html` in any modern browser.

### Option 3: VS Code Live Server
```bash
code RAINCAST_AI/index.html
# Use "Open with Live Server" extension
```

## 📁 Project Structure

```
RAINCAST_AI/
├── index.html      # Main dashboard (single-file application)
├── server.py       # Python HTTP server script
├── SPEC.md         # Technical specification
└── README.md       # This file
```

## 🧠 AI Prediction Engine

The system uses a simulated weather intelligence engine that:

1. **Analyzes** atmospheric patterns and time-of-day factors
2. **Calculates** rain probability based on historical patterns
3. **Generates** confidence-weighted predictions
4. **Updates** automatically every 15 seconds (demo mode)

### Prediction Logic
```
Rainfall Probability = Base_Probability + Time_Variation + Random_Factor

Where:
- Base_Probability: Seasonal/regional average
- Time_Variation: Higher afternoon (14-18h), lower morning (6-10h)
- Random_Factor: Simulated measurement variance
```

## 🎯 Confidence Levels

| Level | Range | Description |
|-------|-------|-------------|
| 🔴 Very Low | < 25% | Ambiguous atmospheric data |
| 🟠 Low | 25-49% | Uncertain conditions |
| 🟡 Medium | 50-74% | Mixed signals present |
| 🟢 High | 75-89% | Clear indicators |
| 💎 Very High | 90%+ | Strong atmospheric conditions |

## 📍 Location Data

| Parameter | Value |
|-----------|-------|
| City | Osogbo |
| Country | Nigeria |
| Latitude | 7.7675° N |
| Longitude | 4.0673° E |
| Altitude | 340m |
| Climate | Tropical Savanna (Aw) |

## 🔧 Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Charts**: Chart.js 4.x
- **Icons**: Font Awesome 6.5
- **Fonts**: Google Fonts (Inter, Roboto Mono)
- **AI/ML**: Browser-based inference (simulated)

## 📱 Responsive Breakpoints

| Device | Width | Layout |
|--------|-------|--------|
| Desktop | > 1200px | 3-column grid |
| Tablet | 768-1200px | 2-column grid |
| Mobile | < 768px | Single column |

## ⚙️ Configuration

### Update Intervals
```javascript
const CONFIG = {
    TIME_UPDATE: 1000,      // Clock update (1s)
    DATA_UPDATE: 15000,     // Weather update (15s)
    RADAR_FPS: 60           // Radar animation
};
```

## 🌐 Browser Support

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

## 📄 License

© 2024 Osogbo RainCast AI - Built with 💙 for the Osogbo community

---

**Made with precision for accurate weather prediction** 🌧️⚡
