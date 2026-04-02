# TOOLS.md - Freq Agent Tool Inventory v1.0

## Core Trading Tools

### 1. freqtrade_trade
**Purpose:** Start/stop trading bots with dry-run default  
**Location:** `./skills/freqtrade_trade/`  
**Input:** strategy, pairs, dry_run (default: true), leverage  
**Output:** Container ID, status, logs  
**Safety:** Always --dry-run unless explicitly overridden

### 2. freqtrade_hyperopt
**Purpose:** Run hyperparameter optimization  
**Location:** `./skills/freqtrade_hyperopt/`  
**Input:** strategy, epochs (default: 100), spaces, loss-function  
**Output:** Winning params, metrics, hyperopt_results.pkl  
**GPU:** LightGBM/XGBoost GPU acceleration if available

### 3. freqtrade_backtest
**Purpose:** Backtest strategies on historical data  
**Location:** `./skills/freqtrade_backtest/`  
**Input:** strategy, timerange, timeframe  
**Output:** Backtest report, trades list, metrics  
**Storage:** Results saved to `./freqtrade/user_data/backtest_results/`

### 4. freqtrade_list_strategies
**Purpose:** List available strategies in user_data/strategies/  
**Location:** `./skills/freqtrade_list_strategies/`  
**Input:** None  
**Output:** Strategy names, descriptions, compatibility

## FreqAI Tools

### 5. freqai_retrain
**Purpose:** Retrain FreqAI models with continual learning  
**Location:** `./skills/freqai_retrain/`  
**Input:** identifier (default: aether_adaptive_v1), train_period_days  
**Output:** Model files, predictions, training logs  
**GPU:** Required for LightGBM GPU acceleration

### 6. freqai_predict
**Purpose:** Generate predictions from trained models  
**Location:** `./skills/freqai_predict/`  
**Input:** pair, timeframe  
**Output:** Prediction values, confidence scores

## Analysis Tools

### 7. analyze_pnl
**Purpose:** Analyze profit/loss across all trades  
**Location:** `./skills/analyze_pnl/`  
**Input:** timerange, pair_filter (optional)  
**Output:** Profit factor, sharpe, win rate, drawdown

### 8. plot_profit
**Purpose:** Generate profit/loss charts  **Location:** `./skills/plot_profit/`  
**Input:** trades, timeframe  
**Output:** PNG charts saved to `./freqtrade/user_data/plots/`

### 9. regime_detection
**Purpose:** Detect market regime using chart analysis  
**Location:** `./skills/regime_detection/`  
**Input:** pair, timeframe, chart_image  
**Output:** Regime (TRENDING/RANGING/VOLATILE/CALM), confidence

## System Tools

### 10. docker_status
**Purpose:** Check Docker container health  
**Location:** Built-in  
**Input:** container_name  
**Output:** Status, uptime, resource usage

### 11. sqlite_query
**Purpose:** Query Freqtrade SQLite database  
**Location:** Built-in  
**Input:** SQL query  
**Output:** Query results

### 12. download_data
**Purpose:** Download OHLCV data via Freqtrade  
**Location:** `./skills/download_data/`  
**Input:** pairs, timeframes, days  
**Output:** Feather files in `./freqtrade/user_data/data/`

## Configuration

All tools:
- Work with `./freqtrade/` directory
- Support Docker/Docker-compose
- Support GPU acceleration where applicable
- Default to dry-run for safety
- Log all actions to `./memory/tool_logs/`
