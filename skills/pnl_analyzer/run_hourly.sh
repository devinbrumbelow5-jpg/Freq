#!/bin/bash
# PnL Analyzer - Hourly runner script for Freq Swarm
# Run this every hour via cron or swarm heartbeat

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/analyze_pnl.py"
exit_code=$?

# Exit code 1 means drawdown alert was triggered
if [ $exit_code -eq 1 ]; then
    echo "⚠️  DRAWDOWN ALERT - Check memory/pnl_hourly.json"
    # Could add notification hooks here (local only)
fi

exit $exit_code
