#!/usr/bin/env python3
"""
Market Regime Guard - Drawdown Monitor
Pauses trading if drawdown >5% in last 4 hours
"""

import sqlite3
import os
import time
import json
from datetime import datetime, timedelta
import logging

# Configuration
DRAWDOWN_THRESHOLD = 0.05  # 5%
LOOKBACK_HOURS = 4
DB_PATH = "/root/.openclaw/workspace/freqtrade/user_data/trades_range.sqlite"
PAUSE_FILE = "/tmp/trading_paused"
LOG_FILE = "/root/.openclaw/workspace/logs/regime_guard.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [REGIME-GUARD] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_recent_trades():
    """Get trades from last 4 hours"""
    try:
        cutoff_time = datetime.now() - timedelta(hours=LOOKBACK_HOURS)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            id, pair, is_open, profit_ratio, close_profit,
            open_date, close_date
        FROM trades
        WHERE close_date > ? OR is_open = 1
        ORDER BY close_date DESC
        """
        
        cursor.execute(query, (cutoff_time.strftime('%Y-%m-%d %H:%M:%S'),))
        trades = cursor.fetchall()
        conn.close()
        
        return trades
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def calculate_drawdown(trades):
    """Calculate max drawdown from trades"""
    if not trades:
        return 0.0, 0.0, 0
    
    profits = []
    total_pnl = 0.0
    peak = 0.0
    max_drawdown = 0.0
    
    for trade in trades:
        profit = trade[3] if trade[3] is not None else 0.0
        profits.append(profit)
        total_pnl += profit
        
        if total_pnl > peak:
            peak = total_pnl
        
        current_drawdown = peak - total_pnl
        if current_drawdown > max_drawdown:
            max_drawdown = current_drawdown
    
    return max_drawdown, total_pnl, len(trades)

def check_open_positions():
    """Get unrealized PnL from open positions"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as open_count, 
                   SUM(CASE WHEN close_profit IS NULL THEN 0 ELSE close_profit END) as unrealized
            FROM trades WHERE is_open = 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] or 0, result[1] or 0.0
        
    except Exception as e:
        logger.error(f"Error checking open positions: {e}")
        return 0, 0.0

def send_alert(message):
    """Send alert to multiple channels"""
    logger.warning(message)
    
    # Also write to alerts file
    with open('/root/.openclaw/workspace/logs/alerts.log', 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] REGIME-GUARD: {message}\n")

def pause_trading(reason):
    """Pause trading"""
    if not os.path.exists(PAUSE_FILE):
        with open(PAUSE_FILE, 'w') as f:
            json.dump({
                'paused_at': datetime.now().isoformat(),
                'reason': reason,
                'drawdown': DRAWDOWN_THRESHOLD
            }, f)
        send_alert(f"🛑 TRADING PAUSED: {reason}")
        logger.info("Trading paused. Create /tmp/resume_trading to resume.")

def resume_trading():
    """Resume trading if conditions normalize"""
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
        send_alert("✅ TRADING RESUMED: Conditions normalized")
        logger.info("Trading resumed")

def should_resume():
    """Check if we should auto-resume"""
    # Check last hour's performance
    try:
        cutoff_time = datetime.now() - timedelta(hours=1)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SUM(profit_ratio) FROM trades
            WHERE close_date > ? AND is_open = 0
        """, (cutoff_time.strftime('%Y-%m-%d %H:%M:%S'),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result[0] is not None and result[0] > 0:
            return True
            
    except Exception as e:
        logger.error(f"Resume check error: {e}")
    
    return False

def main():
    """Main monitoring loop"""
    logger.info("=" * 60)
    logger.info("Market Regime Guard Started")
    logger.info(f"Drawdown Threshold: {DRAWDOWN_THRESHOLD*100}%, Lookback: {LOOKBACK_HOURS}h")
    logger.info("=" * 60)
    
    while True:
        try:
            # Get recent trades
            trades = get_recent_trades()
            
            # Calculate drawdown
            drawdown, total_pnl, trade_count = calculate_drawdown(trades)
            
            # Check open positions
            open_count, unrealized = check_open_positions()
            
            # Total exposure
            total_exposure = drawdown + abs(unrealized)
            
            status_msg = (
                f"Status: {trade_count} trades, "
                f"PnL: {total_pnl:.2%}, "
                f"Drawdown: {drawdown:.2%}, "
                f"Open: {open_count} positions"
            )
            
            # Check if we should pause
            if drawdown >= DRAWDOWN_THRESHOLD:
                pause_trading(f"Drawdown {drawdown:.2%} exceeded {DRAWDOWN_THRESHOLD*100}% threshold")
            elif total_exposure >= DRAWDOWN_THRESHOLD * 1.2:  # Account for unrealized
                pause_trading(f"Total exposure {total_exposure:.2%} (including open positions) exceeded limit")
            
            # Check if we should auto-resume
            elif os.path.exists(PAUSE_FILE) and should_resume():
                resume_trading()
            
            # Log status every 5 minutes
            if int(time.time()) % 300 == 0:
                logger.info(status_msg)
            
            # Check every minute
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()
