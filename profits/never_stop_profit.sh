#!/bin/bash
# never_stop_profit.sh
# Continuous profit optimization - never stops

TZ=America/Chicago
export TZ

echo "[$(date '+%Y-%m-%d %I:%M %p %Z')] NEVER-STOP PROFIT DAEMON STARTED"
echo "Location: Brownwood, Texas"
echo "Mission: 24/7 Profit Generation"
echo ""

CYCLE=0
LAST_REPORT_HOUR=$(date +%H)

while true; do
    CYCLE=$((CYCLE + 1))
    TIMESTAMP=$(date '+%I:%M:%S %p')
    CURRENT_HOUR=$(date +%H)
    
    # Check container health every minute
    CONTAINERS=$(docker ps --filter name=freqtrade --format "{{.Names}}" 2>/dev/null | wc -l)
    
    if [ "$CONTAINERS" -lt 3 ]; then
        echo "[$(date '+%I:%M:%S %p')] 🚨 ALERT: Only $CONTAINERS/3 containers!"
        echo "[$(date '+%I:%M:%S %p')] 🔧 Restarting swarm..."
        cd /root/.openclaw/workspace/freqtrade && docker compose up -d &>/dev/null
        sleep 30
        continue
    fi
    
    # Generate hourly report on the hour
    if [ "$CURRENT_HOUR" != "$LAST_REPORT_HOUR" ]; then
        echo "[$(date '+%I:%M:%S %p')] 📊 Generating hourly report..."
        /root/.openclaw/workspace/scripts/hourly_report.sh > /dev/null 2>&1
        LAST_REPORT_HOUR=$CURRENT_HOUR
        
        # Check P&L and alert
        PNL=$(cat /root/.openclaw/workspace/memory/hourly_summary.json 2>/dev/null | grep -o '"pnl": [^,]*' | tail -1 | awk '{print $2}')
        if (( $(echo "$PNL > 1" | bc -l 2>/dev/null || echo "0") )); then
            echo "[$(date '+%I:%M:%S %p')] 🎉 HOURLY PROFIT: $PNL USDT!"
        elif (( $(echo "$PNL < -1" | bc -l 2>/dev/null || echo "0") )); then
            echo "[$(date '+%I:%M:%S %p')] ⚠️ HOURLY LOSS: $PNL USDT"
        fi
    fi
    
    # Log status every 10 cycles (10 minutes)
    if [ $((CYCLE % 10)) -eq 0 ]; then
        # Get total daily P&L
        DAY_PNL=0
        for DB in /root/.openclaw/workspace/freqtrade/user_data/trades_*.sqlite; do
            if [ -f "$DB" ]; then
                PNL=$(sqlite3 "$DB" "SELECT COALESCE(SUM(realized_profit), 0) FROM trades WHERE is_open=0 AND close_date > datetime('now', 'start of day');" 2>/dev/null || echo "0")
                DAY_PNL=$(echo "$DAY_PNL + $PNL" | bc 2>/dev/null || echo "$DAY_PNL")
            fi
        done
        
        OPEN_POS=0
        for DB in /root/.openclaw/workspace/freqtrade/user_data/trades_*.sqlite; do
            if [ -f "$DB" ]; then
                OPEN=$(sqlite3 "$DB" "SELECT COUNT(*) FROM trades WHERE is_open=1;" 2>/dev/null || echo "0")
                OPEN_POS=$((OPEN_POS + OPEN))
            fi
        done
        
        echo "[$(date '+%I:%M:%S %p')] ✅ CT: $CONTAINERS/3 bots | Daily P&L: $DAY_PNL | Open: $OPEN_POS"
    fi
    
    # Sleep 60 seconds
    sleep 60
done