#!/bin/bash
# CEO STATUS CHECK - Run this anytime to see trading status

cd /root/.openclaw/workspace/kraken_pmm_swarm

echo "=============================================="
echo "CEO STATUS REPORT - $(date)"
echo "=============================================="

echo ""
echo "[ACTIVE PROCESSES]"
ps aux | grep -E "(python3.*run_|python.*main|ceo_swarm)" | grep -v grep | awk '{printf "  PID %-8s CPU %5s%% MEM %5s%% %s\n", $2, $3, $4, $11}'

echo ""
echo "[DATABASE ACTIVITY]"
python3 << 'EOF'
import sqlite3
import json
from datetime import datetime

dbs = ['coinbase_swarm.db', 'scalper_v2.db', 'grid_maker.db', 'ceo_swarm.db']
for db_file in dbs:
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        if 'fills' in tables:
            cursor.execute("SELECT COUNT(*) FROM fills")
            fills = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM orders")
            orders = cursor.fetchone()[0]
            print(f"  {db_file}: {fills} fills, {orders} orders")
        conn.close()
    except Exception as e:
        print(f"  {db_file}: {e}")
EOF

echo ""
echo "[LATEST TRADES]"
python3 << 'EOF'
import sqlite3
from datetime import datetime

try:
    conn = sqlite3.connect('coinbase_swarm.db')
    cursor = conn.cursor()
    cursor.execute("SELECT pair, side, amount, price, timestamp FROM fills ORDER BY timestamp DESC LIMIT 5")
    for row in cursor.fetchall():
        pair, side, amount, price, ts = row
        print(f"  {ts}: {side} {amount} {pair} @ ${price:,.2f}")
    conn.close()
except Exception as e:
    print(f"  Error: {e}")
EOF

echo ""
echo "[LOG FILES]"
ls -lth logs/*.log 2>/dev/null | head -5 | awk '{print "  " $9 " (" $5 " bytes)"}'

echo ""
echo "=============================================="
echo "Monitor: tail -f logs/scalper_v2_live_*.log"
echo "=============================================="
