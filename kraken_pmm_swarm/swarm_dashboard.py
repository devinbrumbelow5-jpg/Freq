#!/usr/bin/env python3
"""Real-time Swarm Dashboard - Monitor all bots from terminal"""

import sqlite3
import asyncio
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "ema_fixed.db"

def get_swarm_stats():
    """Get current swarm statistics."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Get total trades
        cursor.execute("SELECT COUNT(*) FROM fills")
        total_trades = cursor.fetchone()[0]
        
        # Get fills by bot
        cursor.execute("""
            SELECT bot_id, pair, side, price, amount, fee, timestamp 
            FROM fills 
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        recent_fills = cursor.fetchall()
        
        conn.close()
        return {
            'total_trades': total_trades,
            'recent_fills': recent_fills,
            'db_exists': True
        }
    except Exception as e:
        return {
            'total_trades': 0,
            'recent_fills': [],
            'db_exists': False,
            'error': str(e)
        }

def print_dashboard():
    """Print clean dashboard."""
    import os
    os.system('clear' if os.name != 'nt' else 'cls')
    
    print("=" * 80)
    print(f"  CCXT SWARM DASHBOARD | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    stats = get_swarm_stats()
    
    if not stats['db_exists']:
        print("\n  ⚠️  Database not initialized yet. Start the swarm first.")
        print("=" * 80)
        return
    
    print(f"\n  Total Trades: {stats['total_trades']}")
    
    if stats['recent_fills']:
        print("\n  Recent Activity:")
        print(f"  {'Time':<10} {'Bot':<12} {'Pair':<10} {'Side':<6} {'Price':<12} {'Amount':<12}")
        print("  " + "-" * 72)
        for fill in stats['recent_fills'][:5]:
            ts = datetime.fromtimestamp(fill[6]).strftime('%H:%M:%S')
            print(f"  {ts:<10} {fill[0]:<12} {fill[1]:<10} {fill[2].upper():<6} "
                  f"${fill[3]:<11,.2f} {fill[4]:<12,.6f}")
    else:
        print("\n  No trades yet. Waiting for EMA crossovers...")
    
    print("\n" + "=" * 80)
    print("  Status: RUNNING | Strategy: EMA 12/26 Crossover")
    print("=" * 80)

async def monitor_loop():
    """Continuous monitoring."""
    while True:
        print_dashboard()
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        print("\n\nDashboard stopped.")
