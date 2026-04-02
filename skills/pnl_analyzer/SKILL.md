# PnL Analyzer Skill

## Purpose
Hourly profit/loss analyzer for the Freq trading swarm. Calculates win rate, drawdown, profit factor, and Sharpe ratio across all trade databases.

## Location
`./skills/pnl_analyzer/`

## Files
- `analyze_pnl.py` - Main analysis engine
- `run_hourly.sh` - Hourly execution wrapper
- `SKILL.md` - This file

## Usage

### Manual Run
```bash
python3 skills/pnl_analyzer/analyze_pnl.py
```

### Via Wrapper
```bash
bash skills/pnl_analyzer/run_hourly.sh
```

### Cron (Hourly)
```bash
0 * * * * cd /root/.openclaw/workspace && bash skills/pnl_analyzer/run_hourly.sh >> memory/logs/pnl_cron.log 2>&1
```

## Output

### Terminal Output
```
[22:37:44] [PnL] [INFO] Starting hourly PnL analysis...
[22:37:44] [PnL] [INFO] Loaded X trades from trades-main.sqlite
...
[22:37:44] [PnL] [INFO] === HOURLY PnL SUMMARY ===
[22:37:44] [PnL] [INFO] Total Trades: N (Open: X, Closed: Y)
[22:37:44] [PnL] [INFO] Win Rate: XX.XX% (W wins / L losses)
[22:37:44] [PnL] [INFO] Total Profit: $X.XXXX (X.XX%)
[22:37:44] [PnL] [INFO] Profit Factor: X.XX | Sharpe: X.XX
[22:37:44] [PnL] [INFO] Max Drawdown: X.XX% ($X.XXXX)
```

### JSON Output (`memory/pnl_hourly.json`)
```json
{
  "timestamp": "2026-03-26T22:37:44.540471",
  "metrics": {
    "total_trades": N,
    "winning_trades": W,
    "losing_trades": L,
    "win_rate": XX.XX,
    "total_profit_abs": X.XXXX,
    "total_profit_pct": X.XXXX,
    "max_drawdown_pct": X.XX,
    "profit_factor": X.XX,
    "sharpe_ratio": X.XX
  },
  "hourly_breakdown": [...],
  "pair_breakdown": {...},
  "alert": null
}
```

## Alert Thresholds

| Drawdown Level | Action |
|---------------|--------|
| > 10% | 🚨 CRITICAL - Returns exit code 1 |
| 8-10% | ⚠️ WARNING - Logged to terminal |
| < 8% | Normal operation |

## Data Sources

Scans these databases:
- `freqtrade/data/trades-main.sqlite`
- `freqtrade/data/trades-trend.sqlite`
- `freqtrade/data/trades-meanrev.sqlite`
- `freqtrade/data/trades-breakout.sqlite`
- `freqtrade/user_data/tradesv3_freqai.sqlite`

## Integration

### From Swarm Agents
Agents should read `memory/pnl_hourly.json` to check current risk metrics:
- Risk Guardian: Uses `max_drawdown_pct` for emergency stops
- Strategy Generator: Uses `win_rate` and `profit_factor` for strategy switching
- Hyperopt Engineer: Uses metrics to trigger re-optimization

### Exit Codes
- `0` - Analysis complete, no alerts
- `1` - Analysis complete, drawdown alert triggered
- `2` - Error occurred

## Metrics Calculated

1. **Win Rate** - Percentage of profitable trades
2. **Profit Factor** - Gross profit / Gross loss
3. **Sharpe Ratio** - Risk-adjusted return (annualized)
4. **Max Drawdown** - Peak-to-trough decline percentage
5. **Total Profit** - Absolute and percentage PnL
6. **Hourly Breakdown** - Last 24 hours of trade data
7. **Pair Breakdown** - Performance per trading pair
