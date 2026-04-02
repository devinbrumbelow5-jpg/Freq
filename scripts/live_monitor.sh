#!/bin/bash
# Live trade monitor - runs every 5 minutes
# Sends summary of new trades

cd /root/.openclaw/workspace/freqtrade

# Get latest closed trades
NEW_TRADES=$(docker exec freqtrade-range sqlite3 /freqtrade/user_data/trades_range.sqlite "
SELECT pair, ROUND(close_profit*100,2) as profit, exit_reason 
FROM trades 
WHERE close_date > datetime('now', '-5 minutes') 
ORDER BY close_date DESC;
" 2>/dev/null)

if [ ! -z "$NEW_TRADES" ]; then
    echo "=== NEW TRADES LAST 5 MIN ==="
    echo "$NEW_TRADES"
    echo ""
fi

# Get open positions
OPEN=$(docker exec freqtrade-range sqlite3 /freqtrade/user_data/trades_range.sqlite "
SELECT COUNT(*), GROUP_CONCAT(pair) FROM trades WHERE is_open=1;
" 2>/dev/null)

if [ ! -z "$OPEN" ]; then
    echo "=== OPEN POSITIONS ==="
    echo "$OPEN"
fi
