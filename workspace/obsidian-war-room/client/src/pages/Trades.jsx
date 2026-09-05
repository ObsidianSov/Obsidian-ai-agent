import React, { useState, useEffect } from 'react';
import { Plus, X, Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react';

const API_URL = 'http://localhost:3001/api';

export default function Trades() {
  const [trades, setTrades] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingTrade, setEditingTrade] = useState(null);
  const [filters, setFilters] = useState({
    symbol: '',
    side: '',
    strategy_id: '',
    search: ''
  });
  const [pagination, setPagination] = useState({
    page: 1,
    limit: 25,
    total: 0,
    totalPages: 0
  });

  useEffect(() => {
    fetchTrades();
    fetchStrategies();
  }, [pagination.page, filters]);

  const fetchTrades = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: pagination.page,
        limit: pagination.limit,
        sort: 'exit_date',
        order: 'desc'
      });

      if (filters.symbol) params.append('symbol', filters.symbol);
      if (filters.side) params.append('side', filters.side);
      if (filters.strategy_id) params.append('strategy_id', filters.strategy_id);
      if (filters.search) params.append('search', filters.search);

      const res = await fetch(`${API_URL}/trades?${params}`);
      const data = await res.json();
      setTrades(data.trades || []);
      setPagination(prev => ({
        ...prev,
        total: data.total || 0,
        totalPages: Math.ceil((data.total || 0) / prev.limit)
      }));
    } catch (err) {
      console.error('Failed to fetch trades:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStrategies = async () => {
    try {
      const res = await fetch(`${API_URL}/strategies`);
      const data = await res.json();
      setStrategies(data.strategies || []);
    } catch (err) {
      console.error('Failed to fetch strategies:', err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const tradeData = {
      symbol: formData.get('symbol'),
      side: formData.get('side'),
      entry_date: formData.get('entry_date'),
      exit_date: formData.get('exit_date') || null,
      entry_price: parseFloat(formData.get('entry_price')),
      exit_price: formData.get('exit_price') ? parseFloat(formData.get('exit_price')) : null,
      quantity: parseFloat(formData.get('quantity')) || 1,
      strategy_id: formData.get('strategy_id') ? parseInt(formData.get('strategy_id')) : null,
      notes: formData.get('notes') || ''
    };

    try {
      const url = editingTrade
        ? `${API_URL}/trades/${editingTrade.id}`
        : `${API_URL}/trades`;
      const method = editingTrade ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(tradeData)
      });

      if (res.ok) {
        setShowModal(false);
        setEditingTrade(null);
        fetchTrades();
      }
    } catch (err) {
      console.error('Failed to save trade:', err);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this trade?')) return;
    try {
      const res = await fetch(`${API_URL}/trades/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchTrades();
      }
    } catch (err) {
      console.error('Failed to delete trade:', err);
    }
  };

  const openEditModal = (trade) => {
    setEditingTrade(trade);
    setShowModal(true);
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

  const formatPercent = (val) => {
    if (val === null || val === undefined) return '-';
    return `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`;
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getStrategyColor = (strategyId) => {
    const strategy = strategies.find(s => s.id === strategyId);
    return strategy?.color || '#9ca3af';
  };

  const getStrategyName = (strategyId) => {
    const strategy = strategies.find(s => s.id === strategyId);
    return strategy?.name || '-';
  };

  return (
    <div className="trades-page">
      {/* Filters */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="table-header">
          <div className="table-filters" style={{ flex: 1 }}>
            <div style={{ position: 'relative', flex: 1, maxWidth: '300px' }}>
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#9ca3af'
                }}
              />
              <input
                type="text"
                className="input"
                placeholder="Search symbol..."
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                style={{ paddingLeft: '36px' }}
              />
            </div>
            <select
              className="select"
              style={{ width: 'auto' }}
              value={filters.side}
              onChange={(e) => setFilters({ ...filters, side: e.target.value })}
            >
              <option value="">All Sides</option>
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
            <select
              className="select"
              style={{ width: 'auto' }}
              value={filters.strategy_id}
              onChange={(e) => setFilters({ ...filters, strategy_id: e.target.value })}
            >
              <option value="">All Strategies</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary" onClick={() => { setEditingTrade(null); setShowModal(true); }}>
            <Plus size={16} />
            Add Trade
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>Qty</th>
              <th>P&L</th>
              <th>%</th>
              <th>Strategy</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="10" style={{ textAlign: 'center', padding: '40px' }}>
                  <div className="spinner" style={{ margin: '0 auto' }}></div>
                </td>
              </tr>
            ) : trades.length === 0 ? (
              <tr>
                <td colSpan="10" style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                  No trades found
                </td>
              </tr>
            ) : (
              trades.map((trade) => (
                <tr key={trade.id} onClick={() => openEditModal(trade)} style={{ cursor: 'pointer' }}>
                  <td>{formatDate(trade.exit_date || trade.entry_date)}</td>
                  <td style={{ fontWeight: 600, color: '#00d4ff' }}>{trade.symbol}</td>
                  <td>
                    <span className={`badge badge-${trade.side}`}>
                      {trade.side.toUpperCase()}
                    </span>
                  </td>
                  <td>${trade.entry_price?.toFixed(2)}</td>
                  <td>{trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '-'}</td>
                  <td>{trade.quantity}</td>
                  <td className={trade.pnl >= 0 ? 'text-positive' : 'text-negative'}>
                    {formatCurrency(trade.pnl)}
                  </td>
                  <td className={trade.pnl_percent >= 0 ? 'text-positive' : 'text-negative'}>
                    {formatPercent(trade.pnl_percent)}
                  </td>
                  <td>
                    <span
                      className="badge badge-strategy"
                      style={{ backgroundColor: `${getStrategyColor(trade.strategy_id)}20`, color: getStrategyColor(trade.strategy_id) }}
                    >
                      {getStrategyName(trade.strategy_id)}
                    </span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleDelete(trade.id)}
                      style={{ color: '#ef4444' }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {pagination.totalPages > 1 && (
          <div className="pagination">
            <button
              className="pagination-btn"
              disabled={pagination.page === 1}
              onClick={() => setPagination({ ...pagination, page: pagination.page - 1 })}
            >
              <ChevronLeft size={16} />
            </button>
            <span className="pagination-info">
              Page {pagination.page} of {pagination.totalPages} ({pagination.total} trades)
            </span>
            <button
              className="pagination-btn"
              disabled={pagination.page === pagination.totalPages}
              onClick={() => setPagination({ ...pagination, page: pagination.page + 1 })}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editingTrade ? 'Edit Trade' : 'Add New Trade'}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-row">
                  <div className="form-group">
                    <label className="label">Symbol *</label>
                    <input
                      type="text"
                      name="symbol"
                      className="input"
                      placeholder="AAPL"
                      defaultValue={editingTrade?.symbol}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="label">Side *</label>
                    <select name="side" className="select" defaultValue={editingTrade?.side || 'long'} required>
                      <option value="long">Long</option>
                      <option value="short">Short</option>
                    </select>
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="label">Entry Date *</label>
                    <input
                      type="datetime-local"
                      name="entry_date"
                      className="input"
                      defaultValue={editingTrade?.entry_date ? editingTrade.entry_date.slice(0, 16) : ''}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="label">Exit Date</label>
                    <input
                      type="datetime-local"
                      name="exit_date"
                      className="input"
                      defaultValue={editingTrade?.exit_date ? editingTrade.exit_date.slice(0, 16) : ''}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="label">Entry Price *</label>
                    <input
                      type="number"
                      name="entry_price"
                      step="0.01"
                      className="input"
                      placeholder="150.00"
                      defaultValue={editingTrade?.entry_price}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="label">Exit Price</label>
                    <input
                      type="number"
                      name="exit_price"
                      step="0.01"
                      className="input"
                      placeholder="155.00"
                      defaultValue={editingTrade?.exit_price}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="label">Quantity</label>
                    <input
                      type="number"
                      name="quantity"
                      className="input"
                      placeholder="100"
                      defaultValue={editingTrade?.quantity || 100}
                    />
                  </div>
                  <div className="form-group">
                    <label className="label">Strategy</label>
                    <select name="strategy_id" className="select" defaultValue={editingTrade?.strategy_id || ''}>
                      <option value="">Select strategy...</option>
                      {strategies.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="label">Notes</label>
                  <textarea
                    name="notes"
                    className="input"
                    rows="3"
                    placeholder="Trade notes..."
                    defaultValue={editingTrade?.notes}
                    style={{ resize: 'vertical' }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingTrade ? 'Update Trade' : 'Add Trade'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
