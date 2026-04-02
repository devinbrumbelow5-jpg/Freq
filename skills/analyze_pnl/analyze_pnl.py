#!/usr/bin/env python3
"""
analyze_pnl: Analyze profit/loss across all trades with detailed metrics
"""

import sqlite3
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
import statistics

def calculate_sharpe(returns, risk_free_rate=0):
    """Calculate Sharpe ratio"""
    if len(returns) < 2:
        return 0
    avg_return = statistics.mean(returns)
    std_return = statistics.stdev(returns)
    if std_return == 0:
        return 0
    return (avg_return - risk_free_rate) / std_return

def calculate_sortino(returns, risk_free_rate=0):
    """Calculate Sortino ratio (downside deviation only)"""
    if len(returns) < 2:
        return 0
    avg_return = statistics.mean(returns)
    downside_returns = [r for r in returns if r < 0]
    if len(downside_returns) < 2:
        return avg_return * 10  # No downside risk
    downside_std = statistics.stdev(downside_returns)
    if downside_std == 0:
        return avg_return * 10
    return (avg_return - risk_free_rate) / downside_std

def main():
    parser = argparse.ArgumentParser(description='Analyze P&L from Freqtrade database')
    parser.add_argument('--db', default='/root/.openclaw/workspace/freqtrade/tradesv3.dryrun.sqlite',
                       help='Path to SQLite database')
    parser.add_argument('--days', type=int, default=7, help='Analysis period in days')
    parser.add_argument('--pair', default=None, help='Filter by specific pair')
    parser.add_argument('--output', choices=['json', 'table', 'summary'], default='table',
                       help='Output format')
    
    args = parser.parse_args()
    
    if not Path(args.db).exists():
        print(f"❌ Database not found: {args.db}")
        return
    
    # Connect to database
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    # Build query
    query = """
        SELECT pair, profit_ratio, open_date, close_date, amount, open_rate, close_rate
        FROM trades
        WHERE close_date IS NOT NULL
        AND close_date > ?
    """
    params = [start_date.strftime('%Y-%m-%d')]
    
    if args.pair:
        query += " AND pair = ?"
        params.append(args.pair)
    
    cursor.execute(query, params)
    trades = cursor.fetchall()
    
    if not trades:
        print(f"❌ No closed trades found in last {args.days} days")
        conn.close()
        return
    
    # Calculate metrics
    profits = [t['profit_ratio'] for t in trades]
    winning_trades = [p for p in profits if p > 0]
    losing_trades = [p for p in profits if p <= 0]
    
    total_profit = sum(profits)
    avg_profit = statistics.mean(profits)
    
    gross_profit = sum(winning_trades) if winning_trades else 0
    gross_loss = abs(sum(losing_trades)) if losing_trades else 0.0001
    profit_factor = gross_profit / gross_loss
    
    win_rate = len(winning_trades) / len(profits) * 100
    
    # Sharpe and Sortino
    sharpe = calculate_sharpe(profits)
    sortino = calculate_sortino(profits)
    
    # Max drawdown calculation
    cumulative = []
    running_total = 0
    for p in profits:
        running_total += p
        cumulative.append(running_total)
    
    peak = cumulative[0]
    max_drawdown = 0
    for val in cumulative:
        if val > peak:
            peak = val
        drawdown = (peak - val) / peak if peak > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
    
    results = {
        'period_days': args.days,
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': round(win_rate, 2),
        'total_profit_pct': round(total_profit * 100, 4),
        'avg_profit_pct': round(avg_profit * 100, 4),
        'profit_factor': round(profit_factor, 4),
        'sharpe_ratio': round(sharpe, 4),
        'sortino_ratio': round(sortino, 4),
        'max_drawdown_pct': round(max_drawdown * 100, 4),
        'gross_profit': round(gross_profit * 100, 4),
        'gross_loss': round(gross_loss * 100, 4),
        'best_trade_pct': round(max(profits) * 100, 4) if profits else 0,
        'worst_trade_pct': round(min(profits) * 100, 4) if profits else 0
    }
    
    # Output
    if args.output == 'json':
        print(json.dumps(results, indent=2))
    elif args.output == 'summary':
        print(f"📊 P&L Summary (Last {args.days} days)")
        print(f"   Trades: {results['total_trades']} (W: {results['winning_trades']}, L: {results['losing_trades']})")
        print(f"   Win Rate: {results['win_rate']:.1f}%")
        print(f"   Total P&L: {results['total_profit_pct']:.2f}%")
        print(f"   Profit Factor: {results['profit_factor']:.2f}")
        print(f"   Sharpe: {results['sharpe_ratio']:.2f}")
        print(f"   Max DD: {results['max_drawdown_pct']:.2f}%")
    else:
        print(f"\n{'='*60}")
        print(f"📊 P&L ANALYSIS (Last {args.days} days)")
        print(f"{'='*60}")
        print(f"Total Trades:      {results['total_trades']}")
        print(f"Winning Trades:    {results['winning_trades']} ({results['win_rate']:.1f}%)")
        print(f"Losing Trades:     {results['losing_trades']}")
        print(f"{'-'*60}")
        print(f"Total P&L:         {results['total_profit_pct']:+.4f}%")
        print(f"Average Trade:     {results['avg_profit_pct']:+.4f}%")
        print(f"Best Trade:        {results['best_trade_pct']:+.4f}%")
        print(f"Worst Trade:       {results['worst_trade_pct']:+.4f}%")
        print(f"{'-'*60}")
        print(f"Profit Factor:     {results['profit_factor']:.4f}")
        print(f"Sharpe Ratio:      {results['sharpe_ratio']:.4f}")
        print(f"Sortino Ratio:     {results['sortino_ratio']:.4f}")
        print(f"Max Drawdown:      {results['max_drawdown_pct']:.4f}%")
        print(f"Gross Profit:      {results['gross_profit']:+.4f}%")
        print(f"Gross Loss:        -{results['gross_loss']:.4f}%")
        print(f"{'='*60}")
    
    # Save to memory
    workspace = Path('/root/.openclaw/workspace')
    memory_file = workspace / 'memory' / 'pnl_analysis.json'
    
    with open(memory_file, 'a') as f:
        json.dump({**results, 'timestamp': datetime.now().isoformat()}, f)
        f.write('\n')
    
    conn.close()

if __name__ == '__main__':
    main()
