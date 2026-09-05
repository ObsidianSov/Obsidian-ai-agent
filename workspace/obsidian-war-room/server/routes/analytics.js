import express from 'express';
import db from '../database.js';

const router = express.Router();

// GET analytics overview
router.get('/', (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    
    let dateFilter = '';
    const params = [];
    
    if (start_date) {
      dateFilter += ' AND entry_date >= ?';
      params.push(start_date);
    }
    if (end_date) {
      dateFilter += ' AND entry_date <= ?';
      params.push(end_date);
    }

    // Overall stats
    const overall = db.prepare(`
      SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
        SUM(CASE WHEN pnl IS NULL THEN 1 ELSE 0 END) as open_trades,
        SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as gross_profit,
        SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as gross_loss,
        SUM(pnl) as total_pnl,
        AVG(pnl) as avg_pnl,
        AVG(pnl_percent) as avg_pnl_percent,
        MAX(pnl) as best_trade,
        MIN(pnl) as worst_trade,
        MAX(pnl_percent) as best_trade_percent,
        MIN(pnl_percent) as worst_trade_percent
      FROM trades 
      WHERE exit_date IS NOT NULL ${dateFilter}
    `).get(...params);

    // Calculate derived metrics
    const winRate = overall.total_trades > 0 ? (overall.winning_trades / overall.total_trades) * 100 : 0;
    const profitFactor = overall.gross_loss > 0 ? overall.gross_profit / overall.gross_loss : overall.gross_profit > 0 ? Infinity : 0;
    const avgWin = overall.winning_trades > 0 ? overall.gross_profit / overall.winning_trades : 0;
    const avgLoss = overall.losing_trades > 0 ? overall.gross_loss / overall.losing_trades : 0;
    const expectancy = overall.total_trades > 0 ? overall.avg_pnl : 0;

    // Calculate R-multiple (assuming 1R = 1% risk - simplified)
    const avgR = overall.total_trades > 0 ? overall.avg_pnl_percent / 1 : 0;

    // Calculate streak
    const recentTrades = db.prepare(`
      SELECT pnl FROM trades 
      WHERE exit_date IS NOT NULL ${dateFilter}
      ORDER BY exit_date DESC
      LIMIT 20
    `).all(...params);

    let currentStreak = 0;
    let streakType = null;
    for (const trade of recentTrades) {
      if (trade.pnl > 0) {
        if (streakType === 'win') currentStreak++;
        else if (streakType === null) { currentStreak = 1; streakType = 'win'; }
        else break;
      } else if (trade.pnl < 0) {
        if (streakType === 'loss') currentStreak--;
        else if (streakType === null) { currentStreak = -1; streakType = 'loss'; }
        else break;
      }
    }

    // Daily P&L for equity curve
    const dailyPnL = db.prepare(`
      SELECT 
        DATE(entry_date) as date,
        SUM(pnl) as daily_pnl
      FROM trades 
      WHERE exit_date IS NOT NULL ${dateFilter}
      GROUP BY DATE(entry_date)
      ORDER BY date
    `).all(...params);

    // Build cumulative equity curve
    let runningTotal = 0;
    const equityLabels = [];
    const equityValues = [];
    dailyPnL.forEach(day => {
      runningTotal += day.daily_pnl;
      equityLabels.push(day.date);
      equityValues.push(runningTotal);
    });

    // Monthly P&L
    const monthlyPnL = db.prepare(`
      SELECT 
        STRFTIME('%Y-%m', entry_date) as month,
        SUM(pnl) as total_pnl,
        COUNT(*) as trades,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
      FROM trades 
      WHERE exit_date IS NOT NULL ${dateFilter}
      GROUP BY STRFTIME('%Y-%m', entry_date)
      ORDER BY month
    `).all(...params);

    // Win rate by strategy
    const strategyPerformance = db.prepare(`
      SELECT 
        s.id, s.name, s.color,
        COUNT(t.id) as total_trades,
        SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
        SUM(t.pnl) as total_pnl,
        AVG(CASE WHEN t.pnl > 0 THEN t.pnl ELSE NULL END) as avg_win,
        AVG(CASE WHEN t.pnl < 0 THEN t.pnl ELSE NULL END) as avg_loss,
        MAX(t.pnl) as best_trade,
        AVG(t.pnl_percent) as avg_r
      FROM strategies s
      LEFT JOIN trades t ON s.id = t.strategy_id AND t.exit_date IS NOT NULL ${dateFilter}
      GROUP BY s.id
      ORDER BY total_pnl DESC
    `).all(...params);

    // P&L distribution (buckets)
    const pnlDistribution = db.prepare(`
      SELECT 
        CASE 
          WHEN pnl_percent < -10 THEN '<-10%'
          WHEN pnl_percent >= -10 AND pnl_percent < -5 THEN '-10% to -5%'
          WHEN pnl_percent >= -5 AND pnl_percent < -2 THEN '-5% to -2%'
          WHEN pnl_percent >= -2 AND pnl_percent < 0 THEN '-2% to 0%'
          WHEN pnl_percent >= 0 AND pnl_percent < 2 THEN '0% to 2%'
          WHEN pnl_percent >= 2 AND pnl_percent < 5 THEN '2% to 5%'
          WHEN pnl_percent >= 5 AND pnl_percent < 10 THEN '5% to 10%'
          ELSE '>10%'
        END as bucket,
        COUNT(*) as count
      FROM trades
      WHERE exit_date IS NOT NULL ${dateFilter}
      GROUP BY bucket
      ORDER BY 
        CASE bucket
          WHEN '<-10%' THEN 1
          WHEN '-10% to -5%' THEN 2
          WHEN '-5% to -2%' THEN 3
          WHEN '-2% to 0%' THEN 4
          WHEN '0% to 2%' THEN 5
          WHEN '2% to 5%' THEN 6
          WHEN '5% to 10%' THEN 7
          ELSE 8
        END
    `).all(...params);

    // Calculate drawdown
    let maxPnL = 0;
    let maxDrawdown = 0;
    let peak = 0;
    
    equityValues.forEach(val => {
      if (val > peak) peak = val;
      const drawdown = peak - val;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    });

    // Monthly P&L for this month
    const thisMonth = new Date().toISOString().slice(0, 7);
    const monthlyPnlThisMonth = monthlyPnL.find(m => m.month === thisMonth);
    const monthly_pnl = monthlyPnlThisMonth?.total_pnl || 0;

    res.json({
      summary: {
        total_trades: overall.total_trades,
        winning_trades: overall.winning_trades,
        losing_trades: overall.losing_trades,
        open_trades: overall.open_trades,
        win_rate: winRate,
        profit_factor: profitFactor === Infinity ? overall.gross_profit : profitFactor,
        total_pnl: overall.total_pnl,
        avg_pnl: overall.avg_pnl,
        avg_pnl_percent: overall.avg_pnl_percent,
        avg_win: avgWin,
        avg_loss: avgLoss,
        expectancy: expectancy,
        avg_r: avgR,
        best_trade: overall.best_trade,
        worst_trade: overall.worst_trade,
        best_trade_percent: overall.best_trade_percent,
        worst_trade_percent: overall.worst_trade_percent,
        max_drawdown: maxDrawdown,
        current_streak: currentStreak,
        monthly_pnl: monthly_pnl
      },
      equity_curve: {
        labels: equityLabels,
        values: equityValues
      },
      monthly_returns: monthlyPnL.map(m => ({
        month: m.month,
        total_pnl: m.total_pnl,
        trades: m.trades,
        wins: m.wins
      })),
      strategy_performance: strategyPerformance.map(s => ({
        id: s.id,
        name: s.name,
        color: s.color,
        total_trades: s.total_trades || 0,
        win_rate: s.total_trades > 0 ? (s.winning_trades / s.total_trades) * 100 : 0,
        winning_trades: s.winning_trades || 0,
        losing_trades: s.losing_trades || 0,
        total_pnl: s.total_pnl || 0,
        avg_win: s.avg_win,
        avg_loss: s.avg_loss,
        best_trade: s.best_trade,
        avg_r: s.avg_r
      })),
      pnl_distribution: pnlDistribution
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: error.message });
  }
});

// GET equity curve data
router.get('/equity-curve', (req, res) => {
  try {
    const dailyPnL = db.prepare(`
      SELECT 
        DATE(entry_date) as date,
        SUM(pnl) as daily_pnl
      FROM trades 
      WHERE exit_date IS NOT NULL
      GROUP BY DATE(entry_date)
      ORDER BY date
    `).all();

    let runningTotal = 0;
    const labels = [];
    const values = [];
    
    dailyPnL.forEach(day => {
      runningTotal += day.daily_pnl;
      labels.push(day.date);
      values.push(Math.round(runningTotal * 100) / 100);
    });

    res.json({ labels, values });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

export default router;
