#!/bin/bash
# Comprehensive health check for Freq trading system

LOG_FILE="/root/.openclaw/workspace/logs/health_check.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')
ERRORS=0

echo "[$DATE] Starting health check..." >> "$LOG_FILE"

# Check Docker containers
for container in freqtrade-range freqtrade-regime-filter freqtrade-log-aggregator; do
    status=$(docker inspect --format='{{.State.Status}}' $container 2>/dev/null)
    if [ "$status" != "running" ]; then
        echo "[$DATE] ERROR: $container is not running (status: $status)" >> "$LOG_FILE"
        ERRORS=$((ERRORS+1))
    else
        echo "[$DATE] OK: $container is running" >> "$LOG_FILE"
    fi
done

# Check API
api_status=$(curl -s -o /dev/null -w "%{http_code}" -u freq:scalp2026 http://localhost:8082/api/v1/ping 2>/dev/null)
if [ "$api_status" != "200" ]; then
    echo "[$DATE] ERROR: API returned status $api_status" >> "$LOG_FILE"
    ERRORS=$((ERRORS+1))
else
    echo "[$DATE] OK: API responding" >> "$LOG_FILE"
fi

# Check for zombie processes
zombie_count=$(ps aux | grep -E "drawdown_regime_guard" | grep -v grep | wc -l)
if [ "$zombie_count" -gt 1 ]; then
    echo "[$DATE] WARNING: $zombie_count regime guard processes detected, cleaning up..." >> "$LOG_FILE"
    pkill -9 -f drawdown_regime_guard
    sleep 1
fi

# Check disk space
disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$disk_usage" -gt 90 ]; then
    echo "[$DATE] ERROR: Disk usage at ${disk_usage}%" >> "$LOG_FILE"
    ERRORS=$((ERRORS+1))
fi

# Check memory
mem_available=$(free | grep Mem | awk '{print $7}')
mem_total=$(free | grep Mem | awk '{print $2}')
mem_percent=$((mem_available * 100 / mem_total))
if [ "$mem_percent" -lt 10 ]; then
    echo "[$DATE] WARNING: Low memory available (${mem_percent}%)" >> "$LOG_FILE"
fi

if [ "$ERRORS" -eq 0 ]; then
    echo "[$DATE] Health check PASSED" >> "$LOG_FILE"
else
    echo "[$DATE] Health check FAILED with $ERRORS errors" >> "$LOG_FILE"
fi

exit $ERRORS