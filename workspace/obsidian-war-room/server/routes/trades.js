import express from 'express';
import db from '../database.js';
import Papa from 'papaparse';
import fs from 'fs';

const router = express.Router();

// Calculate P&L helper
function calculatePnL(trade) {
  if (trade.exit_price === null || trade.exit_price === undefined) return { pnl: null, pnl_percent: null };
  
  const diff = trade.side === 'long' 
    ? trade.exit_price - trade.entry_price 
    : trade.entry_price - trade.exit_price;
  
  const pnl = diff * trade.quantity;
  const pnlPercent = (diff / trade.entry_price) * 100;
  
  return { pnl, pnl_percent: pnlPercent };
}

// GET all trades with filters
router.get('/', (req, res) => {
  try {
    const { 
      symbol, 
      side, 
      strategy_id, 
      start_date, 
      end_date, 
      min_pnl, 
      max_pnl,
      limit = 100,
      offset = 0 
    } = req.query;

    let query = `
      SELECT t.*, s.name as strategy_name, s.color as strategy_color,
        GROUP_CONCAT(tg.tag_id) as tag_ids
      FROM trades t
      LEFT JOIN strategies s ON t.strategy_id = s.id
      LEFT JOIN trade_tags tg ON t.id = tg.trade_id
      WHERE 1=1
    `;
    const params = [];

    if (symbol) {
      query += ' AND t.symbol LIKE ?';
      params.push(`%${symbol}%`);
    }
    if (side) {
      query += ' AND t.side = ?';
      params.push(side);
    }
    if (strategy_id) {
      query += ' AND t.strategy_id = ?';
      params.push(strategy_id);
    }
    if (start_date) {
      query += ' AND t.entry_date >= ?';
      params.push(start_date);
    }
    if (end_date) {
      query += ' AND t.entry_date <= ?';
      params.push(end_date);
    }
    if (min_pnl) {
      query += ' AND t.pnl >= ?';
      params.push(parseFloat(min_pnl));
    }
    if (max_pnl) {
      query += ' AND t.pnl <= ?';
      params.push(parseFloat(max_pnl));
    }

    query += ' GROUP BY t.id ORDER BY t.entry_date DESC LIMIT ? OFFSET ?';
    params.push(parseInt(limit), parseInt(offset));

    const trades = db.prepare(query).all(...params);
    
    // Get total count
    let countQuery = 'SELECT COUNT(*) as total FROM trades WHERE 1=1';
    const countParams = [];
    if (symbol) { countQuery += ' AND symbol LIKE ?'; countParams.push(`%${symbol}%`); }
    if (side) { countQuery += ' AND side = ?'; countParams.push(side); }
    if (strategy_id) { countQuery += ' AND strategy_id = ?'; countParams.push(strategy_id); }
    if (start_date) { countQuery += ' AND entry_date >= ?'; countParams.push(start_date); }
    if (end_date) { countQuery += ' AND entry_date <= ?'; countParams.push(end_date); }
    
    const { total } = db.prepare(countQuery).get(...countParams);

    res.json({ trades, total, limit: parseInt(limit), offset: parseInt(offset) });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET single trade
router.get('/:id', (req, res) => {
  try {
    const trade = db.prepare(`
      SELECT t.*, s.name as strategy_name, s.color as strategy_color
      FROM trades t
      LEFT JOIN strategies s ON t.strategy_id = s.id
      WHERE t.id = ?
    `).get(req.params.id);

    if (!trade) {
      return res.status(404).json({ error: 'Trade not found' });
    }

    // Get tags
    const tags = db.prepare(`
      SELECT tg.* FROM tags tg
      JOIN trade_tags tt ON tg.id = tt.tag_id
      WHERE tt.trade_id = ?
    `).all(req.params.id);

    trade.tags = tags;
    res.json(trade);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST create trade
router.post('/', (req, res) => {
  try {
    const { symbol, side, entry_date, exit_date, entry_price, exit_price, quantity, strategy_id, notes, tag_ids } = req.body;

    // Validate required fields
    if (!symbol || !side || !entry_date || !entry_price) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    const qty = quantity || 1;
    const calculated = calculatePnL({ side, entry_price, exit_price, quantity: qty });

    const result = db.prepare(`
      INSERT INTO trades (symbol, side, entry_date, exit_date, entry_price, exit_price, quantity, strategy_id, pnl, pnl_percent, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(symbol, side, entry_date, exit_date || null, entry_price, exit_price || null, qty, strategy_id || null, calculated.pnl, calculated.pnl_percent, notes || null);

    const tradeId = result.lastInsertRowid;

    // Add tags
    if (tag_ids && tag_ids.length > 0) {
      const insertTag = db.prepare('INSERT INTO trade_tags (trade_id, tag_id) VALUES (?, ?)');
      tag_ids.forEach(tagId => insertTag.run(tradeId, tagId));
    }

    const trade = db.prepare('SELECT * FROM trades WHERE id = ?').get(tradeId);
    res.status(201).json(trade);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// PUT update trade
router.put('/:id', (req, res) => {
  try {
    const { symbol, side, entry_date, exit_date, entry_price, exit_price, quantity, strategy_id, notes, tag_ids } = req.body;

    const existing = db.prepare('SELECT * FROM trades WHERE id = ?').get(req.params.id);
    if (!existing) {
      return res.status(404).json({ error: 'Trade not found' });
    }

    const updated = {
      symbol: symbol || existing.symbol,
      side: side || existing.side,
      entry_date: entry_date || existing.entry_date,
      exit_date: exit_date !== undefined ? exit_date : existing.exit_date,
      entry_price: entry_price || existing.entry_price,
      exit_price: exit_price !== undefined ? exit_price : existing.exit_price,
      quantity: quantity || existing.quantity,
      strategy_id: strategy_id !== undefined ? strategy_id : existing.strategy_id,
      notes: notes !== undefined ? notes : existing.notes
    };

    const calculated = calculatePnL(updated);

    db.prepare(`
      UPDATE trades SET symbol = ?, side = ?, entry_date = ?, exit_date = ?, 
      entry_price = ?, exit_price = ?, quantity = ?, strategy_id = ?, 
      pnl = ?, pnl_percent = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `).run(updated.symbol, updated.side, updated.entry_date, updated.exit_date,
      updated.entry_price, updated.exit_price, updated.quantity, updated.strategy_id,
      calculated.pnl, calculated.pnl_percent, updated.notes, req.params.id);

    // Update tags
    if (tag_ids !== undefined) {
      db.prepare('DELETE FROM trade_tags WHERE trade_id = ?').run(req.params.id);
      if (tag_ids && tag_ids.length > 0) {
        const insertTag = db.prepare('INSERT INTO trade_tags (trade_id, tag_id) VALUES (?, ?)');
        tag_ids.forEach(tagId => insertTag.run(req.params.id, tagId));
      }
    }

    const trade = db.prepare('SELECT * FROM trades WHERE id = ?').get(req.params.id);
    res.json(trade);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE trade
router.delete('/:id', (req, res) => {
  try {
    const result = db.prepare('DELETE FROM trades WHERE id = ?').run(req.params.id);
    
    if (result.changes === 0) {
      return res.status(404).json({ error: 'Trade not found' });
    }
    
    res.json({ message: 'Trade deleted successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST import CSV
router.post('/import', (req, res) => {
  try {
    const { trades } = req.body;
    
    if (!trades || !Array.isArray(trades)) {
      return res.status(400).json({ error: 'Invalid trades data' });
    }

    const insertTrade = db.prepare(`
      INSERT INTO trades (symbol, side, entry_date, exit_date, entry_price, exit_price, quantity, pnl, pnl_percent)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const insertMany = db.transaction((trades) => {
      let imported = 0;
      for (const trade of trades) {
        try {
          insertTrade.run(
            trade.symbol,
            trade.side || 'long',
            trade.entry_date,
            trade.exit_date || null,
            trade.entry_price,
            trade.exit_price || null,
            trade.quantity || 1,
            trade.pnl || null,
            trade.pnl_percent || null
          );
          imported++;
        } catch (e) {
          // Skip invalid trades
        }
      }
      return imported;
    });

    const count = insertMany(trades);
    res.json({ message: `Imported ${count} trades`, count });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET export CSV
router.get('/export/csv', (req, res) => {
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

export default router;
