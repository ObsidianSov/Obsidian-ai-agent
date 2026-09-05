# Obsidian War-Room - Trading Journal

## Concept & Vision

A tactical trading journal that transforms market data into actionable intelligence. The interface evokes a military command center—dark, precise, and powerful. Every chart tells a story of battles won and lost in the markets. This isn't just a log; it's where traders analyze their performance, refine strategies, and execute with precision.

## Design Language

### Aesthetic Direction
Dark tactical command center with cyan/amber accent lighting. Think Bloomberg Terminal meets military war room. Data-dense but highly organized.

### Color Palette
- **Background Primary**: `#0a0e17` (deep space black)
- **Background Secondary**: `#111827` (panel background)
- **Background Tertiary**: `#1f2937` (card/elevated surfaces)
- **Accent Primary**: `#00d4ff` (cyan - primary actions, highlights)
- **Accent Secondary**: `#f59e0b` (amber - warnings, key metrics)
- **Success**: `#10b981` (green - profits, wins)
- **Danger**: `#ef4444` (red - losses, alerts)
- **Text Primary**: `#f9fafb` (white)
- **Text Secondary**: `#9ca3af` (muted gray)
- **Border**: `#374151` (subtle borders)

### Typography
- **Headings**: `JetBrains Mono` - monospace, tactical feel
- **Body**: `Inter` - clean, readable data
- **Numbers/Stats**: `JetBrains Mono` - aligned, precise

### Spatial System
- Base unit: 4px
- Card padding: 24px
- Section gaps: 32px
- Border radius: 8px (cards), 4px (inputs/buttons)

### Motion Philosophy
- Subtle pulse animations on live data
- Smooth transitions (200ms ease-out) for state changes
- Number counters animate on value changes
- Cards lift slightly on hover (transform + shadow)

### Visual Assets
- Lucide icons for UI elements
- Custom SVG charts (Chart.js)
- Grid pattern backgrounds for tactical feel
- Glow effects on key metrics

## Layout & Structure

### Navigation (Left Sidebar - 64px collapsed, 240px expanded)
- Logo at top
- Dashboard icon
- Trades icon
- Analytics icon
- Strategies icon
- Journal icon
- Settings icon
- Collapse toggle at bottom

### Main Content Area
- **Top Bar**: Page title, date range selector, quick stats
- **Content Grid**: Responsive cards with metrics
- **Footer**: Last sync time, version

### Pages

1. **Dashboard** - Overview with key metrics, recent trades, equity curve
2. **Trades** - Full trade log with filters, add/edit trade modal
3. **Analytics** - Deep performance charts, win rate, expectancy
4. **Strategies** - Strategy performance breakdown
5. **Journal** - Trade notes and reflections
6. **Settings** - Account, preferences, data import/export

## Features & Interactions

### Trade Logging
- Quick add trade button (floating action button)
- Trade form fields:
  - Symbol (autocomplete from watchlist)
  - Entry date/time, exit date/time
  - Entry price, exit price
  - Quantity/contracts
  - Side (Long/Short)
  - Strategy (dropdown)
  - Tags (multi-select)
  - Notes (rich text)
  - Screenshots (drag & drop)
- Auto-calculate P&L, R-multiple, duration
- Validation: required fields, logical price checks

### Dashboard Metrics
- **Total P&L** (daily, weekly, monthly, all-time)
- **Win Rate** (percentage with trend arrow)
- **Profit Factor** (wins/losses ratio)
- **Average Win / Average Loss**
- **Best Trade / Worst Trade**
- **Current Streak** (wins/losses)
- **Max Drawdown**
- **Sharpe Ratio** (optional, advanced)

### Equity Curve Chart
- Line chart showing cumulative P&L over time
- Toggle: Daily, Weekly, Monthly
- Drawdown overlay (secondary axis)
- Hover shows exact values

### Trade Table
- Columns: Date, Symbol, Side, Qty, Entry, Exit, P&L, % Return, Strategy, Tags
- Sortable columns
- Filters: Date range, symbol, side, strategy, tags, P&L range
- Row click opens trade detail/edit modal
- Bulk select for tagging
- Pagination (25 per page)

### Analytics Charts
- **Win Rate by Strategy** (bar chart)
- **P&L Distribution** (histogram)
- **Monthly Returns** (heatmap or bar chart)
- **Trade Duration Analysis** (scatter plot)
- **Cumulative P&L** (area chart)

### Strategy Tracking
- List of strategies with:
  - Total trades
  - Win rate
  - Average R
  - Total P&L
- Click to filter trades by strategy

### Journal/Notes
- Notes attached to trades
- Standalone journal entries
- Tags for organization

### Data Management
- Export to CSV
- Import from CSV (with mapping)
- Demo data included for testing

## Component Inventory

### StatCard
- Icon, label, value, trend indicator
- States: default, loading (skeleton), empty
- Hover: subtle lift and glow

### TradeRow
- All trade data in compact row
- Hover: highlight, show quick actions
- Selected: cyan border

### Button
- Variants: primary (cyan), secondary (gray), danger (red), ghost
- States: default, hover, active, disabled, loading
- Sizes: sm, md, lg

### Input
- Label, input field, helper text, error message
- States: default, focus (cyan glow), error (red border), disabled

### Select/Dropdown
- Single and multi-select
- Search/filter for long lists
- Custom styling to match theme

### Modal
- Overlay with backdrop blur
- Header, content, footer
- Close on escape, backdrop click, or X button
- Smooth fade-in animation

### Chart
- Consistent styling across all charts
- Tooltips match design language
- Legend positioned consistently
- Responsive sizing

### Sidebar Navigation
- Icon-only collapsed state
- Tooltip on hover in collapsed mode
- Active state with cyan indicator

## Technical Approach

### Stack
- **Frontend**: React 18 with Vite
- **Styling**: CSS Modules or styled-components
- **Charts**: Chart.js with react-chartjs-2
- **Icons**: Lucide React
- **State**: React Context + useReducer
- **Routing**: React Router v6
- **Backend**: Express.js (Node)
- **Database**: SQLite with better-sqlite3
- **API**: RESTful JSON

### Data Model

**Trade**
```
id: integer (primary key)
symbol: string
side: enum ('long', 'short')
entry_date: datetime
exit_date: datetime
entry_price: decimal
exit_price: decimal
quantity: decimal
strategy_id: integer (foreign key)
pnl: decimal (calculated)
pnl_percent: decimal (calculated)
notes: text
created_at: datetime
updated_at: datetime
```

**Strategy**
```
id: integer (primary key)
name: string
description: text
color: string
created_at: datetime
```

**Tag**
```
id: integer (primary key)
name: string
color: string
```

**TradeTag** (junction)
```
trade_id: integer
tag_id: integer
```

**JournalEntry**
```
id: integer (primary key)
trade_id: integer (nullable, foreign key)
title: string
content: text
created_at: datetime
```

### API Endpoints
- `GET /api/trades` - List trades (with filters)
- `GET /api/trades/:id` - Single trade
- `POST /api/trades` - Create trade
- `PUT /api/trades/:id` - Update trade
- `DELETE /api/trades/:id` - Delete trade
- `GET /api/strategies` - List strategies
- `POST /api/strategies` - Create strategy
- `GET /api/tags` - List tags
- `POST /api/tags` - Create tag
- `GET /api/analytics` - Aggregated stats
- `GET /api/journal` - List journal entries
- `POST /api/journal` - Create entry
- `POST /api/import` - Import CSV
- `GET /api/export` - Export CSV

### Demo Data
Pre-populated with 50+ sample trades across multiple strategies for demonstration.
