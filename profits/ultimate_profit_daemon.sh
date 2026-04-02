#!/bin/bash
# ULTIMATE PROFIT DAEMON
# Runs 24/7, never stops, makes money

LOG_FILE="/root/.openclaw/workspace/profits/profit_log.txt"
ALERT_LOG="/root/.openclaw/workspace/profits/alerts.txt"
PID_FILE="/root/.openclaw/workspace/profits/daemon.pid"

echo $$ > $PID_FILE
echo "[$(date)] ULTIMATE PROFIT DAEMON STARTED" >> $LOG_FILE

# Function to log profits
log_profit() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# Function to send alerts
alert() {
    echo "[$(date)] 🚨 $1" >> $ALERT_LOG
    echo "🚨 $1"
}

log_profit "Daemon PID: $$"
log_profit "Monitoring 3 freqtrade containers"

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    TIMESTAMP=$(date '+%H:%M:%S')
    
    # Check if containers are running
    CONTAINERS=$(docker ps --filter name=freqtrade --format "{{.Names}}" 2>/dev/null | wc -l)
    
    if [ "$CONTAINERS" -lt 3 ]; then
        alert "CONTAINER DOWN! Only $CONTAINERS/3 running. RESTARTING..."
        cd /root/.openclaw/workspace/freqtrade && docker compose up -d &>/dev/null
        log_profit "Restarted swarm at $TIMESTAMP"
        sleep 30
        continue
    fi
    
    # Check trades across all DBs
    TOTAL_TRADES=0
    TOTAL_PROFIT=0
    OPEN_TRADES=0
    
    for DB in /root/.openclaw/workspace/freqtrade/user_data/tradesv3.sqlite \
              /root/.openclaw/workspace/freqtrade/user_data/trades_micro.sqlite \
              /root/.openclaw/workspace/freqtrade/user_data/trades_range.sqlite; do
        if [ -f "$DB" ]; then
            # Get trade count
            TRADES=$(sqlite3 "$DB" "SELECT COUNT(*) FROM trades WHERE is_open=0;" 2>/dev/null || echo "0")
            TOTAL_TRADES=$((TOTAL_TRADES + TRADES))
            
            # Get profit
            PROFIT=$(sqlite3 "$DB" "SELECT COALESCE(SUM(profit_amount), 0) FROM trades WHERE is_open=0;" 2>/dev/null || echo "0")
            TOTAL_PROFIT=$(echo "$TOTAL_PROFIT + $PROFIT" | bc 2>/dev/null || echo "$TOTAL_PROFIT")
            
            # Get open trades
            OPEN=$(sqlite3 "$DB" "SELECT COUNT(*) FROM trades WHERE is_open=1;" 2>/dev/null || echo "0")
            OPEN_TRADES=$((OPEN_TRADES + OPEN))
        fi
    done
    
    # Log every 10 cycles (10 minutes)
    if [ $((CYCLE % 10)) -eq 0 ]; then
        log_profit "CYCLE $CYCLE | Containers: $CONTAINERS/3 | Trades: $TOTAL_TRADES | Open: $OPEN_TRADES | Profit: $TOTAL_PROFIT USDT"
    fi
    
    # Alert on significant profit
    if (( $(echo "$TOTAL_PROFIT > 10" | bc -l 2>/dev/null || echo "0") )); then
        alert "PROFIT MILESTONE: $TOTAL_PROFIT USDT!"
    fi
    
    # Alert on drawdown
    if (( $(echo "$TOTAL_PROFIT < -50" | bc -l 2>/dev/null || echo "0") )); then
        alert "DANGER: Drawdown $TOTAL_PROFIT USDT!"
    fi
    
    # Sleep 60 seconds
    sleep 60
done