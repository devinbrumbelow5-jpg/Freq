#!/usr/bin/env python3
"""
PnL Analyzer for Freq Swarm
Calculates hourly profit/loss, win rate, and drawdown.
Logs to memory/pnl_hourly.json
Alerts if drawdown exceeds 10%.
"""

import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Configuration
MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
FREQTRADE_DIR = Path("/root/.openclaw/workspace/freqtrade")
DRAWDOWN_ALERT_THRESHOLD = 0.10  # 10%
DB_PATHS = [
    FREQTRADE_DIR / "data" / "trades-main.sqlite",
    FREQTRADE_DIR / "data" / "trades-trend.sqlite",
    FREQTRADE_DIR / "data" / "trades-meanrev.sqlite",
    FREQTRADE_DIR / "data" / "trades-breakout.sqlite",
    FREQTRADE_DIR / "user_data" / "tradesv3_freqai.sqlite",
]


def log_message(level: str, agent: str, message: str):
    """Terminal-style logging matching Freq swarm format"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [PnL] [{level}] {message}")


def get_db_trades(db_path: Path) -> List[Dict]:
    """Extract all trades from a SQLite database"""
    if not db_path.exists():
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, pair, is_open, open_date, close_date,
                open_rate, close_rate, amount, stake_amount,
                close_profit, close_profit_abs, realized_profit,
                exit_reason, strategy, enter_tag
            FROM trades
            WHERE open_date IS NOT NULL
            ORDER BY open_date DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        log_message("WARN", "PnL", f"Error reading {db_path}: {e}")
        return []


def calculate_pnl_metrics(all_trades: List[Dict]) -> Dict[str, Any]:
    """Calculate comprehensive PnL metrics"""
    if not all_trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_profit_abs": 0.0,
            "total_profit_pct": 0.0,
            "average_profit": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "open_trades": 0,
            "closed_trades": 0
        }
    
    # Separate open and closed trades
    closed_trades = [t for t in all_trades if not t.get("is_open")]
    open_trades = [t for t in all_trades if t.get("is_open")]
    
    if not closed_trades:
        return {
            "total_trades": len(all_trades),
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_profit_abs": 0.0,
            "total_profit_pct": 0.0,
            "average_profit": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "open_trades": len(open_trades),
            "closed_trades": 0
        }
    
    # Sort by close date for equity curve
    closed_trades_sorted = sorted(
        [t for t in closed_trades if t.get("close_date")],
        key=lambda x: x["close_date"]
    )
    
    # Calculate wins/losses
    profits = []
    profits_abs = []
    winning_trades = 0
    losing_trades = 0
    gross_profit = 0.0
    gross_loss = 0.0
    
    for trade in closed_trades:
        profit = trade.get("close_profit") or 0.0
        profit_abs = trade.get("close_profit_abs") or trade.get("realized_profit") or 0.0
        
        profits.append(profit)
        profits_abs.append(profit_abs)
        
        if profit > 0:
            winning_trades += 1
            gross_profit += profit_abs
        else:
            losing_trades += 1
            gross_loss += abs(profit_abs)
    
    total_closed = len(closed_trades)
    win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0.0
    
    # Calculate equity curve and drawdown
    equity_curve = []
    running_balance = 0.0
    peak_equity = 0.0
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    
    for trade in closed_trades_sorted:
        profit_abs = trade.get("close_profit_abs") or trade.get("realized_profit") or 0.0
        running_balance += profit_abs
        equity_curve.append(running_balance)
        
        if running_balance > peak_equity:
            peak_equity = running_balance
        
        if peak_equity > 0:
            current_drawdown = peak_equity - running_balance
            current_drawdown_pct = current_drawdown / peak_equity if peak_equity > 0 else 0.0
            
            if current_drawdown_pct > max_drawdown_pct:
                max_drawdown = current_drawdown
                max_drawdown_pct = current_drawdown_pct
    
    # Calculate profit factor
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit if gross_profit > 0 else 0.0
    
    # Calculate average profit
    total_profit_abs = sum(profits_abs)
    average_profit = total_profit_abs / total_closed if total_closed > 0 else 0.0
    
    # Calculate total profit percentage (based on stake)
    total_stake = sum(t.get("stake_amount", 0) for t in closed_trades)
    total_profit_pct = (total_profit_abs / total_stake * 100) if total_stake > 0 else 0.0
    
    # Simple Sharpe calculation (assuming risk-free rate = 0)
    if len(profits) > 1:
        import statistics
        try:
            avg_return = statistics.mean(profits)
            std_return = statistics.stdev(profits)
            sharpe_ratio = avg_return / std_return * (252 ** 0.5) if std_return > 0 else 0.0  # Annualized
        except statistics.StatisticsError:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0
    
    return {
        "total_trades": len(all_trades),
        "closed_trades": len(closed_trades),
        "open_trades": len(open_trades),
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate, 2),
        "total_profit_abs": round(total_profit_abs, 4),
        "total_profit_pct": round(total_profit_pct, 4),
        "average_profit": round(average_profit, 4),
        "max_drawdown": round(max_drawdown, 4),
        "max_drawdown_pct": round(max_drawdown_pct * 100, 2),  # As percentage
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4)
    }


def get_hourly_breakdown(all_trades: List[Dict]) -> List[Dict]:
    """Get PnL breakdown by hour"""
    if not all_trades:
        return []
    
    hourly_data = {}
    
    for trade in all_trades:
        close_date = trade.get("close_date")
        if not close_date:
            continue
        
        # Parse datetime
        try:
            if isinstance(close_date, str):
                dt = datetime.fromisoformat(close_date.replace('Z', '+00:00'))
            else:
                dt = close_date
            hour_key = dt.strftime("%Y-%m-%d %H:00")
        except:
            continue
        
        profit = trade.get("close_profit_abs") or trade.get("realized_profit") or 0.0
        
        if hour_key not in hourly_data:
            hourly_data[hour_key] = {
                "trades": 0,
                "profit": 0.0,
                "wins": 0,
                "losses": 0
            }
        
        hourly_data[hour_key]["trades"] += 1
        hourly_data[hour_key]["profit"] += profit
        if profit > 0:
            hourly_data[hour_key]["wins"] += 1
        else:
            hourly_data[hour_key]["losses"] += 1
    
    return [
        {
            "hour": hour,
            "trades": data["trades"],
            "profit": round(data["profit"], 4),
            "wins": data["wins"],
            "losses": data["losses"],
            "win_rate": round(data["wins"] / data["trades"] * 100, 2) if data["trades"] > 0 else 0
        }
        for hour, data in sorted(hourly_data.items())
    ]


def get_pair_breakdown(all_trades: List[Dict]) -> Dict[str, Dict]:
    """Get PnL breakdown by trading pair"""
    if not all_trades:
        return {}
    
    pair_data = {}
    
    for trade in all_trades:
        pair = trade.get("pair", "UNKNOWN")
        profit = trade.get("close_profit_abs") or trade.get("realized_profit") or 0.0
        is_open = trade.get("is_open", False)
        
        if pair not in pair_data:
            pair_data[pair] = {
                "trades": 0,
                "profit": 0.0,
                "wins": 0,
                "losses": 0,
                "open": 0
            }
        
        pair_data[pair]["trades"] += 1
        pair_data[pair]["profit"] += profit
        
        if is_open:
            pair_data[pair]["open"] += 1
        elif profit > 0:
            pair_data[pair]["wins"] += 1
        else:
            pair_data[pair]["losses"] += 1
    
    # Convert to sorted list
    return {
        pair: {
            "trades": data["trades"],
            "profit": round(data["profit"], 4),
            "wins": data["wins"],
            "losses": data["losses"],
            "open": data["open"],
            "win_rate": round(data["wins"] / (data["wins"] + data["losses"]) * 100, 2) if (data["wins"] + data["losses"]) > 0 else 0
        }
        for pair, data in sorted(pair_data.items(), key=lambda x: x[1]["profit"], reverse=True)
    }


def check_drawdown_alert(metrics: Dict[str, Any]) -> Optional[str]:
    """Check if drawdown exceeds threshold and return alert message"""
    drawdown_pct = metrics.get("max_drawdown_pct", 0)
    
    if drawdown_pct > DRAWDOWN_ALERT_THRESHOLD * 100:
        return f"🚨 [CRITICAL] [PnL] Drawdown {drawdown_pct}% exceeds 10% threshold! | Emergency review required"
    elif drawdown_pct > 8:
        return f"⚠️ [WARN] [PnL] Drawdown {drawdown_pct}% approaching 10% limit | Consider reducing exposure"
    
    return None


def analyze_pnl():
    """Main PnL analysis function"""
    log_message("INFO", "PnL", "Starting hourly PnL analysis...")
    
    # Ensure memory directory exists
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Collect all trades from all databases
    all_trades = []
    db_stats = {}
    
    for db_path in DB_PATHS:
        if db_path.exists():
            trades = get_db_trades(db_path)
            all_trades.extend(trades)
            db_stats[db_path.name] = len(trades)
            log_message("INFO", "PnL", f"Loaded {len(trades)} trades from {db_path.name}")
        else:
            db_stats[db_path.name] = 0
    
    log_message("INFO", "PnL", f"Total trades across all DBs: {len(all_trades)}")
    
    # Calculate metrics
    metrics = calculate_pnl_metrics(all_trades)
    hourly_breakdown = get_hourly_breakdown(all_trades)
    pair_breakdown = get_pair_breakdown(all_trades)
    
    # Check for drawdown alert
    alert = check_drawdown_alert(metrics)
    
    # Build result
    result = {
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics,
        "hourly_breakdown": hourly_breakdown[-24:] if hourly_breakdown else [],  # Last 24 hours
        "pair_breakdown": pair_breakdown,
        "db_stats": db_stats,
        "alert": alert
    }
    
    # Write to memory file (atomic write)
    output_path = MEMORY_DIR / "pnl_hourly.json"
    temp_path = MEMORY_DIR / "pnl_hourly.json.tmp"
    
    with open(temp_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    os.replace(temp_path, output_path)
    
    log_message("INFO", "PnL", f"Results written to {output_path}")
    
    # Print summary
    log_message("INFO", "PnL", f"=== HOURLY PnL SUMMARY ===")
    log_message("INFO", "PnL", f"Total Trades: {metrics['total_trades']} (Open: {metrics['open_trades']}, Closed: {metrics['closed_trades']})")
    log_message("INFO", "PnL", f"Win Rate: {metrics['win_rate']:.2f}% ({metrics['winning_trades']} wins / {metrics['losing_trades']} losses)")
    log_message("INFO", "PnL", f"Total Profit: ${metrics['total_profit_abs']:.4f} ({metrics['total_profit_pct']:.2f}%)")
    log_message("INFO", "PnL", f"Profit Factor: {metrics['profit_factor']:.2f} | Sharpe: {metrics['sharpe_ratio']:.2f}")
    log_message("INFO", "PnL", f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}% (${metrics['max_drawdown']:.4f})")
    
    # Output alert if present
    if alert:
        print(f"\n{alert}\n")
        return 1  # Return non-zero for alerting
    
    return 0


if __name__ == "__main__":
    sys.exit(analyze_pnl())
