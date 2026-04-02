#!/bin/bash
# live_data_monitor.sh
# Continuously monitor live data feeds and ensure trading active

echo "[$(date '+%H:%M:%S')] Starting live data monitor..."

while true; do
    TIMESTAMP=$(date '+%H:%M:%S')
    
    # Check container health
    CONTAINERS=$(docker ps --filter name=freqtrade --format "{{.Names}}" | wc -l)
    
    if [ "$CONTAINERS" -lt 3 ]; then
        echo "[$TIMESTAMP] 🚨 ALERT: Only $CONTAINERS/3 containers running!"
        echo "[$TIMESTAMP] Restarting swarm..."
        cd /root/.openclaw/workspace/freqtrade && docker compose up -d
    else
        echo "[$TIMESTAMP] ✅ Swarm healthy: 3/3 containers"
    fi
    
    # Check for recent trades (every 5 minutes)
    sleep 60
done