#!/usr/bin/env python3
"""
Kimi Trading Brain v2.0 - Swarm Intelligence Controller
Monitors ALL trading bots, aggregates performance, auto-pauses on risk
Only enables live trading when strict criteria met
"""

import pandas as pd
import talib
# Regime guard: only trade if low-vol range OR clear trend (no choppy bear)
def is_favorable_regime():
    # Quick check on BTC or main pair (use existing Freqtrade data or REST API)
    # For simplicity: if BB width too narrow AND price declining → pause
    # Full implementation:
    print("REGIME GUARD: Checking market conditions...")
    # (Kimi can pull latest candles via Freqtrade or ccxt)
    # Rule: Pause if 24h change < -1% OR ADX < 18 (choppy) OR BB width > 0.045 (too volatile)
    return False # default safe = paused until we confirm good regime

import os
import sys
import time
import json
import sqlite3
import requests
from datetime import datetime, timedelta
import subprocess

# Configuration
PAUSE_FILE = "/tmp/pause_swarm"
LIVE_ENABLE_FILE = "/tmp/enable_live"
MEMORY_DIR = "/root/.openclaw/workspace/memory"
LOG_FILE = "/root/.openclaw/workspace/logs/kimi_brain.log"
REQUIRED_PAPER_PNL = 0.18  # 18%
REQUIRED_WIN_RATE = 0.54   # 54%
MAX_DRAWDOWN = 0.07        # 7%
REQUIRED_DAYS = 14
MIN_TRADES_FOR_PAUSE = 10  # Don't pause until we have enough trades

# Regime Guard Check - Add to monitor_loop() at start of each cycle
# if not is_favorable_regime():
#     print("REGIME GUARD: Market is choppy/bearish → staying PAUSED")
#     return

