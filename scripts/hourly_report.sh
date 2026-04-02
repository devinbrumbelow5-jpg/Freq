#!/bin/bash
# hourly_report.sh
# Generate comprehensive hourly trading reports

TZ="America/Chicago"
export TZ

REPORT_FILE="/root/.openclaw/workspace/profits/hourly_report_$(date +%Y%m%d).txt"
SUMMARY_JSON="/root/.openclaw/workspace/memory/hourly_summary.json"

echo "==============================================" >> $REPORT_FILE
echo "⚡ FREQ ULTIMATE SCALPER - HOURLY REPORT" >> $REPORT_FILE
echo "==============================================" >> $REPORT_FILE
echo "Time: $(date '+%Y-%m-%d %I:%M %p %Z')" >> $REPORT_FILE
echo "Location: Brownwood, Texas (Central Time)" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# Container Status
echo "📊 SWARM STATUS:" >> $REPORT_FILE
docker ps --filter name=freqtrade --format "  {{.Names}}: {{.Status}}" >> $REPORT_FILE 2>/dev/null || echo "  ⚠️ Docker check failed" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# Trade Summary
echo "💰 TRADING PERFORMANCE (Last Hour):" >> $REPORT_FILE
TOTAL_TRADES=0
TOTAL_PNL=0
TOTAL_WINS=0
TOTAL_LOSSES=0

for DB in /root/.openclaw/workspace/freqtrade/user_data/trades_*.sqlite; do
    if [ -f "$DB" ]; then
        BOT=$(basename $DB .sqlite | sed 's/trades_//')
        STATS=$(sqlite3 "$DB" "SELECT COALESCE(COUNT(*), 0), COALESCE(SUM(realized_profit), 0), COALESCE(SUM(CASE WHEN realized_profit > 0 THEN 1 ELSE 0 END), 0), COALESCE(SUM(CASE WHEN realized_profit <= 0 THEN 1 ELSE 0 END), 0) FROM trades WHERE is_open=0 AND close_date > datetime('now', '-1 hour');" 2>/dev/null || echo "0|0|0|0")
        
        TRADES=$(echo $STATS | cut -d'|' -f1)
        PNL=$(echo $STATS | cut -d'|' -f2)
        WINS=$(echo $STATS | cut -d'|' -f3)
        LOSSES=$(echo $STATS | cut -d'|' -f4)
        
        if [ "$TRADES" -gt 0 ]; then
            printf "  %-20s: %2d trades | $%8.4f | %dW/%dL\n" "$BOT" "$TRADES" "$PNL" "$WINS" "$LOSSES" >> $REPORT_FILE
            TOTAL_TRADES=$((TOTAL_TRADES + TRADES))
            TOTAL_PNL=$(echo "$TOTAL_PNL + $PNL" | bc 2>/dev/null || echo "$TOTAL_PNL")
            TOTAL_WINS=$((TOTAL_WINS + WINS))
            TOTAL_LOSSES=$((TOTAL_LOSSES + LOSSES))
        fi
    fi
done

if [ "$TOTAL_TRADES" -eq 0 ]; then
    echo "  No trades in last hour" >> $REPORT_FILE
fi

echo "" >> $REPORT_FILE
echo "----------------------------------------------" >> $REPORT_FILE
printf "  HOURLY TOTAL:       %2d trades | $%8.4f | %dW/%dL\n" "$TOTAL_TRADES" "$TOTAL_PNL" "$TOTAL_WINS" "$TOTAL_LOSSES" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# Daily Summary
echo "📈 DAILY SUMMARY (Since Midnight CT):" >> $REPORT_FILE
DAY_TRADES=0
DAY_PNL=0

for DB in /root/.openclaw/workspace/freqtrade/user_data/trades_*.sqlite; do
    if [ -f "$DB" ]; then
        DAY_STATS=$(sqlite3 "$DB" "SELECT COALESCE(COUNT(*), 0), COALESCE(SUM(realized_profit), 0) FROM trades WHERE is_open=0 AND close_date > datetime('now', 'start of day');" 2>/dev/null || echo "0|0")
        DAY_T=$(echo $DAY_STATS | cut -d'|' -f1)
        DAY_P=$(echo $DAY_STATS | cut -d'|' -f2)
        DAY_TRADES=$((DAY_TRADES + DAY_T))
        DAY_PNL=$(echo "$DAY_PNL + $DAY_P" | bc 2>/dev/null || echo "$DAY_PNL")
    fi
done

printf "  TODAY: %d trades | $%.4f USDT\n" "$DAY_TRADES" "$DAY_PNL" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# Open Positions
echo "🎯 OPEN POSITIONS:" >> $REPORT_FILE
OPEN_COUNT=0
for DB in /root/.openclaw/workspace/freqtrade/user_data/trades_*.sqlite; do
    if [ -f "$DB" ]; then
        OPEN=$(sqlite3 "$DB" "SELECT COUNT(*) FROM trades WHERE is_open=1;" 2>/dev/null || echo "0")
        OPEN_COUNT=$((OPEN_COUNT + OPEN))
    fi
done

if [ "$OPEN_COUNT" -gt 0 ]; then
    echo "  $OPEN_COUNT positions open" >> $REPORT_FILE
else
    echo "  No open positions" >> $REPORT_FILE
fi

echo "" >> $REPORT_FILE

# System Health
echo "⚙️  SYSTEM HEALTH:" >> $REPORT_FILE
echo "  CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%" >> $REPORT_FILE
echo "  Memory: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')" >> $REPORT_FILE
echo "  Disk: $(df / | tail -1 | awk '{print $5}')" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# Status
echo "==============================================" >> $REPORT_FILE
if (( $(echo "$TOTAL_PNL > 0" | bc -l 2>/dev/null || echo "0") )); then
    echo "🟢 STATUS: PROFITABLE HOUR" >> $REPORT_FILE
elif (( $(echo "$TOTAL_PNL < 0" | bc -l 2>/dev/null || echo "0") )); then
    echo "🔴 STATUS: DRAWDOWN" >> $REPORT_FILE
else
    echo "⏳ STATUS: NO TRADES" >> $REPORT_FILE
fi
echo "==============================================" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# Save JSON summary
cat > $SUMMARY_JSON << EOF
{
  "timestamp": "$(date -Iseconds)",
  "timezone": "America/Chicago",
  "hourly": {
    "trades": $TOTAL_TRADES,
    "pnl": $TOTAL_PNL,
    "wins": $TOTAL_WINS,
    "losses": $TOTAL_LOSSES
  },
  "daily": {
    "trades": $DAY_TRADES,
    "pnl": $DAY_PNL
  },
  "open_positions": $OPEN_COUNT
}
EOF

echo "Report saved: $REPORT_FILE"