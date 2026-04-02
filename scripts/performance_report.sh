#!/bin/bash
# Performance tracker for Freq scalping bots
# Run every 30 minutes to track profitability

echo "=== Freq Scalping Performance Report ==="
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# Aggressive/Adaptive Bot
echo "--- ADAPTIVE SCALPER ---"
docker exec freqtrade-aggressive sqlite3 /freqtrade/user_data/trades_aggressive.sqlite "
SELECT 
  COUNT(*) as total_trades,
  SUM(CASE WHEN close_profit > 0 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN close_profit <= 0 THEN 1 ELSE 0 END) as losses,
  ROUND(100.0 * SUM(CASE WHEN close_profit > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate,
  ROUND(SUM(close_profit)*100, 2) as total_pnl_pct,
  ROUND(AVG(close_profit)*100, 2) as avg_profit_pct,
  COUNT(CASE WHEN is_open=1 THEN 1 END) as open_positions
FROM trades;
" 2>/dev/null || echo "Database not accessible"

# Range Bot
echo ""
echo "--- RANGE MEAN REVERSION ---"
docker exec freqtrade-range sqlite3 /freqtrade/user_data/trades_range.sqlite "
SELECT 
  COUNT(*) as total_trades,
  SUM(CASE WHEN close_profit > 0 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN close_profit <= 0 THEN 1 ELSE 0 END) as losses,
  ROUND(100.0 * SUM(CASE WHEN close_profit > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate,
  ROUND(SUM(close_profit)*100, 2) as total_pnl_pct,
  ROUND(AVG(close_profit)*100, 2) as avg_profit_pct,
  COUNT(CASE WHEN is_open=1 THEN 1 END) as open_positions
FROM trades;
" 2>/dev/null || echo "Database not accessible"

echo ""
echo "=== Container Status ==="
docker ps --filter name=freqtrade --format "{{.Names}}: {{.Status}}" 2>/dev/null

echo ""
echo "=== End Report ==="
