#!/bin/bash
# Auto-check scalper status every 5 minutes

cd /root/.openclaw/workspace/kraken_pmm_swarm

PID=$(cat /tmp/scalper_v2.pid 2>/dev/null)
if ! ps -p $PID >/dev/null 2>&1; then
    echo "$(date): ALERT - Scalper not running!" >> logs/monitor_alerts.log
    # Could add: telegram send here
    exit 1
fi

# Get latest status
LOG=$(ls -t logs/scalper_v2_*.log 2>/dev/null | head -1)
if [ -f "$LOG" ]; then
    tail -5 "$LOG" > logs/last_status.txt
fi

# Check if stuck (no new output for 10 min)
if [ -f "$LOG" ]; then
    AGE=$(stat -c %Y "$LOG")
    NOW=$(date +%s)
    DIFF=$((NOW - AGE))
    if [ $DIFF -gt 600 ]; then
        echo "$(date): WARNING - No log updates for ${DIFF}s" >> logs/monitor_alerts.log
    fi
fi

echo "$(date): Check complete - PID $PID running" >> logs/monitor.log