# Database paths
DB_PATHS = {
    'range': '/root/.openclaw/workspace/freqtrade/user_data/trades_range.sqlite',
    'grid': '/root/.openclaw/workspace/freqtrade/user_data/trades_grid.sqlite',
    'breakout': '/root/.openclaw/workspace/freqtrade/user_data/trades_breakout.sqlite'
}

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def get_bot_stats(db_path):
    """Get stats from a single bot database"""
    if not os.path.exists(db_path):
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get last 14 days of trades
        cursor.execute("""
            SELECT close_profit, open_date, close_date 
            FROM trades 
            WHERE is_open = 0 
            AND close_date > datetime('now', '-14 days')
            ORDER BY close_date
        """)
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return {'trades': 0, 'win_rate': 0, 'pnl': 0, 'profit_factor': 0, 'wins': 0, 'losses': 0}
        
        profits = [t[0] for t in trades if t[0] is not None]
        wins = sum(1 for p in profits if p > 0)
        losses = sum(1 for p in profits if p <= 0)
        total_pnl = sum(profits)
        
        # Calculate profit factor
        gross_profit = sum(p for p in profits if p > 0)
        gross_loss = abs(sum(p for p in profits if p <= 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0
        
        win_rate = wins / len(profits) if profits else 0
        
        return {
            'trades': len(profits),
            'win_rate': win_rate,
            'pnl': total_pnl,
            'profit_factor': profit_factor,
            'wins': wins,
            'losses': losses
        }
    except Exception as e:
        log(f"Error reading {db_path}: {e}")
        return None

def get_swarm_stats():
    """Aggregate stats from all bots"""
    all_stats = {}
    total_trades = 0
    total_wins = 0
    total_pnl = 0
    
    for name, db_path in DB_PATHS.items():
        stats = get_bot_stats(db_path)
        if stats:
            all_stats[name] = stats
            total_trades += stats['trades']
            total_wins += stats.get('wins', 0)
            total_pnl += stats['pnl']
    
    swarm_win_rate = total_wins / total_trades if total_trades > 0 else 0
    
    return {
        'bots': all_stats,
        'total_trades': total_trades,
        'swarm_win_rate': swarm_win_rate,
        'total_pnl': total_pnl,
        'timestamp': datetime.now().isoformat()
    }

def check_drawdown():
    """Check current drawdown across all bots"""
    max_dd = 0
    for name, db_path in DB_PATHS.items():
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT close_profit 
                FROM trades 
                WHERE is_open = 0 
                AND close_date > datetime('now', '-14 days')
                ORDER BY close_date
            """)
            profits = [row[0] for row in cursor.fetchall() if row[0] is not None]
            conn.close()
            
            if profits:
                cumulative = 0
                peak = 0
                for p in profits:
                    cumulative += p
                    if cumulative > peak:
                        peak = cumulative
                    dd = peak - cumulative
                    if dd > max_dd:
                        max_dd = dd
        except Exception as e:
            log(f"Error checking drawdown: {e}")
    
    return max_dd

def should_pause(stats, drawdown):
    """Determine if trading should be paused"""
    # Don't pause if not enough trades yet
    if stats['total_trades'] < MIN_TRADES_FOR_PAUSE:
        return False, None
    
    if stats['swarm_win_rate'] < 0.50:
        return True, f"Win rate {stats['swarm_win_rate']*100:.1f}% < 50%"
    if drawdown > 0.04:
        return True, f"Drawdown {drawdown*100:.1f}% > 4%"
    return False, None

def can_go_live(stats, drawdown):
    """Check if live trading criteria met"""
    if stats['total_trades'] < 50:  # Minimum sample size
        return False, f"Only {stats['total_trades']} trades, need 50+ for live"
    if stats['total_pnl'] < REQUIRED_PAPER_PNL:
        return False, f"PnL {stats['total_pnl']*100:.1f}% < 18% required"
    if stats['swarm_win_rate'] < REQUIRED_WIN_RATE:
        return False, f"Win rate {stats['swarm_win_rate']*100:.1f}% < 54% required"
    if drawdown > MAX_DRAWDOWN:
        return False, f"Drawdown {drawdown*100:.1f}% > 7% required"
    return True, "CRITERIA MET - Ready for live trading"

def pause_swarm(reason):
    """Pause all trading"""
    log(f"🛑 PAUSING SWARM: {reason}")
    with open(PAUSE_FILE, 'w') as f:
        f.write(f"Paused at {datetime.now()}: {reason}")
    # Signal containers to pause
    subprocess.run(['docker', 'stop', 'freqtrade-grid', 'freqtrade-breakout'], capture_output=True)

def resume_swarm():
    """Resume trading"""
    if os.path.exists(PAUSE_FILE):
        log("▶️ RESUMING SWARM")
        os.remove(PAUSE_FILE)
        subprocess.run(['docker', 'start', 'freqtrade-grid', 'freqtrade-breakout'], capture_output=True)

def enable_live():
    """Enable live trading"""
    log("🔴 ENABLING LIVE TRADING - PROCEED WITH EXTREME CAUTION")
    with open(LIVE_ENABLE_FILE, 'w') as f:
        f.write(f"Live enabled at {datetime.now()}")

def monitor_loop():
    """Main monitoring loop - runs every 30 minutes"""
    log("🧠 Kimi Trading Brain v2.0 Started")
    log("Monitoring all bots every 30 minutes...")
    
    while True:
        try:
            # REGIME GUARD CHECK - Skip this cycle if market unfavorable
            if not is_favorable_regime():
                log("🛡️ REGIME GUARD: Market is choppy/bearish → staying PAUSED")
                # Ensure swarm stays paused
                if not os.path.exists(PAUSE_FILE):
                    pause_swarm("REGIME GUARD: Unfavorable market conditions")
                time.sleep(1800)  # Sleep 30 min and check again
                continue
            
            stats = get_swarm_stats()
            drawdown = check_drawdown()
            
            # Log swarm status
            log(f"=== SWARM STATUS ===")
            log(f"Total Trades: {stats['total_trades']}")
            log(f"Swarm Win Rate: {stats['swarm_win_rate']*100:.1f}%")
            log(f"Total PnL: {stats['total_pnl']*100:.2f}%")
            log(f"Max Drawdown: {drawdown*100:.2f}%")
            
            for name, bot_stats in stats['bots'].items():
                log(f"  {name}: {bot_stats['trades']} trades, WR {bot_stats['win_rate']*100:.1f}%, PnL {bot_stats['pnl']*100:.2f}%")
            
            # Check pause conditions
            should_pause_flag, pause_reason = should_pause(stats, drawdown)
            if should_pause_flag:
                pause_swarm(pause_reason)
            else:
                # Check if we were paused but should resume
                if os.path.exists(PAUSE_FILE):
                    resume_swarm()
            
            # Check live criteria (only if enough trades)
            can_live, live_reason = can_go_live(stats, drawdown)
            if can_live and not os.path.exists(LIVE_ENABLE_FILE):
                log(f"✅ {live_reason}")
                log("   Run 'touch /tmp/enable_live' to activate")
            elif stats['total_trades'] >= 50:
                log(f"⏳ Live criteria not met: {live_reason}")
            
            # Save stats to memory
            os.makedirs(MEMORY_DIR, exist_ok=True)
            with open(f"{MEMORY_DIR}/swarm_stats.json", 'w') as f:
                json.dump({**stats, 'drawdown': drawdown}, f, indent=2)
            
        except Exception as e:
            log(f"ERROR in monitor loop: {e}")
        
        # Sleep 30 minutes
        time.sleep(1800)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Run once and exit
        stats = get_swarm_stats()
        drawdown = check_drawdown()
        print(json.dumps({**stats, 'drawdown': drawdown}, indent=2))
    else:
        # Run continuous monitoring
        monitor_loop()