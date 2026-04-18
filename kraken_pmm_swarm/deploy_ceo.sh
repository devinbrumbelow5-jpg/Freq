#!/bin/bash
# CEO DEPLOYMENT SCRIPT - April 13, 2026
# Active trading mode - no stopping until profitable

echo "=================================================="
echo "CEO DEPLOYMENT: Freq Ultimate Scalper v2.0"
echo "Time: $(date)"
echo "Directive: Trade until profitable"
echo "=================================================="

cd /root/.openclaw/workspace/kraken_pmm_swarm

# Check what's running
echo "[CEO] Checking current processes..."
ps aux | grep -E "(python3.*run_|python.*main)" | grep -v grep

# Ensure main swarm is running
if ! pgrep -f "main.py" > /dev/null; then
    echo "[CEO] Starting main Coinbase swarm..."
    nohup ./venv/bin/python main.py > logs/main_live_$(date +%Y%m%d_%H%M%S).log 2>&1 &
    sleep 2
fi

# Start scalper v2 if not running
if ! pgrep -f "run_scalper_v2.py" > /dev/null; then
    echo "[CEO] Starting Mean Reversion Scalper v2.0..."
    nohup python3 run_scalper_v2.py > logs/scalper_v2_live_$(date +%Y%m%d_%H%M%S).log 2>&1 &
    sleep 2
fi

# Check grid maker - STOP IT (losing money)
if pgrep -f "run_grid_maker.py" > /dev/null; then
    echo "[CEO] Stopping Grid Maker (losing -6.1%)..."
    pkill -f "run_grid_maker.py"
fi

# Start CEO unified controller
echo "[CEO] Starting CEO Swarm Controller..."
nohup python3 run_ceo_swarm.py > logs/ceo_swarm_$(date +%Y%m%d_%H%M%S).log 2>&1 &

echo ""
echo "[CEO] Deployment Complete. Active bots:"
sleep 1
ps aux | grep -E "(python3.*run_|python.*main)" | grep -v grep | awk '{print "  PID:", $2, "-", $11, $12}'

echo ""
echo "[CEO] Monitoring:"
echo "  tail -f logs/ceo_swarm_*.log"
echo "  tail -f logs/scalper_v2_live_*.log"
echo ""
echo "[CEO] Status check:"
echo "  python3 -c 'import sqlite3; conn=sqlite3.connect(\"./coinbase_swarm.db\"); print(\"Orders:\", conn.execute(\"SELECT COUNT(*) FROM orders\").fetchone()[0], \"Fills:\", conn.execute(\"SELECT COUNT(*) FROM fills\").fetchone()[0])'"
