import express from 'express';
import db from '../database.js';

const router = express.Router();

// GET all strategies with stats
router.get('/', (req, res) => {
  try {
    const strategies = db.prepare(`
      SELECT s.*, 
        COUNT(t.id) as trade_count,
        SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as win_count,
        SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) as loss_count,
        SUM(t.pnl) as total_pnl,
        AVG(t.pnl_percent) as avg_pnl_percent
      FROM strategies s
      LEFT JOIN trades t ON s.id = t.strategy_id AND t.exit_date IS NOT NULL
      GROUP BY s.id
      ORDER BY s.name
    `).all();

    res.json(strategies.map(s => ({
      ...s,
      win_rate: s.trade_count > 0 ? (s.win_count / s.trade_count) * 100 : 0
    })));
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET single strategy
router.get('/:id', (req, res) => {
  try {
    const strategy = db.prepare('SELECT * FROM strategies WHERE id = ?').get(req.params.id);
    
    if (!strategy) {
      return res.status(404).json({ error: 'Strategy not found' });
    }

    // Get stats
    const stats = db.prepare(`
      SELECT 
        COUNT(*) as trade_count,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
        SUM(pnl) as total_pnl,
        AVG(pnl) as avg_pnl,
        MAX(pnl) as best_trade,
        MIN(pnl) as worst_trade
      FROM trades 
      WHERE strategy_id = ? AND exit_date IS NOT NULL
    `).get(req.params.id);

    res.json({ ...strategy, ...stats });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST create strategy
router.post('/', (req, res) => {
  try {
    const { name, description, color } = req.body;

    if (!name) {
      return res.status(400).json({ error: 'Name is required' });
    }

    const result = db.prepare('INSERT INTO strategies (name, description, color) VALUES (?, ?, ?)').run(name, description || null, color || '#00d4ff');
    
    const strategy = db.prepare('SELECT * FROM strategies WHERE id = ?').get(result.lastInsertRowid);
    res.status(201).json(strategy);
  } catch (error) {
    if (error.message.includes('UNIQUE')) {
      return res.status(400).json({ error: 'Strategy name already exists' });
    }
    res.status(500).json({ error: error.message });
  }
});

// PUT update strategy
router.put('/:id', (req, res) => {
  try {
    const { name, description, color } = req.body;

    const existing = db.prepare('SELECT * FROM strategies WHERE id = ?').get(req.params.id);
    if (!existing) {
      return res.status(404).json({ error: 'Strategy not found' });
    }

    db.prepare(`
      UPDATE strategies SET name = ?, description = ?, color = ? WHERE id = ?
    `).run(name || existing.name, description !== undefined ? description : existing.description, color || existing.color, req.params.id);

    const strategy = db.prepare('SELECT * FROM strategies WHERE id = ?').get(req.params.id);
    res.json(strategy);
  } catch (error) {
    if (error.message.includes('UNIQUE')) {
      return res.status(400).json({ error: 'Strategy name already exists' });
    }
    res.status(500).json({ error: error.message });
  }
});

// DELETE strategy
router.delete('/:id', (req, res) => {
  try {
    // Check if strategy has trades
    const tradeCount = db.prepare('SELECT COUNT(*) as count FROM trades WHERE strategy_id = ?').get(req.params.id);
    
    if (tradeCount.count > 0) {
      return res.status(400).json({ error: 'Cannot delete strategy with existing trades. Reassign trades first.' });
    }

    const result = db.prepare('DELETE FROM strategies WHERE id = ?').run(req.params.id);
    
    if (result.changes === 0) {
      return res.status(404).json({ error: 'Strategy not found' });
    }
    
    res.json({ message: 'Strategy deleted successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

export default router;
