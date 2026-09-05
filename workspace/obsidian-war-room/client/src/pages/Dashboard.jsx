import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  Award,
  AlertTriangle,
  Zap,
  Activity
} from 'lucide-react';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const API_URL = 'http://localhost:3001/api';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [recentTrades, setRecentTrades] = useState([]);
  const [equityCurve, setEquityCurve] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [analyticsRes, tradesRes, equityRes] = await Promise.all([
        fetch(`${API_URL}/analytics`),
        fetch(`${API_URL}/trades?limit=5&sort=exit_date&order=desc`),
        fetch(`${API_URL}/analytics/equity-curve`)
      ]);

      const analyticsData = await analyticsRes.json();
      const tradesData = await tradesRes.json();
      const equityData = await equityRes.json();

      setSummary(analyticsData.summary);
      setRecentTrades(tradesData.trades || []);
      setEquityCurve(equityData);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
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

  const formatPercent = (val) => {
    if (val === null || val === undefined) return '-';
    return `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`;
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
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

  const equityChartData = {
    labels: equityCurve?.labels || [],
    datasets: [
      {
        label: 'Equity',
        data: equityCurve?.values || [],
        borderColor: '#00d4ff',
        backgroundColor: 'rgba(0, 212, 255, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: '#00d4ff'
      }
    ]
  };

  const equityChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1f2937',
        titleColor: '#f9fafb',
        bodyColor: '#f9fafb',
        borderColor: '#374151',
        borderWidth: 1,
        padding: 12,
        displayColors: false,
        callbacks: {
          label: (ctx) => formatCurrency(ctx.raw)
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(55, 65, 81, 0.5)' },
        ticks: { color: '#9ca3af', font: { size: 11 } }
      },
      y: {
        grid: { color: 'rgba(55, 65, 81, 0.5)' },
        ticks: {
          color: '#9ca3af',
          font: { size: 11 },
          callback: (val) => formatCurrency(val)
        }
      }
    }
  };

  return (
    <div className="dashboard">
      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-icon">
            <DollarSign size={20} />
          </div>
          <div className="stat-card-label">Total P&L</div>
          <div className={`stat-card-value ${(summary?.total_pnl || 0) >= 0 ? 'positive' : 'negative'}`}>
            {formatCurrency(summary?.total_pnl)}
          </div>
          {summary?.monthly_pnl !== undefined && (
            <div className={`stat-card-trend ${summary.monthly_pnl >= 0 ? 'up' : 'down'}`}>
              {summary.monthly_pnl >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              <span>This month: {formatCurrency(summary.monthly_pnl)}</span>
            </div>
          )}
        </div>

        <div className="stat-card">
          <div className="stat-card-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
            <Target size={20} />
          </div>
          <div className="stat-card-label">Win Rate</div>
          <div className="stat-card-value">{summary?.win_rate?.toFixed(1) || '0.0'}%</div>
          <div className="stat-card-trend up">
            <span>{summary?.winning_trades || 0} wins / {summary?.losing_trades || 0} losses</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon" style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' }}>
            <Award size={20} />
          </div>
          <div className="stat-card-label">Profit Factor</div>
          <div className="stat-card-value">
            {summary?.profit_factor ? summary.profit_factor.toFixed(2) : '-'}
          </div>
          <div className="stat-card-trend">
            <span>Wins / Losses ratio</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon" style={{ background: 'rgba(139, 92, 246, 0.1)', color: '#8b5cf6' }}>
            <Zap size={20} />
          </div>
          <div className="stat-card-label">Avg R-Multiple</div>
          <div className={`stat-card-value ${(summary?.avg_r || 0) >= 0 ? 'positive' : 'negative'}`}>
            {summary?.avg_r ? `R${summary.avg_r >= 0 ? '+' : ''}${summary.avg_r.toFixed(2)}` : '-'}
          </div>
          <div className="stat-card-trend">
            <span>Average risk-adjusted return</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
            <TrendingUp size={20} />
          </div>
          <div className="stat-card-label">Best Trade</div>
          <div className="stat-card-value positive">{formatCurrency(summary?.best_trade)}</div>
          <div className="stat-card-trend up">
            <span>{formatPercent(summary?.best_trade_percent)} return</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
            <AlertTriangle size={20} />
          </div>
          <div className="stat-card-label">Worst Trade</div>
          <div className="stat-card-value negative">{formatCurrency(summary?.worst_trade)}</div>
          <div className="stat-card-trend down">
            <span>{formatPercent(summary?.worst_trade_percent)} return</span>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="charts-grid">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Equity Curve</h3>
            <div className="tabs">
              <button className="tab active">All Time</button>
            </div>
          </div>
          <div style={{ height: '300px' }}>
            {equityCurve?.values?.length > 0 ? (
              <Line data={equityChartData} options={equityChartOptions} />
            ) : (
              <div className="empty-state">
                <Activity size={48} style={{ color: '#374151', marginBottom: '16px' }} />
                <p>No equity data available yet</p>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Quick Stats</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-muted">Total Trades</span>
              <span className="font-mono">{summary?.total_trades || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-muted">Avg Win</span>
              <span className="font-mono text-positive">{formatCurrency(summary?.avg_win)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-muted">Avg Loss</span>
              <span className="font-mono text-negative">{formatCurrency(summary?.avg_loss)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-muted">Expectancy</span>
              <span className={`font-mono ${(summary?.expectancy || 0) >= 0 ? 'text-positive' : 'text-negative'}`}>
                {formatCurrency(summary?.expectancy)}/trade
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-muted">Max Drawdown</span>
              <span className="font-mono text-negative">{formatCurrency(summary?.max_drawdown)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-muted">Current Streak</span>
              <span className={`font-mono ${(summary?.current_streak || 0) >= 0 ? 'text-positive' : 'text-negative'}`}>
                {summary?.current_streak > 0 
                  ? `${summary.current_streak}W` 
                  : summary?.current_streak < 0 
                    ? `${Math.abs(summary.current_streak)}L` 
                    : '-'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Trades */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recent Trades</h3>
          <a href="/trades" className="btn btn-ghost btn-sm">View All</a>
        </div>
        <div className="table-container" style={{ border: 'none' }}>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P&L</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', color: '#9ca3af' }}>
                    No trades yet
                  </td>
                </tr>
              ) : (
                recentTrades.map((trade) => (
                  <tr key={trade.id}>
                    <td>{formatDate(trade.exit_date || trade.entry_date)}</td>
                    <td style={{ fontWeight: 600 }}>{trade.symbol}</td>
                    <td>
                      <span className={`badge badge-${trade.side}`}>
                        {trade.side.toUpperCase()}
                      </span>
                    </td>
                    <td>${trade.entry_price?.toFixed(2)}</td>
                    <td>${trade.exit_price?.toFixed(2) || '-'}</td>
                    <td className={trade.pnl >= 0 ? 'text-positive' : 'text-negative'}>
                      {formatCurrency(trade.pnl)}
                    </td>
                    <td className={trade.pnl_percent >= 0 ? 'text-positive' : 'text-negative'}>
                      {formatPercent(trade.pnl_percent)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
