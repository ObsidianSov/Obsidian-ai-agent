# Obsidian War-Room Trading Journal

A tactical trading journal that transforms market data into actionable intelligence. The interface evokes a military command center—dark, precise, and powerful.

![Obsidian War-Room](https://img.shields.io/badge/Status-Ready-brightgreen)
![Node](https://img.shields.io/badge/Node.js-18+-green)
![License](https://img.shields.io/badge/License-MIT-blue)

## Features

- 📊 **Dashboard** - Key metrics, equity curve, recent trades
- 📈 **Trade Log** - Full trade history with filters and CRUD operations
- 📉 **Analytics** - Performance charts, win rate analysis, strategy breakdown
- 🎯 **Strategies** - Track performance by trading strategy
- 📔 **Journal** - Trading notes and reflections
- ⚙️ **Settings** - Data import/export (CSV)

## Tech Stack

- **Frontend**: React 18, Vite, Chart.js, Lucide Icons
- **Backend**: Express.js, Node.js
- **Database**: SQLite with better-sqlite3
- **Styling**: Custom CSS with dark tactical theme

## Quick Start

### Prerequisites

- Node.js 18 or higher
- npm

### Installation

```bash
# Install all dependencies
npm run install:all

# Or install separately
npm install
cd client && npm install
```

### Running the App

```bash
# Run both server and client concurrently
npm run dev
```

The app will be available at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:3001

### Running Separately

```bash
# Terminal 1 - Start backend
npm run server

# Terminal 2 - Start frontend
npm run client
```

### Build for Production

```bash
npm run build
```

## Project Structure

```
obsidian-war-room/
├── client/                 # React frontend
│   ├── src/
│   │   ├── pages/         # Page components
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Trades.jsx
│   │   │   ├── Analytics.jsx
│   │   │   ├── Strategies.jsx
│   │   │   ├── Journal.jsx
│   │   │   └── Settings.jsx
│   │   ├── App.jsx         # Main app component
│   │   ├── main.jsx        # Entry point
│   │   └── index.css        # Global styles
│   └── package.json
├── server/                 # Express backend
│   ├── routes/             # API routes
│   │   ├── trades.js
│   │   ├── strategies.js
│   │   ├── analytics.js
│   │   ├── tags.js
│   │   └── journal.js
│   ├── database.js         # SQLite setup
│   └── index.js            # Server entry
├── SPEC.md                 # Design specification
└── package.json
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trades` | List trades (with filters) |
| POST | `/api/trades` | Create trade |
| PUT | `/api/trades/:id` | Update trade |
| DELETE | `/api/trades/:id` | Delete trade |
| GET | `/api/strategies` | List strategies |
| POST | `/api/strategies` | Create strategy |
| GET | `/api/analytics` | Analytics overview |
| GET | `/api/analytics/equity-curve` | Equity curve data |
| GET | `/api/journal` | List journal entries |
| POST | `/api/journal` | Create journal entry |
| GET | `/api/export` | Export trades to CSV |
| POST | `/api/import` | Import trades from CSV |

## Demo Data

The app comes pre-loaded with:
- 4 trading strategies (Breakout, Mean Reversion, Scalping, Swing Trade)
- 5 tags (High Confidence, News Play, Gap Fill, Earnings, Technical Setup)
- 60 sample trades across 6 months
- 3 journal entries

## Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Deep Black | `#0a0e17` | Primary background |
| Panel | `#111827` | Secondary background |
| Card | `#1f2937` | Elevated surfaces |
| Cyan | `#00d4ff` | Primary accent |
| Amber | `#f59e0b` | Secondary accent |
| Green | `#10b981` | Profit/success |
| Red | `#ef4444` | Loss/danger |

## License

MIT © 2024 Obsidian War-Room
