#!/usr/bin/env python3
"""
Tier 1: Ultra-Rapid Risk Check (Every 15 Seconds)
Scalping Risk Guardian + Latency Monitor
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
import subprocess
import sys

# Config
MEMORY_DIR = "/root/.openclaw/workspace/memory"
DB_PATHS = [
    "/root/.openclaw/workspace/freqtrade/user_data/tradesv3.sqlite",
    "/root/.openclaw/workspace/freqtrade/user_data/trades_micro.sqlite",
    "/root/.openclaw/workspace/freqtrade/user_data/trades_range.sqlite"
]
MAX_EXPOSURE_PCT = 0.06  # 6%
DRAWDOWN_ALERT_PCT = 0.10  # 10%
DRAWDOWN_KILL_PCT = 0.12  # 12%

def check_positions():
    """Query all open positions from SQLite databases"""
    total_exposure = 0
    open_trades = []
    
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pair, amount, open_rate, stake_amount, profit_ratio 
                FROM trades 
                WHERE is_open = 1
            """)
            trades = cursor.fetchall()
            for trade in trades:
                open_trades.append({
                    'pair': trade[0],
                    'amount': trade[1],
                    'open_rate': trade[2],
                    'stake': trade[3],
                    'profit': trade[4]
                })
                total_exposure += trade[3] if trade[3] else 0
            conn.close()
        except Exception as e:
            print(f"[WARN] DB error {db_path}: {e}")
    
    return total_exposure, open_trades

def check_drawdown():
    """Calculate current drawdown"""
    max_equity = 1000  # Starting dry-run wallet
    current_equity = 1000
    
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Get total realized profit
            cursor.execute("""
                SELECT COALESCE(SUM(profit_ratio * stake_amount), 0)
                FROM trades 
                WHERE is_open = 0
            """)
            realized = cursor.fetchone()[0] or 0
            # Get unrealized profit from open trades
            cursor.execute("""
                SELECT COALESCE(SUM(profit_ratio * stake_amount), 0)
                FROM trades 
                WHERE is_open = 1
            """)
            unrealized = cursor.fetchone()[0] or 0
            
            current_equity += realized + unrealized
            conn.close()
        except Exception as e:
            print(f"[WARN] Drawdown calc error: {e}")
    
    drawdown = (max_equity - current_equity) / max_equity if max_equity > 0 else 0
    return drawdown, current_equity

def check_container_health():
    """Check if all containers are running"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=freqtrade", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        containers = result.stdout.strip().split('\n')
        expected = ['freqtrade-scalp-main', 'freqtrade-micro', 'freqtrade-range']
        running = [c for c in containers if c in expected]
        return len(running) == len(expected), running
    except Exception as e:
        return False, []

def emergency_stop_all():
    """Execute emergency stop - kill all positions"""
    print("🚨 EMERGENCY STOP EXECUTING")
    try:
        subprocess.run([
            "docker", "exec", "freqtrade-scalp-main",
            "freqtrade", "forcesell", "all"
        ], capture_output=True)
        print("✅ Emergency stop completed")
    except Exception as e:
        print(f"❌ Emergency stop failed: {e}")

def write_memory_files(metrics):
    """Write metrics to memory files"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    
    # Risk metrics
    with open(f"{MEMORY_DIR}/scalping_risk_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    # Timestamp
    with open(f"{MEMORY_DIR}/last_risk_check.txt", "w") as f:
        f.write(datetime.now().isoformat())

def main():
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] [RISK] Running 15s risk check...")
    
    # Check container health
    healthy, containers = check_container_health()
    if not healthy:
        print(f"⚠️ WARNING: Only {len(containers)}/3 containers running")
    
    # Check positions
    exposure, trades = check_positions()
    exposure_pct = exposure / 1000  # Assuming 1000 USDT dry-run wallet
    
    # Check drawdown
    drawdown, equity = check_drawdown()
    
    # Build metrics
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "total_exposure_usdt": exposure,
        "exposure_pct": round(exposure_pct * 100, 2),
        "drawdown_pct": round(drawdown * 100, 2),
        "current_equity": round(equity, 2),
        "open_trades_count": len(trades),
        "containers_healthy": healthy,
        "trades": trades[:5]  # Last 5 trades
    }
    
    # Risk checks
    alerts = []
    
    if exposure_pct > MAX_EXPOSURE_PCT:
        alerts.append(f"EXPOSURE: {exposure_pct*100:.1f}% > 6% limit")
    
    if drawdown > DRAWDOWN_KILL_PCT:
        alerts.append(f"CRITICAL DRAWDOWN: {drawdown*100:.1f}% > 12% KILL")
        emergency_stop_all()
    elif drawdown > DRAWDOWN_ALERT_PCT:
        alerts.append(f"HIGH DRAWDOWN: {drawdown*100:.1f}% > 10% alert")
    
    if alerts:
        metrics["alerts"] = alerts
        print(f"🚨 ALERTS: {alerts}")
    else:
        print(f"✅ Risk OK: Exposure {exposure_pct*100:.1f}%, Drawdown {drawdown*100:.1f}%")
    
    # Write to memory
    write_memory_files(metrics)
    
    return 0 if not alerts else 1

if __name__ == "__main__":
    sys.exit(main())