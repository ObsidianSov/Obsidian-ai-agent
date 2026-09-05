import React, { useState, useEffect } from 'react';
import { Plus, X, Target } from 'lucide-react';

const API_URL = 'http://localhost:3001/api';

export default function Strategies() {
  const [strategies, setStrategies] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [strategiesRes, analyticsRes] = await Promise.all([
        fetch(`${API_URL}/strategies`),
        fetch(`${API_URL}/analytics`)
      ]);
      const strategiesData = await strategiesRes.json();
      const analyticsData = await analyticsRes.json();
      setStrategies(strategiesData.strategies || []);
      setAnalytics(analyticsData.strategy_performance || []);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const strategyData = {
      name: formData.get('name'),
      description: formData.get('description') || '',
      color: formData.get('color') || '#00d4ff'
    };

    try {
      const url = editingStrategy
        ? `${API_URL}/strategies/${editingStrategy.id}`
        : `${API_URL}/strategies`;
      const method = editingStrategy ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(strategyData)
      });

      if (res.ok) {
        setShowModal(false);
        setEditingStrategy(null);
        fetchData();
      }
    } catch (err) {
      console.error('Failed to save strategy:', err);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this strategy?')) return;
    try {
      const res = await fetch(`${API_URL}/strategies/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchData();
      }
    } catch (err) {
      console.error('Failed to delete strategy:', err);
    }
  };

  const formatCurrency = (val) => {
    if (val === null || val === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(val);
  };

  const getStrategyStats = (strategyId) => {
    return analytics.find(a => a.id === strategyId) || {};
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="strategies-page">
      <div className="flex items-center justify-between mb-4">
        <p className="text-muted">Track performance and manage your trading strategies</p>
        <button className="btn btn-primary" onClick={() => { setEditingStrategy(null); setShowModal(true); }}>
          <Plus size={16} />
          Add Strategy
        </button>
      </div>

      {/* Strategy Cards */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
        {strategies.map((strategy) => {
          const stats = getStrategyStats(strategy.id);
          return (
            <div key={strategy.id} className="card" style={{ borderTop: `3px solid ${strategy.color}` }}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div
                    style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '8px',
                      backgroundColor: `${strategy.color}20`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    <Target size={20} style={{ color: strategy.color }} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: 600 }}>{strategy.name}</h3>
                    <p className="text-muted" style={{ fontSize: '12px' }}>
                      {strategy.description || 'No description'}
                    </p>
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '20px' }}>
                <div>
                  <div className="stat-card-label">Total Trades</div>
                  <div className="font-mono" style={{ fontSize: '20px', fontWeight: 600 }}>
                    {stats.total_trades || 0}
                  </div>
                </div>
                <div>
                  <div className="stat-card-label">Win Rate</div>
                  <div className="font-mono" style={{ fontSize: '20px', fontWeight: 600 }}>
                    {stats.win_rate?.toFixed(1) || 0}%
                  </div>
                </div>
                <div>
                  <div className="stat-card-label">Avg R-Multiple</div>
                  <div className={`font-mono ${(stats.avg_r || 0) >= 0 ? 'text-positive' : 'text-negative'}`}
                    style={{ fontSize: '20px', fontWeight: 600 }}>
                    {stats.avg_r ? `R${stats.avg_r >= 0 ? '+' : ''}${stats.avg_r.toFixed(2)}` : '-'}
                  </div>
                </div>
                <div>
                  <div className="stat-card-label">Total P&L</div>
                  <div className={`font-mono ${(stats.total_pnl || 0) >= 0 ? 'text-positive' : 'text-negative'}`}
                    style={{ fontSize: '20px', fontWeight: 600 }}>
                    {formatCurrency(stats.total_pnl)}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: '20px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => { setEditingStrategy(strategy); setShowModal(true); }}
                >
                  Edit
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => handleDelete(strategy.id)}
                  style={{ color: '#ef4444' }}
                >
                  Delete
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {strategies.length === 0 && (
        <div className="empty-state card">
          <Target className="empty-state-icon" size={48} />
          <h3 className="empty-state-title">No Strategies Yet</h3>
          <p className="empty-state-text">Create your first trading strategy to track performance</p>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={16} />
            Add Strategy
          </button>
        </div>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" style={{ maxWidth: '450px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editingStrategy ? 'Edit Strategy' : 'Add New Strategy'}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="label">Strategy Name *</label>
                  <input
                    type="text"
                    name="name"
                    className="input"
                    placeholder="Breakout Trading"
                    defaultValue={editingStrategy?.name}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="label">Description</label>
                  <textarea
                    name="description"
                    className="input"
                    rows="3"
                    placeholder="Describe your trading strategy..."
                    defaultValue={editingStrategy?.description}
                    style={{ resize: 'vertical' }}
                  />
                </div>

                <div className="form-group">
                  <label className="label">Color</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      name="color"
                      defaultValue={editingStrategy?.color || '#00d4ff'}
                      style={{ width: '50px', height: '40px', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
                    />
                    <input
                      type="text"
                      className="input"
                      placeholder="#00d4ff"
                      defaultValue={editingStrategy?.color || '#00d4ff'}
                      pattern="^#[0-9A-Fa-f]{6}$"
                      style={{ flex: 1 }}
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingStrategy ? 'Update Strategy' : 'Create Strategy'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
