import React, { useState, useEffect } from 'react';
import { Plus, X, BookOpen, Edit2, Trash2, Calendar } from 'lucide-react';

const API_URL = 'http://localhost:3001/api';

export default function Journal() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);

  useEffect(() => {
    fetchEntries();
  }, []);

  const fetchEntries = async () => {
    try {
      const res = await fetch(`${API_URL}/journal`);
      const data = await res.json();
      setEntries(data.entries || []);
    } catch (err) {
      console.error('Failed to fetch journal entries:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const entryData = {
      title: formData.get('title'),
      content: formData.get('content') || ''
    };

    try {
      const url = editingEntry
        ? `${API_URL}/journal/${editingEntry.id}`
        : `${API_URL}/journal`;
      const method = editingEntry ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entryData)
      });

      if (res.ok) {
        setShowModal(false);
        setEditingEntry(null);
        fetchEntries();
      }
    } catch (err) {
      console.error('Failed to save entry:', err);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this journal entry?')) return;
    try {
      const res = await fetch(`${API_URL}/journal/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchEntries();
      }
    } catch (err) {
      console.error('Failed to delete entry:', err);
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="journal-page">
      <div className="flex items-center justify-between mb-4">
        <p className="text-muted">Record your trading thoughts, lessons learned, and market observations</p>
        <button className="btn btn-primary" onClick={() => { setEditingEntry(null); setShowModal(true); }}>
          <Plus size={16} />
          New Entry
        </button>
      </div>

      {/* Journal Entries */}
      <div className="journal-entries">
        {entries.length === 0 ? (
          <div className="empty-state card">
            <BookOpen className="empty-state-icon" size={48} />
            <h3 className="empty-state-title">No Journal Entries Yet</h3>
            <p className="empty-state-text">Start documenting your trading journey and reflections</p>
            <button className="btn btn-primary" onClick={() => setShowModal(true)}>
              <Plus size={16} />
              Write First Entry
            </button>
          </div>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="card journal-entry" style={{ marginBottom: '16px' }}>
              <div className="flex items-center justify-between" style={{ marginBottom: '12px' }}>
                <div className="flex items-center gap-2">
                  <BookOpen size={18} style={{ color: '#00d4ff' }} />
                  <h3 style={{ fontSize: '18px', fontWeight: 600 }}>{entry.title}</h3>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => { setEditingEntry(entry); setShowModal(true); }}
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDelete(entry.id)}
                    style={{ color: '#ef4444' }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              <p style={{ color: '#d1d5db', lineHeight: '1.7', whiteSpace: 'pre-wrap' }}>
                {entry.content}
              </p>
              <div className="flex items-center gap-2" style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
                <Calendar size={14} style={{ color: '#9ca3af' }} />
                <span className="text-muted" style={{ fontSize: '12px' }}>
                  {formatDate(entry.created_at)}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editingEntry ? 'Edit Journal Entry' : 'New Journal Entry'}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="label">Title *</label>
                  <input
                    type="text"
                    name="title"
                    className="input"
                    placeholder="Trading Psychology Notes"
                    defaultValue={editingEntry?.title}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="label">Content</label>
                  <textarea
                    name="content"
                    className="input"
                    rows="10"
                    placeholder="Write your thoughts, lessons learned, or market observations..."
                    defaultValue={editingEntry?.content}
                    style={{ resize: 'vertical', minHeight: '200px' }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingEntry ? 'Update Entry' : 'Save Entry'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <style>{`
        .journal-entry {
          transition: all 0.2s ease;
        }
        .journal-entry:hover {
          border-color: var(--accent-primary);
        }
      `}</style>
    </div>
  );
}
