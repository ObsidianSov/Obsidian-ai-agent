import Database from 'better-sqlite3';
import { v4 as uuidv4 } from 'uuid';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = path.join(__dirname, 'trading.db');

const db = new Database(dbPath);

// Enable foreign keys
db.pragma('foreign_keys = ON');

// Create tables
db.exec(`
  CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT DEFAULT '#00d4ff',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#9ca3af',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('long', 'short')),
    entry_date DATETIME NOT NULL,
    exit_date DATETIME,
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity REAL DEFAULT 1,
    strategy_id INTEGER,
    pnl REAL,
    pnl_percent REAL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
  );

  CREATE TABLE IF NOT EXISTS trade_tags (
    trade_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (trade_id, tag_id),
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER,
    title TEXT NOT NULL,
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE SET NULL
  );

  CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
  CREATE INDEX IF NOT EXISTS idx_trades_entry_date ON trades(entry_date);
  CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
`);

// Calculate P&L for a trade
function calculatePnL(trade) {
  if (trade.exit_price === null || trade.exit_price === undefined) return null;
  
  const diff = trade.side === 'long' 
    ? trade.exit_price - trade.entry_price 
    : trade.entry_price - trade.exit_price;
  
  const pnl = diff * trade.quantity;
  const pnlPercent = (diff / trade.entry_price) * 100 * (trade.side === 'long' ? 1 : 1);
  
  return { pnl, pnl_percent: pnlPercent };
}

// Seed demo data
function seedDemoData() {
  const strategyCount = db.prepare('SELECT COUNT(*) as count FROM strategies').get();
  
  if (strategyCount.count === 0) {
    // Insert strategies
    const insertStrategy = db.prepare('INSERT INTO strategies (name, description, color) VALUES (?, ?, ?)');
    insertStrategy.run('Breakout', 'Trend following breakout trades', '#00d4ff');
    insertStrategy.run('Mean Reversion', 'Contrarian trades at extremes', '#f59e0b');
    insertStrategy.run('Scalping', 'Quick in-and-out trades', '#10b981');
    insertStrategy.run('Swing Trade', 'Multi-day positions', '#8b5cf6');
    
    // Insert tags
    const insertTag = db.prepare('INSERT INTO tags (name, color) VALUES (?, ?)');
    insertTag.run('High Confidence', '#10b981');
    insertTag.run('News Play', '#f59e0b');
    insertTag.run('Gap Fill', '#ef4444');
    insertTag.run('Earnings', '#8b5cf6');
    insertTag.run('Technical Setup', '#00d4ff');
    
    // Insert demo trades
    const insertTrade = db.prepare(`
      INSERT INTO trades (symbol, side, entry_date, exit_date, entry_price, exit_price, quantity, strategy_id, pnl, pnl_percent, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    const strategies = [1, 2, 3, 4]; // IDs of inserted strategies
    const symbols = ['AAPL', 'TSLA', 'NVDA', 'SPY', 'QQQ', 'MSFT', 'GOOGL', 'AMZN', 'META', 'AMD'];
    const tags = [1, 2, 3, 4, 5];
    
    // Generate 60 demo trades over the past 6 months
    const baseDate = new Date();
    baseDate.setMonth(baseDate.getMonth() - 6);
    
    for (let i = 0; i < 60; i++) {
      const strategyId = strategies[Math.floor(Math.random() * strategies.length)];
      const symbol = symbols[Math.floor(Math.random() * symbols.length)];
      const side = Math.random() > 0.5 ? 'long' : 'short';
      
      // Random date within range
      const entryDate = new Date(baseDate.getTime() + Math.random() * (Date.now() - baseDate.getTime()));
      const duration = Math.random() * 30 * 24 * 60 * 60 * 1000; // 0-30 days in ms
      const exitDate = new Date(entryDate.getTime() + duration);
      
      // Random prices
      const basePrice = 50 + Math.random() * 450;
      const entryPrice = basePrice;
      const exitVariation = (Math.random() - 0.45) * 0.2 * basePrice; // Slight positive bias
      const exitPrice = basePrice + exitVariation;
      const quantity = Math.floor(10 + Math.random() * 190);
      
      const diff = side === 'long' ? exitPrice - entryPrice : entryPrice - exitPrice;
      const pnl = diff * quantity;
      const pnlPercent = (diff / entryPrice) * 100;
      
      const notes = [
        'Strong momentum on the 1-hour chart. Entered on breakout above resistance.',
        'Pulled back to key support. Looking for continuation.',
        'Gap up at open. Fade the gap setup worked well.',
        'Earnings play. IV crush after report.',
        'Multiple timeframe alignment. High conviction setup.',
        '',
        'Tight stop placement. Managed risk carefully.',
        'Patience paid off. Waited for the setup to develop.'
      ][Math.floor(Math.random() * 8)];
      
      insertTrade.run(
        symbol,
        side,
        entryDate.toISOString(),
        exitDate.toISOString(),
        entryPrice,
        exitPrice,
        quantity,
        strategyId,
        pnl,
        pnlPercent,
        notes
      );
      
      // Randomly assign tags (30% chance each)
      const tradeId = i + 1;
      const insertTradeTag = db.prepare('INSERT INTO trade_tags (trade_id, tag_id) VALUES (?, ?)');
      tags.forEach(tagId => {
        if (Math.random() < 0.3) {
          try {
            insertTradeTag.run(tradeId, tagId);
          } catch (e) {
            // Ignore duplicate errors
          }
        }
      });
    }
    
    // Add some journal entries
    const insertJournal = db.prepare('INSERT INTO journal_entries (title, content) VALUES (?, ?)');
    insertJournal.run('Trading Psychology Notes', 'Focus on process over outcomes. A losing trade can still be a good trade if risk was managed properly.');
    insertJournal.run('Strategy Review - Week 1', 'Breakout strategy underperforming this week. Need to adjust entry criteria for choppy markets.');
    insertJournal.run('Risk Management Reminder', 'Never risk more than 1% per trade. Keep position sizes small until account grows.');
    
    console.log('Demo data seeded successfully!');
  }
}

// Run seed on startup
seedDemoData();

export default db;
