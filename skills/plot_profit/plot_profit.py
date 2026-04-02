#!/usr/bin/env python3
"""
plot_profit: Generate profit/loss charts from trade data
"""

import sqlite3
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
import subprocess

def generate_chart_data(db_path, days=30):
    """Generate data for profit chart"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT close_date, profit_ratio, cumulative_profit
        FROM trades
        WHERE close_date IS NOT NULL
        AND close_date > ?
        ORDER BY close_date
    """, [start_date])
    
    trades = cursor.fetchall()
    conn.close()
    return trades

def main():
    parser = argparse.ArgumentParser(description='Generate P&L charts')
    parser.add_argument('--db', default='/root/.openclaw/workspace/freqtrade/tradesv3.dryrun.sqlite',
                       help='Path to SQLite database')
    parser.add_argument('--days', type=int, default=30, help='Chart period in days')
    parser.add_argument('--output', default='/root/.openclaw/workspace/freqtrade/user_data/plots/profit_chart.png',
                       help='Output PNG file path')
    parser.add_argument('--format', choices=['png', 'svg', 'html'], default='png',
                       help='Output format')
    
    args = parser.parse_args()
    
    if not Path(args.db).exists():
        print(f"❌ Database not found: {args.db}")
        return
    
    print(f"📊 Generating profit chart...")
    print(f"   Period: {args.days} days")
    print(f"   Output: {args.output}")
    
    trades = generate_chart_data(args.db, args.days)
    
    if not trades:
        print("❌ No trade data available for charting")
        return
    
    # Ensure output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    # Use Freqtrade's built-in plot-profit command via Docker
    cmd = [
        'docker', 'run', '--rm',
        '-v', '/root/.openclaw/workspace/freqtrade/user_data:/freqtrade/user_data:cached',
        'freqtradeorg/freqtrade:stable_freqai',
        'plot-profit',
        '--config', '/freqtrade/user_data/config.json',
        '--export-filename', f'/freqtrade/user_data/plots/profit_chart_{datetime.now().strftime("%Y%m%d")}.png',
        '--timerange', f"{(datetime.now() - timedelta(days=args.days)).strftime('%Y%m%d')}-{datetime.now().strftime('%Y%m%d')}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Chart generated successfully")
            print(f"   Location: /freqtrade/user_data/plots/")
            
            # List available plots
            plots_dir = Path('/root/.openclaw/workspace/freqtrade/user_data/plots')
            if plots_dir.exists():
                plots = list(plots_dir.glob('*.png'))
                print(f"\n📁 Available plots ({len(plots)} total):")
                for plot in sorted(plots)[-5:]:  # Show last 5
                    print(f"   • {plot.name}")
        else:
            print(f"⚠️  Using fallback ASCII chart:")
            print(f"\n{'='*60}")
            
            # Calculate cumulative profit
            cumulative = 0
            profits = []
            for trade in trades:
                cumulative += trade['profit_ratio']
                profits.append(cumulative)
            
            # Simple ASCII chart
            if profits:
                max_val = max(abs(min(profits)), abs(max(profits)))
                if max_val == 0:
                    max_val = 0.01
                
                print(f"Cumulative Profit Over {args.days} Days")
                print(f"{'='*60}")
                
                # Show last 20 trades
                for i, profit in enumerate(profits[-20:]):
                    bar_len = int(abs(profit) / max_val * 30)
                    bar = '█' * bar_len
                    sign = '+' if profit >= 0 else '-'
                    print(f"{i+1:2d}. {sign}{bar:<30} {profit*100:+.2f}%")
                
                print(f"{'='*60}")
                print(f"Final: {profits[-1]*100:+.2f}% | Trades: {len(trades)}")
            
    except Exception as e:
        print(f"❌ Error generating chart: {e}")

if __name__ == '__main__':
    main()
