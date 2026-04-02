#!/usr/bin/env python3
"""Test script to verify PnL analyzer with mock data"""

import sqlite3
import os
import tempfile
from pathlib import Path
import sys

# Add skill to path
sys.path.insert(0, "/root/.openclaw/workspace/skills/pnl_analyzer")
from analyze_pnl import calculate_pnl_metrics, check_drawdown_alert

# Test 1: Empty trades
print("Test 1: Empty trades")
result = calculate_pnl_metrics([])
assert result["total_trades"] == 0
assert result["win_rate"] == 0.0
print("  ✓ Empty trades handled correctly")

# Test 2: Simple win/loss
print("Test 2: Simple win/loss calculation")
mock_trades = [
    {"is_open": False, "close_profit": 0.05, "close_profit_abs": 50.0, "stake_amount": 1000, "close_date": "2026-03-26T20:00:00"},
    {"is_open": False, "close_profit": -0.02, "close_profit_abs": -20.0, "stake_amount": 1000, "close_date": "2026-03-26T21:00:00"},
    {"is_open": False, "close_profit": 0.03, "close_profit_abs": 30.0, "stake_amount": 1000, "close_date": "2026-03-26T22:00:00"},
]
result = calculate_pnl_metrics(mock_trades)
assert result["total_trades"] == 3
assert result["winning_trades"] == 2
assert result["losing_trades"] == 1
assert result["win_rate"] == 66.67
assert abs(result["total_profit_abs"] - 60.0) < 0.01
print(f"  ✓ Win rate: {result['win_rate']}% (2/3)")
print(f"  ✓ Total profit: ${result['total_profit_abs']}")

# Test 3: Drawdown calculation
print("Test 3: Drawdown calculation")
# Sequence: +50, -20 (drawdown from 50 to 30 = 40%), +30 (drawdown ends), +10
mock_trades = [
    {"is_open": False, "close_profit": 0.05, "close_profit_abs": 50.0, "stake_amount": 1000, "close_date": "2026-03-26T20:00:00"},
    {"is_open": False, "close_profit": -0.02, "close_profit_abs": -80.0, "stake_amount": 1000, "close_date": "2026-03-26T21:00:00"},
    {"is_open": False, "close_profit": 0.03, "close_profit_abs": 30.0, "stake_amount": 1000, "close_date": "2026-03-26T22:00:00"},
]
result = calculate_pnl_metrics(mock_trades)
print(f"  ✓ Max drawdown: {result['max_drawdown_pct']}%")
assert result["max_drawdown_pct"] > 0

# Test 4: Drawdown alert thresholds
print("Test 4: Drawdown alert thresholds")

# Below threshold
result_low = {"max_drawdown_pct": 5.0}
alert = check_drawdown_alert(result_low)
assert alert is None
print("  ✓ 5% drawdown: No alert")

# Warning threshold (8-10%)
result_warn = {"max_drawdown_pct": 9.0}
alert = check_drawdown_alert(result_warn)
assert alert is not None
assert "WARN" in alert
print("  ✓ 9% drawdown: Warning alert")

# Critical threshold (>10%)
result_crit = {"max_drawdown_pct": 12.0}
alert = check_drawdown_alert(result_crit)
assert alert is not None
assert "CRITICAL" in alert
print("  ✓ 12% drawdown: Critical alert")

print("\n=== All tests passed! ===")
