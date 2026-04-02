#!/bin/bash
# profit_summary.sh
# Real-time profit summary

echo "=========================================="
echo "💰 FREQ ULTIMATE SCALPER - PROFIT REPORT 💰"
echo "=========================================="
echo "Timestamp: $(date)"
echo ""

# Container status
echo "📊 SWARM STATUS:"
docker ps --filter name=freqtrade --format "  ✅ {{.Names}}: {{.Status}}"
echo ""

# Profit summary
echo "💵 TRADING PERFORMANCE:"
TOTAL_PNL=0
TOTAL_TRADES=0

for DB in /root/.openclaw/workspace/freqtrade/user_data/trades_*.sqlite; do
    if [ -f "$DB" ]; then
        BOT=$(basename $DB .sqlite)
        STATS=$(sqlite3 "$DB" "SELECT COALESCE(COUNT(*), 0), COALESCE(SUM(profit_amount), 0), COALESCE(SUM(CASE WHEN profit_amount > 0 THEN 1 ELSE 0 END), 0), COALESCE(SUM(CASE WHEN profit_amount <= 0 THEN 1 ELSE 0 END), 0) FROM trades WHERE is_open=0;" 2>/dev/null || echo "0|0|0|0")
        
        TRADES=$(echo $STATS | cut -d'|' -f1)
        PNL=$(echo $STATS | cut -d'|' -f2)
        WINS=$(echo $STATS | cut -d'|' -f3)
        LOSSES=$(echo $STATS | cut -d'|' -f4)
        
        if [ "$TRADES" -gt 0 ]; then
            WIN_RATE=$(echo "scale=1; $WINS * 100 / $TRADES" | bc)
            echo "  📈 $BOT: $TRADES trades | $PNL USDT | ${WIN_RATE}% wins"
            TOTAL_PNL=$(echo "$TOTAL_PNL + $PNL" | bc)
            TOTAL_TRADES=$((TOTAL_TRADES + TRADES))
        fi
    fi
done

echo ""
echo "=========================================="
echo "TOTAL PERFORMANCE:"
echo "  📊 Total Trades: $TOTAL_TRADES"
echo "  💰 Total P&L: $TOTAL_PNL USDT"

if (( $(echo "$TOTAL_PNL > 0" | bc -l 2>/dev/null || echo "0") )); then
    echo "  🟢 STATUS: PROFITABLE!"
elif (( $(echo "$TOTAL_PNL < 0" | bc -l 2>/dev/null || echo "0") )); then
    echo "  🔴 STATUS: DRAWDOWN"
else
    echo "  ⏳ STATUS: WAITING FOR FIRST TRADE"
fi

echo "=========================================="