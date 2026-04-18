#!/usr/bin/env python3
"""
PROFITGUARD AI — Automated Hourly Report Generator
Called by OpenClaw cron every hour
"""

import sqlite3
import ccxt
import subprocess
from datetime import datetime
import json
import os

# Report file location
REPORT_FILE = "/root/.openclaw/workspace/memory/profitguard_latest_report.json"
LOG_FILE = "/root/.openclaw/workspace/memory/profitguard_hourly_log.txt"

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S CDT')
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(msg)

def generate_report():
    report = {
        "timestamp": datetime.now().isoformat(),
        "time_cdt": datetime.now().strftime('%I:%M %p CDT'),
        "scalper": {},
        "main_swarm": {},
        "pnl": {},
        "actions": []
    }
    
    log("="*70)
    log(f"PROFITGUARD AI — HOURLY REPORT — {report['time_cdt']}")
    log("="*70)
    
    # Check processes
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    procs = [l for l in result.stdout.split('\n') if any(x in l for x in ['scalper', 'main.py']) and 'grep' not in l and 'python' in l]
    
    log("\n[SYSTEM STATUS]")
    for p in procs:
        parts = p.split()
        if len(parts) >= 11:
            pid = parts[1]
            cpu = parts[2]
            mem = parts[3]
            runtime = parts[9]
            if 'scalper' in p.lower():
                report["scalper"] = {"pid": pid, "cpu": cpu, "mem": mem, "runtime": runtime, "status": "RUNNING"}
                log(f"Scalper v2: PID {pid} | CPU {cpu}% | MEM {mem}% | {runtime}")
            elif 'main.py' in p:
                report["main_swarm"] = {"pid": pid, "cpu": cpu, "mem": mem, "runtime": runtime, "status": "RUNNING"}
                log(f"Main Swarm: PID {pid} | CPU {cpu}% | MEM {mem}% | {runtime}")
    
    # Get prices
    try:
        exchange = ccxt.coinbase({'enableRateLimit': True})
        prices = {
            'BTC/USD': exchange.fetch_ticker('BTC/USD')['last'],
            'ETH/USD': exchange.fetch_ticker('ETH/USD')['last'],
            'SOL/USD': exchange.fetch_ticker('SOL/USD')['last']
        }
    except:
        prices = {}
    
    # Database analysis
    conn = sqlite3.connect('/root/.openclaw/workspace/kraken_pmm_swarm/scalper_v2.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM fills")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM fills WHERE side='buy'")
    buys = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM fills WHERE side='sell'")
    sells = cursor.fetchone()[0]
    
    report["scalper"]["total_fills"] = total
    report["scalper"]["open_positions"] = buys - sells
    report["scalper"]["completed_sells"] = sells
    
    log(f"\n[SCALPER V2 METRICS]")
    log(f"  Total fills: {total}")
    log(f"  Open positions: {buys - sells}")
    log(f"  Completed sells: {sells}")
    
    # Calculate P&L
    if prices:
        total_unrealized = 0
        pair_data = {}
        
        for pair in ['BTC/USD', 'ETH/USD', 'SOL/USD']:
            current = prices.get(pair, 0)
            cursor.execute("SELECT side, price, amount FROM fills WHERE pair = ? ORDER BY filled_at ASC", (pair,))
            fills = cursor.fetchall()
            
            buys_fifo = []
            realized = 0
            
            for side, price, amount in fills:
                if side == 'buy':
                    buys_fifo.append([price, amount])
                else:
                    sell_amt = amount
                    while sell_amt > 0.00001 and buys_fifo:
                        entry, buy_amt = buys_fifo[0]
                        match = min(sell_amt, buy_amt)
                        realized += match * (price - entry)
                        sell_amt -= match
                        buys_fifo[0][1] -= match
                        if buys_fifo[0][1] <= 0.00001:
                            buys_fifo.pop(0)
            
            if buys_fifo and current:
                qty = sum(b[1] for b in buys_fifo)
                cost = sum(b[0] * b[1] for b in buys_fifo)
                avg = cost / qty if qty > 0 else 0
                unrealized = qty * (current - avg)
                total_unrealized += unrealized
                pair_data[pair] = {"lots": len(buys_fifo), "unrealized": unrealized}
        
        report["pnl"] = {
            "realized": realized,
            "unrealized": total_unrealized,
            "total": realized + total_unrealized,
            "pairs": pair_data
        }
        
        log(f"\n[P&L SUMMARY]")
        log(f"  Realized: ${realized:.2f}")
        log(f"  Unrealized: ${total_unrealized:.2f}")
        log(f"  Total P&L: ${realized + total_unrealized:.2f}")
    
    # Recent activity
    cursor.execute("SELECT pair, side, price, amount, filled_at FROM fills ORDER BY id DESC LIMIT 3")
    recent = cursor.fetchall()
    log(f"\n[RECENT ACTIVITY]")
    for row in recent:
        ts = row[4][11:16] if len(row[4]) > 19 else row[4]
        log(f"  {ts} {row[1].upper()} {row[3]:.4f} {row[0]} @ ${row[2]:,.2f}")
    
    conn.close()
    
    # Save report
    report["actions"].append("Hourly status check completed")
    report["next_check"] = (datetime.now().replace(minute=0, second=0) + __import__('datetime').timedelta(hours=1)).strftime('%I:%M %p CDT')
    
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2)
    
    log(f"\nReport saved to: {REPORT_FILE}")
    log(f"Next hourly report: {report['next_check']}")
    log("="*70)
    
    return report

if __name__ == '__main__':
    generate_report()
