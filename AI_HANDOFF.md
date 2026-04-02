# Freq Ultimate Scalper v2.0 - AI HANDOFF DOCUMENT

**Status:** Paper trading mode - optimizing for profitability  
**Last Update:** 2026-04-02  
**Current State:** Single bot (Range Mean Reversion) - 33.3% win rate

---

## 🚨 CRITICAL CONTEXT FOR NEXT AI

### What Happened
1. Started with 3-bot swarm (Aggressive, Range, Trend)
2. **Aggressive bot:** 29.4% win rate, -7.7% PnL - **KILLED**
3. **Trend bot:** 0% win rate, 0 trades - **KILLED**
4. **Range bot:** 33.3% win rate, improving - **ONLY RUNNING BOT**

### Current Deployment
- **Single Bot:** Range Mean Reversion
- **Exchange:** OKX (Binance blocked due to geo-restriction)
- **Mode:** Paper trading (`dry_run: true`)
- **Pairs:** 10 (BTC, ETH, SOL, AVAX, LINK, UNI, AAVE, CRV, SUSHI, LTC)

---

## 📁 PROJECT STRUCTURE

```
/root/.openclaw/workspace/
├── AGENTS.md              # Swarm architecture (outdated - now single bot)
├── SOUL.md               # Original mission spec
├── HEARTBEAT.md          # 4-hour cycle protocol
├── docker-compose.yml    # NOW SINGLE BOT ONLY
│
├── freqtrade/
│   ├── docker-compose.yml
│   ├── user_data/
│   │   ├── config_range.json        # ACTIVE CONFIG
│   │   ├── config_aggressive.json   # DISABLED
│   │   ├── config_trend.json        # DISABLED
│   │   ├── strategies/
│   │   │   ├── MeanReversionScalper_v1.py  # ACTIVE STRATEGY
│   │   │   ├── AggressiveScalper_v1.py     # DISABLED
│   │   │   ├── TrendScalper_v1.py          # DISABLED
│   │   │   └── AdaptiveScalper_v1.py       # TRIED & FAILED
│   │   ├── trades_range.sqlite      # ACTIVE DATABASE
│   │   └── logs/
│   │       └── range.log
│
├── scripts/
│   ├── performance_report.sh   # Run for status
│   ├── live_monitor.sh         # Live trade tracking
│   └── verify_scalping_cycle.sh
│
└── skills/                      # OpenClaw skills for operations
```

---

## 🎯 CURRENT BOT CONFIG (Range Mean Reversion)

### Strategy Parameters
```python
timeframe = '5m'
stoploss = -0.008  # -0.8%
max_open_trades = 6
dry_run_wallet = 1000 USDT

# Entry
buy_rsi_low = 24      # Was 22, loosened to get more trades
buy_rsi_high = 35
bb_dev = 2.1          # Bollinger band deviation

# Exit
minimal_roi = {
    "0": 0.018,      # 1.8% immediate
    "45": 0.012,     # 1.2% after 45s
    "90": 0.006      # 0.6% after 90s
}

# Filters
volume_ratio > 0.8
RSI > 15 (not crashing)
BB width < 0.04 (ranging market)
```

### Performance (Last 18 Trades)
- Win Rate: 33.3% (6/18)
- Total PnL: -3.79%
- Avg Win: +0.95%
- Avg Loss: -0.79%
- Open Positions: 0 (flat)

---

## 🔧 OPERATIONAL COMMANDS

### Check Status
```bash
cd /root/.openclaw/workspace
./scripts/performance_report.sh
```

### View Recent Trades
```bash
docker exec freqtrade-range sqlite3 /freqtrade/user_data/trades_range.sqlite \
  "SELECT pair, close_profit, exit_reason FROM trades ORDER BY close_date DESC LIMIT 10;"
```

### Restart Bot
```bash
cd /root/.openclaw/workspace/freqtrade
docker restart freqtrade-range
```

### View Logs
```bash
docker logs freqtrade-range --tail 50
```

---

## 🎯 OPTIMIZATION TARGETS

The bot needs to achieve:

| Metric | Current | Target |
|--------|---------|--------|
| Win Rate | 33.3% | >48% |
| Profit Factor | ~0.8 | >1.6 |
| Avg Trade | -0.21% | >+0.3% |
| Total PnL | -3.79% | >+5% before live |

### Suggested Next Steps

1. **RUN HYPEROPT** (when data download completes)
   ```bash
   cd /root/.openclaw/workspace/freqtrade
   docker run --rm -v $(pwd)/user_data:/freqtrade/user_data \
     freqtradeorg/freqtrade:stable hyperopt \
     --strategy MeanReversionScalper_v1 \
     --timeframe 5m --timerange 20250326-20250402 \
     --spaces buy sell roi stoploss trailing \
     -e 500 --hyperopt-loss SharpeHyperOptLoss \
     --config user_data/config_range.json
   ```

2. **BACKTEST VALIDATION**
   ```bash
   docker run --rm -v $(pwd)/user_data:/freqtrade/user_data \
     freqtradeorg/freqtrade:stable backtest \
     --strategy MeanReversionScalper_v1 \
     --timeframe 5m --timerange 20250326-20250402 \
     --config user_data/config_range.json
   ```

3. **TUNE PARAMETERS** if hyperopt fails:
   - Lower RSI entry (24 → 28) for more opportunities
   - Tighten stop loss (-0.8% → -0.6%)
   - Increase position size on wins, decrease on losses

---

## 🛡️ SAFETY PROTOCOLS

- **NEVER** remove `dry_run: true` without explicit human approval
- **NEVER** add API keys without confirmation
- **NEVER** trade live until paper trading shows consistent profitability
- **ALWAYS** maintain stop losses on every trade
- **MAX** 6 concurrent positions
- **MAX** 12% drawdown kill switch

---

## 📝 NOTES

### Why Other Bots Failed

**Aggressive Scalper (1m):**
- Too many false signals on 1m timeframe
- Entry criteria too loose
- Got chopped up in ranging market
- -7.7% PnL, killed

**Trend Scalper (5m):**
- Market is choppy, not trending
- 0 trades, never got entry signals
- Strategy mismatch for current regime

**Adaptive Scalper (3m):**
- Tried to detect regimes automatically
- Entry criteria became too restrictive
- 0 trades in 2+ hours, killed

### Why Range Bot Survived

- **Market regime:** Choppy/ranging (perfect for mean reversion)
- **Entry:** Buying dips when RSI oversold
- **Exit:** Selling bounces at middle BB or overbought
- **Matches current market conditions**

---

## 🔄 DATA AVAILABILITY

- 5m data for all 10 pairs exists from 2026-03-20 onwards
- Download in progress for hyperopt
- Check: `ls freqtrade/user_data/data/okx/*.feather`

---

## 📊 MONITORING

Use these files to track progress:
- `memory/scalping_heartbeat.log` - Real-time decisions
- `freqtrade/user_data/logs/range.log` - Detailed bot logs
- `freqtrade/user_data/trades_range.sqlite` - All trade data

---

## ⚡ EMERGENCY PROCEDURES

**Stop All Trading:**
```bash
docker stop freqtrade-range
docker rm freqtrade-range
```

**Check Drawdown:**
```bash
docker exec freqtrade-range sqlite3 /freqtrade/user_data/trades_range.sqlite \
  "SELECT SUM(close_profit) FROM trades;"
```

---

**Mission:** Get Range bot to >48% win rate, >1.6 profit factor, consistent profitability. Then consider live trading.

**Current State:** Optimizing. Data downloading for hyperopt.
