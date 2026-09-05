import express from 'express';
import db from '../database.js';

const router = express.Router();

// GET all tags
router.get('/', (req, res) => {
  try {
    const tags = db.prepare(`
      SELECT t.*, COUNT(tt.trade_id) as usage_count
      FROM tags t
      LEFT JOIN trade_tags tt ON t.id = tt.tag_id
      GROUP BY t.id
      ORDER BY t.name
    `).all();

    res.json(tags);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST create tag
router.post('/', (req, res) => {
  try {
    const { name, color } = req.body;

    if (!name) {
      return res.status(400).json({ error: 'Name is required' });
    }

    const result = db.prepare('INSERT INTO tags (name, color) VALUES (?, ?)').run(name, color || '#9ca3af');
    
    const tag = db.prepare('SELECT * FROM tags WHERE id = ?').get(result.lastInsertRowid);
    res.status(201).json(tag);
  } catch (error) {
    if (error.message.includes('UNIQUE')) {
      return res.status(400).json({ error: 'Tag already exists' });
    }
    res.status(500).json({ error: error.message });
  }
});

// PUT update tag
router.put('/:id', (req, res) => {
  try {
    const { name, color } = req.body;

    const existing = db.prepare('SELECT * FROM tags WHERE id = ?').get(req.params.id);
    if (!existing) {
      return res.status(404).json({ error: 'Tag not found' });
    }

    db.prepare('UPDATE tags SET name = ?, color = ? WHERE id = ?').run(name || existing.name, color || existing.color, req.params.id);

    const tag = db.prepare('SELECT * FROM tags WHERE id = ?').get(req.params.id);
    res.json(tag);
  } catch (error) {
    if (error.message.includes('UNIQUE')) {
      return res.status(400).json({ error: 'Tag name already exists' });
    }
    res.status(500).json({ error: error.message });
  }
});

// DELETE tag
router.delete('/:id', (req, res) => {
  try {
    const result = db.prepare('DELETE FROM tags WHERE id = ?').run(req.params.id);
    
    if (result.changes === 0) {
      return res.status(404).json({ error: 'Tag not found' });
    }
    
    res.json({ message: 'Tag deleted successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

export default router;
