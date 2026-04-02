# SSD Migration Data Manifest
**Generated:** $(date)
**Total Size:** 1.8GB

## Critical Components (MUST migrate)

### 1. Configuration Files
- `user_data/config.json` - Main config (8.0K)
- `user_data/config-meanrev.json` - Mean reversion bot (8.0K)
- `user_data/config-basic.json` - Basic config (4.0K)
- `user_data/config_*.json` - All other configs (~32K total)

### 2. Trading Strategies (312MB)
- `user_data/strategies/` - 312MB of strategy files
- Includes: NostalgiaForInfinity, AetherFreqaiStrategy, custom swarm
- **CRITICAL:** Do not lose these

### 3. SQLite Databases (~500KB)
- `data/trades-main.sqlite` - Main bot trades
- `data/trades-meanrev.sqlite` - Mean reversion trades
- `data/trades-trend.sqlite` - Trend bot trades
- `data/trades-breakout.sqlite` - Breakout bot trades
- `user_data/tradesv3_freqai.sqlite` - FreqAI trades
- `user_data/eth-trades.sqlite` - ETH bot trades
- `tradesv3.dryrun.sqlite` - Dry run trades

### 4. FreqAI Models (9.7MB)
- `user_data/models/` - Trained ML models
- LightGBM/XGBoost models
- **IMPORTANT:** Can be regenerated but takes hours

## Important Components (SHOULD migrate)

### 5. OHLCV Data (18MB)
- `user_data/data/` - Historical price data
- Can be re-downloaded but saves time

### 6. Hyperopt Results (8.0K)
- `user_data/hyperopts/` - Optimized parameters
- `user_data/hyperopt_results/` - Result files

### 7. Backtest Results (3.3MB)
- `user_data/backtest_results/` - Historical backtests
- For performance comparison

## Optional Components (CAN skip)

### 8. Logs (1.4MB)
- `user_data/logs/` - Application logs
- Safe to delete logs older than 7 days

### 9. Notebooks (20KB)
- `user_data/notebooks/` - Jupyter notebooks
- Analysis scripts

### 10. Plots (4.0K)
- `user_data/plot/` - Generated charts
- Can be regenerated

## Migration Priority

```
TIER 1 (Stop trading if lost):
├── configs/*.json
├── strategies/*.py
└── data/*.sqlite

TIER 2 (Hours to rebuild):
├── models/*
├── hyperopts/*
└── data/historical/*

TIER 3 (Can regenerate):
├── logs/*
├── backtest_results/*
└── plot/*
```

## Post-Migration Speed Expectations

| Operation | HDD Time | SSD Time | Improvement |
|-----------|----------|----------|-------------|
| SQLite query | 100ms | 2ms | 50x |
| FreqAI retrain | 45min | 12min | 4x |
| 90-day backtest | 25min | 5min | 5x |
| Hot-reload | 45s | 8s | 6x |
| Container start | 30s | 5s | 6x |
