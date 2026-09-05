import React, { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import { TrendingUp, TrendingDown, Target, BarChart3 } from 'lucide-react';

ChartJS.register(
  CategoryScale, LinearScale, BarElement, PointElement, LineElement,
  ArcElement, Title, Tooltip, Legend, Filler
);

const API_URL = 'http://localhost:3001/api';

export default function Analytics() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const res = await fetch(`${API_URL}/analytics`);
      const data = await res.json();
      setAnalytics(data);
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
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

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  const { summary, strategy_performance, monthly_returns, pnl_distribution } = analytics || {};

  // Strategy Performance Chart
  const strategyChartData = {
    labels: strategy_performance?.map(s => s.name) || [],
    datasets: [
      {
        label: 'P&L',
        data: strategy_performance?.map(s => s.total_pnl) || [],
        backgroundColor: strategy_performance?.map(s => s.total_pnl >= 0 ? '#10b981' : '#ef4444') || [],
        borderRadius: 6,
        barThickness: 40
      }
    ]
  };

  const strategyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1f2937',
        titleColor: '#f9fafb',
        bodyColor: '#f9fafb',
        callbacks: {
          label: (ctx) => formatCurrency(ctx.raw)
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(55, 65, 81, 0.5)' },
        ticks: { color: '#9ca3af', callback: (val) => formatCurrency(val) }
      },
      y: {
        grid: { display: false },
        ticks: { color: '#f9fafb' }
      }
    }
  };

  // Monthly Returns Chart
  const monthlyChartData = {
    labels: monthly_returns?.map(m => m.month) || [],
    datasets: [
      {
        label: 'P&L',
        data: monthly_returns?.map(m => m.total_pnl) || [],
        backgroundColor: monthly_returns?.map(m => m.total_pnl >= 0 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)') || [],
        borderRadius: 4
      }
    ]
  };

  const monthlyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1f2937',
        titleColor: '#f9fafb',
        bodyColor: '#f9fafb',
        callbacks: {
          label: (ctx) => formatCurrency(ctx.raw)
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#9ca3af' }
      },
      y: {
        grid: { color: 'rgba(55, 65, 81, 0.5)' },
        ticks: { color: '#9ca3af', callback: (val) => formatCurrency(val) }
      }
    }
  };

  // Win/Loss Doughnut
  const winLossData = {
    labels: ['Wins', 'Losses'],
    datasets: [
      {
        data: [summary?.winning_trades || 0, summary?.losing_trades || 0],
        backgroundColor: ['#10b981', '#ef4444'],
        borderColor: ['#10b981', '#ef4444'],
        borderWidth: 2
      }
    ]
  };

  const winLossOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: { color: '#9ca3af', padding: 20 }
      },
      tooltip: {
        backgroundColor: '#1f2937',
        titleColor: '#f9fafb',
        bodyColor: '#f9fafb'
      }
    },
    cutout: '70%'
  };

  return (
    <div className="analytics-page">
      {/* Stats Overview */}
      <div className="stats-grid" style={{ marginBottom: '24px' }}>
        <div className="stat-card">
          <div className="stat-card-icon">
            <TrendingUp size={20} />
          </div>
          <div className="stat-card-label">Total P&L</div>
          <div className={`stat-card-value ${summary?.total_pnl >= 0 ? 'positive' : 'negative'}`}>
            {formatCurrency(summary?.total_pnl)}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
            <Target size={20} />
          </div>
          <div className="stat-card-label">Win Rate</div>
          <div className="stat-card-value">{summary?.win_rate?.toFixed(1)}%</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon" style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' }}>
            <BarChart3 size={20} />
          </div>
          <div className="stat-card-label">Profit Factor</div>
          <div className="stat-card-value">{summary?.profit_factor?.toFixed(2) || '-'}</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-label">Expectancy</div>
          <div className={`stat-card-value ${(summary?.expectancy || 0) >= 0 ? 'positive' : 'negative'}`}>
            {formatCurrency(summary?.expectancy)}/trade
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginBottom: '24px' }}>
        {/* Strategy Performance */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Performance by Strategy</h3>
          </div>
          <div style={{ height: '300px' }}>
            {strategy_performance?.length > 0 ? (
              <Bar data={strategyChartData} options={strategyChartOptions} />
            ) : (
              <div className="empty-state">
                <p>No strategy data available</p>
              </div>
            )}
          </div>
        </div>

        {/* Win Rate Doughnut */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Win Rate</h3>
          </div>
          <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: '200px', height: '200px', position: 'relative' }}>
              <Doughnut data={winLossData} options={winLossOptions} />
              <div style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>
                  {summary?.win_rate?.toFixed(0)}%
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Monthly Returns */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Monthly Returns</h3>
        </div>
        <div style={{ height: '300px' }}>
          {monthly_returns?.length > 0 ? (
            <Bar data={monthlyChartData} options={monthlyChartOptions} />
          ) : (
            <div className="empty-state">
              <p>No monthly data available</p>
            </div>
          )}
        </div>
      </div>

      {/* Detailed Stats Table */}
      <div className="card" style={{ marginTop: '24px' }}>
        <div className="card-header">
          <h3 className="card-title">Strategy Breakdown</h3>
        </div>
        <div className="table-container" style={{ border: 'none' }}>
          <table>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Trades</th>
                <th>Win Rate</th>
                <th>Avg Win</th>
                <th>Avg Loss</th>
                <th>Total P&L</th>
                <th>Best Trade</th>
              </tr>
            </thead>
            <tbody>
              {strategy_performance?.map((s) => (
                <tr key={s.id}>
                  <td>
                    <span
                      className="badge badge-strategy"
                      style={{ backgroundColor: `${s.color}20`, color: s.color }}
                    >
                      {s.name}
                    </span>
                  </td>
                  <td>{s.total_trades}</td>
                  <td>{s.win_rate?.toFixed(1)}%</td>
                  <td className="text-positive">{formatCurrency(s.avg_win)}</td>
                  <td className="text-negative">{formatCurrency(s.avg_loss)}</td>
                  <td className={s.total_pnl >= 0 ? 'text-positive' : 'text-negative'}>
                    {formatCurrency(s.total_pnl)}
                  </td>
                  <td className="text-positive">{formatCurrency(s.best_trade)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
