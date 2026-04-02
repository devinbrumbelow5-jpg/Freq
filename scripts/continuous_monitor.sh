#!/bin/bash
# continuous_monitor.sh
# Continuous monitoring and adaptive trading

echo "[$(date '+%H:%M:%S')] Starting continuous trading monitor..."
echo "Monitoring: 3 freqtrade containers"
echo "Strategy: Market-adaptive scalping"
echo ""

while true; do
    TIMESTAMP=$(date '+%H:%M:%S')
    DATE=$(date '+%Y-%m-%d')
    
    # Check container health
    SCALP_MAIN=$(docker ps --filter name=freqtrade-scalp-main --format "{{.Status}}" 2>/dev/null || echo "down")
    MICRO=$(docker ps --filter name=freqtrade-micro --format "{{.Status}}" 2>/dev/null || echo "down")
    RANGE=$(docker ps --filter name=freqtrade-range --format "{{.Status}}" 2>/dev/null || echo "down")
    
    # Count running containers
    COUNT=$(docker ps --filter name=freqtrade --format "{{.Names}}" | wc -l)
    
    # Check for recent trades in last hour
    TRADES=$(sqlite3 /root/.openclaw/workspace/freqtrade/user_data/tradesv3.sqlite \
        "SELECT COUNT(*) FROM trades WHERE close_date > datetime('now', '-1 hour')" 2>/dev/null || echo "0")
    
    # Check P&L
    PNL=$(sqlite3 /root/.openclaw/workspace/freqtrade/user_data/tradesv3.sqlite \
        "SELECT COALESCE(SUM(profit_ratio * stake_amount), 0) FROM trades WHERE close_date > datetime('now', '-24 hours')" 2>/dev/null || echo "0")
    
    # Log status
    echo "[$TIMESTAMP] Containers: $COUNT/3 | Trades(last hour): $TRADES | 24h P&L: $PNL USDT"
    
    # Alert if containers down
    if [ "$COUNT" -lt 3 ]; then
        echo "[$TIMESTAMP] 🚨 ALERT: $COUNT/3 containers running!"
        echo "[$TIMESTAMP] Restarting swarm..."
        cd /root/.openclaw/workspace/freqtrade && docker compose up -d 2>&1
    fi
    
    # Save metrics to memory
    mkdir -p /root/.openclaw/workspace/memory/trading
    cat > /root/.openclaw/workspace/memory/trading/monitor_${DATE}.log << EOF
{ "timestamp": "$TIMESTAMP", "containers": $COUNT, "recent_trades": $TRADES, "daily_pnl": $PNL }
EOF
    
    # Sleep 60 seconds before next check
    sleep 60
done