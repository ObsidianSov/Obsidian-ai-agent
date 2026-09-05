import express from 'express';
import cors from 'cors';
import { fileURLToPath } from 'url';
import path from 'path';
import multer from 'multer';
import Papa from 'papaparse';

import tradesRouter from './routes/trades.js';
import strategiesRouter from './routes/strategies.js';
import tagsRouter from './routes/tags.js';
import analyticsRouter from './routes/analytics.js';
import journalRouter from './routes/journal.js';
import db from './database.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Configure multer for file uploads
const storage = multer.memoryStorage();
const upload = multer({ storage });

// API Routes
app.use('/api/trades', tradesRouter);
app.use('/api/strategies', strategiesRouter);
app.use('/api/tags', tagsRouter);
app.use('/api/analytics', analyticsRouter);
app.use('/api/journal', journalRouter);

// Export endpoint
app.get('/api/export', (req, res) => {
  try {
    const trades = db.prepare(`
      SELECT t.*, s.name as strategy_name
      FROM trades t
      LEFT JOIN strategies s ON t.strategy_id = s.id
      ORDER BY t.entry_date DESC
    `).all();

    const csv = Papa.unparse(trades.map(t => ({
      id: t.id,
      symbol: t.symbol,
      side: t.side,
      entry_date: t.entry_date,
      exit_date: t.exit_date,
      entry_price: t.entry_price,
      exit_price: t.exit_price,
      quantity: t.quantity,
      strategy: t.strategy_name,
      pnl: t.pnl,
      pnl_percent: t.pnl_percent,
      notes: t.notes
    })));

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', 'attachment; filename=trades-export.csv');
    res.send(csv);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Import endpoint
app.post('/api/import', upload.single('file'), (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const text = req.file.buffer.toString('utf8');
    const parsed = Papa.parse(text, { header: true, skipEmptyLines: true });
    
    if (parsed.errors.length > 0) {
      return res.status(400).json({ error: 'Invalid CSV format', details: parsed.errors });
    }

    const trades = parsed.data.map(row => ({
      symbol: row.symbol,
      side: row.side || 'long',
      entry_date: row.entry_date,
      exit_date: row.exit_date || null,
      entry_price: parseFloat(row.entry_price),
      exit_price: row.exit_price ? parseFloat(row.exit_price) : null,
      quantity: row.quantity ? parseFloat(row.quantity) : 1,
      pnl: row.pnl ? parseFloat(row.pnl) : null,
      pnl_percent: row.pnl_percent ? parseFloat(row.pnl_percent) : null
    }));

    const insertTrade = db.prepare(`
      INSERT INTO trades (symbol, side, entry_date, exit_date, entry_price, exit_price, quantity, pnl, pnl_percent)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const insertMany = db.transaction((trades) => {
      let imported = 0;
      for (const trade of trades) {
        try {
          if (!trade.symbol || !trade.entry_date || !trade.entry_price) continue;
          insertTrade.run(
            trade.symbol,
            trade.side,
            trade.entry_date,
            trade.exit_date,
            trade.entry_price,
            trade.exit_price,
            trade.quantity,
            trade.pnl,
            trade.pnl_percent
          );
          imported++;
        } catch (e) {
          // Skip invalid rows
        }
      }
      return imported;
    });

    const count = insertMany(trades);
    res.json({ message: `Imported ${count} trades`, imported: count });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Serve static files in production
if (process.env.NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, '../client/dist')));
  
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../client/dist/index.html'));
  });
}

app.listen(PORT, () => {
  console.log(`🚀 Obsidian War-Room API running on port ${PORT}`);
});
