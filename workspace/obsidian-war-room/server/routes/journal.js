import express from 'express';
import db from '../database.js';

const router = express.Router();

// GET all journal entries
router.get('/', (req, res) => {
  try {
    const entries = db.prepare(`
      SELECT j.*, t.symbol, t.side
      FROM journal_entries j
      LEFT JOIN trades t ON j.trade_id = t.id
      ORDER BY j.created_at DESC
    `).all();

    res.json({ entries });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET single journal entry
router.get('/:id', (req, res) => {
  try {
    const entry = db.prepare(`
      SELECT j.*, t.symbol, t.side, t.entry_price, t.exit_price, t.pnl
      FROM journal_entries j
      LEFT JOIN trades t ON j.trade_id = t.id
      WHERE j.id = ?
    `).get(req.params.id);

    if (!entry) {
      return res.status(404).json({ error: 'Entry not found' });
    }

    res.json(entry);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST create journal entry
router.post('/', (req, res) => {
  try {
    const { title, content, trade_id } = req.body;

    if (!title) {
      return res.status(400).json({ error: 'Title is required' });
    }

    const result = db.prepare('INSERT INTO journal_entries (title, content, trade_id) VALUES (?, ?, ?)').run(title, content || null, trade_id || null);
    
    const entry = db.prepare('SELECT * FROM journal_entries WHERE id = ?').get(result.lastInsertRowid);
    res.status(201).json(entry);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// PUT update journal entry
router.put('/:id', (req, res) => {
  try {
    const { title, content, trade_id } = req.body;

    const existing = db.prepare('SELECT * FROM journal_entries WHERE id = ?').get(req.params.id);
    if (!existing) {
      return res.status(404).json({ error: 'Entry not found' });
    }

    db.prepare('UPDATE journal_entries SET title = ?, content = ?, trade_id = ? WHERE id = ?').run(
      title || existing.title,
      content !== undefined ? content : existing.content,
      trade_id !== undefined ? trade_id : existing.trade_id,
      req.params.id
    );

    const entry = db.prepare('SELECT * FROM journal_entries WHERE id = ?').get(req.params.id);
    res.json(entry);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE journal entry
router.delete('/:id', (req, res) => {
  try {
    const result = db.prepare('DELETE FROM journal_entries WHERE id = ?').run(req.params.id);
    
    if (result.changes === 0) {
      return res.status(404).json({ error: 'Entry not found' });
    }
    
    res.json({ message: 'Entry deleted successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

export default router;
