#!/bin/bash
# Periodic report script for Scalper v2

cd /root/.openclaw/workspace/kraken_pmm_swarm

LOG=$(ls -t logs/scalper_v2_*.log 2>/dev/null | head -1)
PID=$(cat /tmp/scalper_v2.pid 2>/dev/null)

if [ ! -f "$LOG" ]; then
    echo "No log file found"
    exit 1
fi

# Count trades
TRADES=$(grep -c "Fill recorded" "$LOG" 2>/dev/null || echo "0")
EXITS=$(grep -cE "(CLOSED|take_profit|stop_loss)" "$LOG" 2>/dev/null || echo "0")

# Get last status line
LAST_STATUS=$(grep "USD:" "$LOG" | tail -1)

# Check if running
if ps -p "$PID" > /dev/null 2>&1; then
    STATE="RUNNING"
else
    STATE="STOPPED"
fi

echo "=================================="
echo "SCALPER v2 REPORT - $(date '+%H:%M %Z')"
echo "=================================="
echo "Status: $STATE (PID: $PID)"
echo "Fills: $TRADES | Exits: $EXITS"
echo "$LAST_STATUS"
echo "=================================="
